"""S&P 보도자료 서술문에서 후보 이벤트의 행동과 적용일을 보수적으로 검증한다."""

from __future__ import annotations

import argparse
import csv
import re
from datetime import date, datetime
from pathlib import Path

from lxml import html

from herd.constituent_event_contract import (
    ConstituentEventContractError,
    classify_effective_timing,
)

EXCHANGE_TICKER = r"\((?:NYSE|NASD|NASDAQ|AMEX|OTC)\s*:\s*{ticker}\b[^)]*\)"
ANY_EXCHANGE_TICKER = re.compile(
    r"\((?:NYSE(?:\s+MKT|\s+American)?|NASD|NASDAQ|AMEX|OTC)\s*:\s*"
    r"[A-Z0-9.-]+\b[^)]*\)",
    re.IGNORECASE,
)
DATE_PATTERN = re.compile(
    r"(?:January|February|March|April|May|June|July|August|September|Sept\.?|"
    r"October|November|December|Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|"
    r"Aug\.?|Sep\.?|Oct\.?|Nov\.?|Dec\.?)\s+\d{1,2}(?:,?\s+\d{4})?",
    re.IGNORECASE,
)
QUALIFIER_PATTERN = re.compile(
    r"(?:effective|prior to (?:the )?open(?:ing)?|before (?:the )?market opens|"
    r"after (?:the )?close(?: of trading)?|at (?:the )?open(?: of trading)?|"
    r"prior to (?:the )?market open)",
    re.IGNORECASE,
)


class ProseVerificationError(RuntimeError):
    pass


def normalize_text(content: bytes) -> str:
    document = html.fromstring(content)
    return " ".join(document.text_content().replace("\xa0", " ").split())


def parse_date_mention(value: str, *, published_date: date | None = None) -> date:
    normalized = re.sub(r"\bSept(?:\.|\b)", "Sep", value).replace(".", "")
    normalized = re.sub(r",\s*", ", ", normalized)
    for pattern in ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(normalized, pattern).date()
        except ValueError:
            continue
    if published_date is not None:
        for pattern in ("%B %d", "%b %d"):
            try:
                parsed = datetime.strptime(normalized, pattern)
                inferred = date(published_date.year, parsed.month, parsed.day)
                if inferred < published_date:
                    inferred = date(published_date.year + 1, parsed.month, parsed.day)
                return inferred
            except ValueError:
                continue
    raise ProseVerificationError(f"unsupported date mention: {value}")


def qualified_effective_mentions(
    text: str,
    start: int,
    end: int,
    *,
    published_date: date,
) -> set[tuple[date, str]]:
    window_start = max(0, start - 1600)
    window_end = min(len(text), end + 1600)
    window = text[window_start:window_end]
    occurrence_start = start - window_start
    occurrence_end = end - window_start
    mentions = []
    for match in DATE_PATTERN.finditer(window):
        qualifier_start = max(0, match.start() - 130)
        qualifier_end = min(len(window), match.end() + 40)
        context = window[qualifier_start:qualifier_end]
        if not QUALIFIER_PATTERN.search(context):
            continue
        try:
            timing = classify_effective_timing(context)
        except ConstituentEventContractError:
            continue
        if match.end() <= occurrence_start:
            distance = occurrence_start - match.end()
        elif match.start() >= occurrence_end:
            distance = match.start() - occurrence_end
        else:
            distance = 0
        mentions.append((
            distance,
            parse_date_mention(match.group(), published_date=published_date),
            timing,
        ))
    if not mentions:
        return set()
    nearest_distance = min(item[0] for item in mentions)
    return {
        (stated_date, timing)
        for distance, stated_date, timing in mentions
        if distance == nearest_distance
    }


def mention_matches_candidate(
    stated_date: date,
    timing: str,
    candidate_session_date: date,
) -> bool:
    if timing in {"PRIOR_TO_OPEN", "UNSPECIFIED"}:
        return stated_date == candidate_session_date
    if timing == "AFTER_CLOSE":
        gap = (candidate_session_date - stated_date).days
        return 1 <= gap <= 4 and candidate_session_date.weekday() < 5
    return False


