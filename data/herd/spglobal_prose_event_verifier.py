"""S&P 보도자료 서술문에서 후보 이벤트의 행동과 적용일을 보수적으로 검증한다."""

from __future__ import annotations

import argparse
import csv
import re
from datetime import date, datetime
from pathlib import Path

from lxml import html

EXCHANGE_TICKER = r"\((?:NYSE|NASD|NASDAQ|AMEX|OTC)\s*:\s*{ticker}\b[^)]*\)"
DATE_PATTERN = re.compile(
    r"(?:January|February|March|April|May|June|July|August|September|Sept\.?|"
    r"October|November|December|Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|"
    r"Aug\.?|Sep\.?|Oct\.?|Nov\.?|Dec\.?)\s+\d{1,2},?\s+\d{4}",
    re.IGNORECASE,
)
QUALIFIER_PATTERN = re.compile(
    r"(?:effective|prior to (?:the )?open(?:ing)?|before (?:the )?market opens|"
    r"after (?:the )?close(?: of trading)?)",
    re.IGNORECASE,
)


class ProseVerificationError(RuntimeError):
    pass


def normalize_text(content: bytes) -> str:
    document = html.fromstring(content)
    return " ".join(document.text_content().replace("\xa0", " ").split())


def parse_date_mention(value: str) -> date:
    normalized = re.sub(r"\bSept(?:\.|\b)", "Sep", value).replace(".", "")
    normalized = re.sub(r",\s*", ", ", normalized)
    for pattern in ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(normalized, pattern).date()
        except ValueError:
            continue
    raise ProseVerificationError(f"unsupported date mention: {value}")


def qualified_dates(text: str, start: int, end: int) -> set[date]:
    window_start = max(0, start - 500)
    window_end = min(len(text), end + 500)
    window = text[window_start:window_end]
    dates = set()
    for match in DATE_PATTERN.finditer(window):
        qualifier_start = max(0, match.start() - 100)
        qualifier_end = min(len(window), match.end() + 30)
        if QUALIFIER_PATTERN.search(window[qualifier_start:qualifier_end]):
            dates.add(parse_date_mention(match.group()))
    return dates


def classify_occurrence(text: str, ticker_match: re.Match) -> str | None:
    before = text[max(0, ticker_match.start() - 450):ticker_match.start()]
    after = text[ticker_match.end():min(len(text), ticker_match.end() + 450)]
    if re.search(
        r"(?:will be added to|will join)\s+(?:the\s+)?S&P 500", after, re.IGNORECASE
    ):
        return "ADD"
    if re.search(
        r"will replace.{0,260}in (?:the )?S&P 500", after, re.IGNORECASE
    ):
        return "ADD"
    if re.search(
        r"(?:will be removed from|will leave)\s+(?:the\s+)?S&P 500",
        after,
        re.IGNORECASE,
    ):
        return "REMOVE"
    replacement_start = before.lower().rfind("will replace")
    if replacement_start >= 0 and re.search(
        r"in (?:the )?S&P 500", after[:250], re.IGNORECASE
    ):
        return "REMOVE"
    return None


def verify_candidate(event: dict, release: dict) -> dict:
    ticker = event["ticker"].upper()
    expected_action = event["action"]
    expected_date = date.fromisoformat(event["effective_date"])
    pattern = re.compile(EXCHANGE_TICKER.format(ticker=re.escape(ticker)), re.IGNORECASE)
    outcomes = []
    for occurrence in pattern.finditer(release["text"]):
        action = classify_occurrence(release["text"], occurrence)
        dates = qualified_dates(release["text"], occurrence.start(), occurrence.end())
        if action == expected_action and expected_date in dates:
            outcomes.append((occurrence, dates))
    if len(outcomes) != 1:
        return {
            **event,
            "verification_status": (
                "AMBIGUOUS_PROSE_MATCH" if len(outcomes) > 1 else "PROSE_NOT_CONFIRMED"
            ),
            "source_url": release["source_url"],
            "source_sha256": release["source_sha256"],
        }
    occurrence, _ = outcomes[0]
    return {
        **event,
        "announcement_date": release["published_date"],
        "source_url": release["source_url"],
        "source_sha256": release["source_sha256"],
        "extraction_method": "QUALIFIED_PROSE_V1",
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


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_verified(path: Path, rows: list[dict]) -> None:
    verified = [
        row for row in rows if row["verification_status"] == "SEMANTICS_AND_DATE_VERIFIED"
    ]
    if not verified:
        raise ProseVerificationError("no prose events passed verification")
    fields = [
        "announcement_date", "effective_date", "action", "ticker", "source_url",
        "source_sha256", "extraction_method", "verification_status", "context",
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
