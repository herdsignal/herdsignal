"""공식 S&P 문서에서 후보 날짜·행동과 독립적으로 사건 의미를 추출한다."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

from herd.constituent_event_contract import xnys_membership_session_date
from herd.spglobal_prose_event_verifier import (
    EXCHANGE_TICKER,
    classify_occurrence,
    load_release_texts,
    qualified_effective_mentions,
    shared_replacement_removal_mentions,
)


class CandidateSemanticsError(RuntimeError):
    pass


def extract_candidate_semantics(candidate: dict, release: dict) -> dict:
    ticker = candidate["ticker"].upper()
    pattern = re.compile(EXCHANGE_TICKER.format(ticker=re.escape(ticker)), re.IGNORECASE)
    outcomes = []
    for occurrence in pattern.finditer(release["text"]):
        action = classify_occurrence(release["text"], occurrence)
        mentions = qualified_effective_mentions(
            release["text"],
            occurrence.start(),
            occurrence.end(),
            published_date=date.fromisoformat(release["published_date"]),
        )
        if action == "REMOVE":
            shared_mentions = shared_replacement_removal_mentions(
                release["text"],
                occurrence.end(),
                published_date=date.fromisoformat(release["published_date"]),
            )
            if shared_mentions:
                mentions = shared_mentions
        if action and len(mentions) == 1:
            stated_date, timing = next(iter(mentions))
            outcomes.append((occurrence, action, stated_date, timing))
    semantics = {
        (action, stated_date, timing)
        for _, action, stated_date, timing in outcomes
    }
    base = {
        "candidate_effective_date": candidate["effective_date"],
        "candidate_action": candidate["action"],
        "ticker": ticker,
        "announcement_date": release["published_date"],
        "source_url": release["source_url"],
        "source_sha256": release["source_sha256"],
    }
    if not outcomes:
        return {**base, "extraction_status": "NO_MEMBERSHIP_SEMANTICS"}
    if len(semantics) != 1:
        return {**base, "extraction_status": "AMBIGUOUS_MEMBERSHIP_SEMANTICS"}
    action, stated_date, timing = next(iter(semantics))
    membership_date = xnys_membership_session_date(stated_date.isoformat(), timing)
    candidate_matches = (
        action == candidate["action"]
        and membership_date == candidate["effective_date"]
    )
    occurrence = outcomes[0][0]
    return {
        **base,
        "official_action": action,
        "stated_effective_date": stated_date.isoformat(),
        "effective_timing": timing,
        "membership_session_date": membership_date or "",
        "extraction_status": (
            "OFFICIAL_SEMANTICS_MATCH_CANDIDATE"
            if candidate_matches
            else "OFFICIAL_SEMANTICS_CONFLICTS_WITH_CANDIDATE"
        ),
        "context": release["text"][
            max(0, occurrence.start() - 220):
            min(len(release["text"]), occurrence.end() + 420)
        ],
    }


def extract_suggestions(
    suggestions: list[dict],
    releases: dict[str, dict],
) -> tuple[list[dict], dict]:
    rows = []
    seen = set()
    for candidate in suggestions:
        key = (
            candidate["effective_date"],
            candidate["action"],
            candidate["ticker"],
            candidate["source_url"],
        )
        if key in seen:
            continue
        seen.add(key)
        release = releases.get(candidate["source_url"])
        if release:
            rows.append(extract_candidate_semantics(candidate, release))
    statuses = Counter(row["extraction_status"] for row in rows)
    return rows, {
        "suggestions": len(seen),
        "results": len(rows),
        "statuses": dict(sorted(statuses.items())),
        "candidate_matches": statuses["OFFICIAL_SEMANTICS_MATCH_CANDIDATE"],
        "candidate_conflicts": statuses["OFFICIAL_SEMANTICS_CONFLICTS_WITH_CANDIDATE"],
    }


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise CandidateSemanticsError("no candidate semantics")
    fields = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suggestions", type=Path)
    parser.add_argument("corpus_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows, audit = extract_suggestions(
        read_csv(args.suggestions),
        load_release_texts(args.corpus_dir),
    )
    write_csv(args.output, rows)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