def classify_occurrence(text: str, ticker_match: re.Match) -> str | None:
    before = text[max(0, ticker_match.start() - 650):ticker_match.start()]
    after = text[ticker_match.end():min(len(text), ticker_match.end() + 650)]
    # 교체 대상 ticker 뒤에는 새 구성 종목의 "will be added" 설명이 다시
    # 등장할 수 있다. 따라서 ticker를 감싼 교체 관계를 먼저 판정한다.
    replacement_start = before.lower().rfind("will replace")
    replacement_tail = (
        before[replacement_start + len("will replace"):]
        if replacement_start >= 0 else ""
    )
    if (
        replacement_start >= 0
        and not ANY_EXCHANGE_TICKER.search(replacement_tail)
        and re.search(r"in (?:the )?S&P 500", after[:220], re.IGNORECASE)
    ):
        return "REMOVE"
    if replacement_start >= 0 and re.search(
        r"respectively\s+in (?:the )?S&P 500", after[:600], re.IGNORECASE
    ):
        return "REMOVE"
    if re.search(
        r"(?:will be added to|will join)\s+(?:the\s+)?S&P 500",
        after[:180],
        re.IGNORECASE,
    ):
        return "ADD"
    if re.search(
        r"which will be removed from (?:the\s+)?S&P 500",
        after[:180],
        re.IGNORECASE,
    ):
        return "REMOVE"
    switching_start = before.lower().rfind("will switch places with")
    if switching_start >= 0 and re.search(
        r"(?:respectively\s+)?in (?:the )?S&P 500", after[:350], re.IGNORECASE
    ):
        return "REMOVE"
    move_start = before.lower().rfind("will move to the s&p 500")
    switching_with_start = before.lower().rfind("switching places with")
    replacing_start = before.lower().rfind("replacing")
    if (
        move_start >= 0
        and max(switching_with_start, replacing_start) > move_start
        and re.search(r"(?:respectively)?", after[:220], re.IGNORECASE)
    ):
        return "REMOVE"
    if re.search(
        r"will replace.{0,260}in (?:the )?S&P 500",
        after[:400],
        re.IGNORECASE,
    ):
        return "ADD"
    if re.search(
        r"will switch places with.{0,500}(?:respectively\s+)?"
        r"in (?:the )?S&P 500",
        after[:600],
        re.IGNORECASE,
    ):
        return "ADD"
    if re.search(
        r"will move to (?:the )?S&P 500", after[:400], re.IGNORECASE
    ):
        return "ADD"
    if re.search(
        r"(?:will be removed from|will leave)\s+(?:the\s+)?S&P 500",
        after[:350],
        re.IGNORECASE,
    ):
        return "REMOVE"
    return None


def verify_candidate(event: dict, release: dict) -> dict:
    ticker = event["ticker"].upper()
    expected_action = event["action"]
    expected_date = date.fromisoformat(event["effective_date"])
    published_date = date.fromisoformat(release["published_date"])
    pattern = re.compile(EXCHANGE_TICKER.format(ticker=re.escape(ticker)), re.IGNORECASE)
    outcomes = []
    for occurrence in pattern.finditer(release["text"]):
        action = classify_occurrence(release["text"], occurrence)
        mentions = qualified_effective_mentions(
            release["text"],
            occurrence.start(),
            occurrence.end(),
            published_date=published_date,
        )
        matching_mentions = {
            mention for mention in mentions
            if mention_matches_candidate(mention[0], mention[1], expected_date)
        }
        if action == expected_action and len(matching_mentions) == 1:
            outcomes.append((occurrence, matching_mentions))
    if len(outcomes) != 1:
        return {
            **event,
            "verification_status": (
                "AMBIGUOUS_PROSE_MATCH" if len(outcomes) > 1 else "PROSE_NOT_CONFIRMED"
            ),
            "source_url": release["source_url"],
            "source_sha256": release["source_sha256"],
        }
    occurrence, mentions = outcomes[0]
    stated_date, timing = next(iter(mentions))
    return {
        **event,
        "announcement_date": release["published_date"],
        "stated_effective_date": stated_date.isoformat(),
        "effective_timing": timing,
        "membership_session_date": event["effective_date"],
        "source_url": release["source_url"],
        "source_sha256": release["source_sha256"],
        "extraction_method": "QUALIFIED_PROSE_V2",
        "verification_status": "SEMANTICS_AND_DATE_VERIFIED",
        "context": release["text"][
            max(0, occurrence.start() - 180):min(len(release["text"]), occurrence.end() + 300)
        ],
    }


