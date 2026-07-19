"""구성 변경 후보와 S&P 공식 보도자료를 연결할 검토 대기열을 만든다."""

from __future__ import annotations

import argparse
import csv
import re
from datetime import date, timedelta
from pathlib import Path

from lxml import html

EXCHANGE_TICKER = r"(?:NYSE|NASD|NASDAQ|AMEX|OTC)\s*:\s*{ticker}\b"


class EvidenceMatcherError(RuntimeError):
    pass


def extract_html_text(path: Path) -> str:
    document = html.fromstring(Path(path).read_bytes())
    return " ".join(document.text_content().split())


def load_release_texts(corpus_dir: Path) -> list[dict]:
    corpus = Path(corpus_dir)
    with (corpus / "release_index.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    releases = []
    for row in rows:
        matches = list((corpus / "evidence").glob(f"{row['source_sha256']}.*"))
        if len(matches) != 1:
            raise EvidenceMatcherError(f"missing evidence: {row['source_sha256']}")
        if matches[0].suffix != ".html":
            # PDF 본문 추출은 별도 검증 경로에서 처리한다.
            continue
        releases.append({**row, "text": extract_html_text(matches[0])})
    return releases


def match_backlog(
    backlog: list[dict],
    releases: list[dict],
    *,
    lookback_days: int = 45,
    forward_days: int = 3,
) -> list[dict]:
    matches = []
    for event in backlog:
        effective = date.fromisoformat(event["effective_date"])
        ticker = event["ticker"].upper()
        pattern = re.compile(EXCHANGE_TICKER.format(ticker=re.escape(ticker)), re.IGNORECASE)
        for release in releases:
            published = date.fromisoformat(release["published_date"])
            if not effective - timedelta(days=lookback_days) <= published <= effective + timedelta(days=forward_days):
                continue
            found = pattern.search(release["text"])
            if not found:
                continue
            start = max(0, found.start() - 120)
            end = min(len(release["text"]), found.end() + 180)
            matches.append(
                {
                    "effective_date": event["effective_date"],
                    "action": event["action"],
                    "ticker": ticker,
                    "published_date": release["published_date"],
                    "source_url": release["source_url"],
                    "source_sha256": release["source_sha256"],
                    "match_basis": "EXCHANGE_TICKER_IN_OFFICIAL_RELEASE",
                    "review_status": "REQUIRES_HUMAN_REVIEW",
                    "context": release["text"][start:end],
                }
            )
    return sorted(matches, key=lambda row: (row["effective_date"], row["action"], row["ticker"]))


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_matches(path: Path, matches: list[dict]) -> None:
    if not matches:
        raise EvidenceMatcherError("no evidence suggestions were found")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(matches[0]))
        writer.writeheader()
        writer.writerows(matches)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backlog", type=Path)
    parser.add_argument("corpus_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    suggestions = match_backlog(read_csv(args.backlog), load_release_texts(args.corpus_dir))
    write_matches(args.output, suggestions)
    print(f"wrote {len(suggestions)} evidence suggestions")


if __name__ == "__main__":
    main()
