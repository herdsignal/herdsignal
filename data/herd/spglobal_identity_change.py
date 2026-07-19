"""S&P 공식 발표에서 구성 연속성을 유지하는 ticker 변경을 분류한다."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

from herd.spglobal_prose_event_verifier import EXCHANGE_TICKER, load_release_texts

NEW_TICKER_PATTERNS = (
    re.compile(r"ticker symbol to\s+([A-Z][A-Z0-9.-]+)", re.IGNORECASE),
    re.compile(r"trade .{0,80}\bunder (?:the )?ticker\s+([A-Z][A-Z0-9.-]+)", re.IGNORECASE),
    re.compile(
        r"(?:name and )?ticker (?:change )?to .{0,100}"
        r"\((?:NYSE|NASD|NASDAQ|AMEX|OTC)\s*:\s*([A-Z][A-Z0-9.-]+)\)",
        re.IGNORECASE,
    ),
)
ANY_TICKER = re.compile(
    r"\((?:NYSE(?:\s+(?:MKT|American))?|NASD|NASDAQ|AMEX|OTC)"
    r"\s*:\s*([A-Z][A-Z0-9.-]+)\)",
    re.IGNORECASE,
)


def _new_tickers(text: str) -> set[str]:
    return {
        match.group(1).upper().rstrip(".")
        for pattern in NEW_TICKER_PATTERNS
        for match in pattern.finditer(text)
    }


def classify_identity_candidate(candidate: dict, release: dict) -> dict:
    ticker = candidate["ticker"].upper()
    occurrences = list(re.finditer(
        EXCHANGE_TICKER.format(ticker=re.escape(ticker)),
        release["text"],
        re.IGNORECASE,
    ))
    base = {
        "candidate_effective_date": candidate["effective_date"],
        "candidate_action": candidate["action"],
        "ticker": ticker,
        "announcement_date": release["published_date"],
        "source_url": release["source_url"],
        "source_sha256": release["source_sha256"],
    }
    for occurrence in occurrences:
        window = release["text"][
            max(0, occurrence.start() - 900):
            min(len(release["text"]), occurrence.end() + 1200)
        ]
        new_tickers = _new_tickers(window)
        if not new_tickers:
            continue
        listed = [value.upper() for value in ANY_TICKER.findall(window)]
        explicitly_remains = bool(re.search(
            r"(?:will\s+)?remain in (?:the\s+)?S&P 500",
            window,
            re.IGNORECASE,
        ))
        constituent_context = bool(re.search(
            r"S&P 500(?:\s*(?:and|&)\s*100)? constituent",
            window[:1000],
            re.IGNORECASE,
        ))
        if ticker in new_tickers:
            old_candidates = [
                value for value in listed if value != ticker
            ]
            old_ticker = old_candidates[-1] if old_candidates else ""
            new_ticker = ticker
        else:
            old_ticker = ticker
            new_ticker = sorted(new_tickers)[0] if len(new_tickers) == 1 else ""
        if not new_ticker or not old_ticker:
            return {
                **base,
                "identity_status": "AMBIGUOUS_TICKER_CHANGE",
                "context": " ".join(window.split()),
            }
        if explicitly_remains:
            status = "OFFICIAL_INDEX_CONTINUITY_TICKER_CHANGE"
        elif constituent_context:
            status = "OFFICIAL_CONSTITUENT_TICKER_CHANGE_REQUIRES_DATE"
        else:
            continue
        return {
            **base,
            "old_ticker": old_ticker,
            "new_ticker": new_ticker,
            "identity_status": status,
            "effective_date_status": "NOT_EXPLICITLY_VERIFIED",
            "context": " ".join(window.split()),
        }
    return {**base, "identity_status": "NO_IDENTITY_CHANGE"}


def classify_suggestions(
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
            rows.append(classify_identity_candidate(candidate, release))
    statuses = Counter(row["identity_status"] for row in rows)
    return rows, {
        "suggestions": len(seen),
        "statuses": dict(sorted(statuses.items())),
        "identity_candidates": sum(
            status != "NO_IDENTITY_CHANGE"
            for status in (row["identity_status"] for row in rows)
        ),
        "date_verified": sum(
            row.get("effective_date_status") == "VERIFIED" for row in rows
        ),
    }


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
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
    rows, audit = classify_suggestions(
        read_csv(args.suggestions), load_release_texts(args.corpus_dir)
    )
    write_csv(args.output, rows)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