def load_release_texts(corpus_dir: Path) -> dict[str, dict]:
    corpus = Path(corpus_dir)
    with (corpus / "release_index.csv").open(encoding="utf-8", newline="") as handle:
        index = list(csv.DictReader(handle))
    releases = {}
    for row in index:
        files = list((corpus / "evidence").glob(f"{row['source_sha256']}.*"))
        if len(files) != 1 or files[0].suffix != ".html":
            continue
        releases[row["source_url"]] = {**row, "text": normalize_text(files[0].read_bytes())}
    return releases


def verify_suggestions(suggestions: list[dict], releases: dict[str, dict]) -> tuple[list[dict], dict]:
    results = []
    seen = set()
    for suggestion in suggestions:
        key = (
            suggestion["effective_date"], suggestion["action"], suggestion["ticker"],
            suggestion["source_url"],
        )
        if key in seen:
            continue
        seen.add(key)
        release = releases.get(suggestion["source_url"])
        if release:
            results.append(verify_candidate(suggestion, release))
    statuses = {}
    for row in results:
        status = row["verification_status"]
        statuses[status] = statuses.get(status, 0) + 1
    return results, {"suggestions": len(seen), "results": len(results), "statuses": statuses}


def canonical_verified_events(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    grouped = {}
    for row in rows:
        if row["verification_status"] != "SEMANTICS_AND_DATE_VERIFIED":
            continue
        key = row["effective_date"], row["action"], row["ticker"]
        grouped.setdefault(key, []).append(row)
    canonical = []
    conflicts = []
    for key, matches in grouped.items():
        semantics = {
            (row["stated_effective_date"], row["effective_timing"])
            for row in matches
        }
        if len(semantics) != 1:
            conflicts.append({
                "effective_date": key[0],
                "action": key[1],
                "ticker": key[2],
                "reason": "CONFLICTING_OFFICIAL_EFFECTIVE_SEMANTICS",
                "source_urls": "|".join(sorted(row["source_url"] for row in matches)),
            })
            continue
        canonical.append(min(
            matches,
            key=lambda row: (row["announcement_date"], row["source_url"]),
        ))
    return sorted(
        canonical,
        key=lambda row: (row["effective_date"], row["action"], row["ticker"]),
    ), conflicts


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_verified(path: Path, rows: list[dict]) -> None:
    verified, conflicts = canonical_verified_events(rows)
    if not verified:
        raise ProseVerificationError("no prose events passed verification")
    if conflicts:
        raise ProseVerificationError(
            f"{len(conflicts)} official events have conflicting effective semantics"
        )
    fields = [
        "announcement_date", "effective_date", "stated_effective_date",
        "effective_timing", "membership_session_date", "action", "ticker",
        "source_url", "source_sha256", "extraction_method", "verification_status",
        "context",
    ]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(verified)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suggestions", type=Path)
    parser.add_argument("corpus_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows, audit = verify_suggestions(
        read_csv(args.suggestions), load_release_texts(args.corpus_dir)
    )
    write_verified(args.output, rows)
    print(audit)


if __name__ == "__main__":
    main()
