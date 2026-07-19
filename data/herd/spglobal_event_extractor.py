"""S&P 공식 보도자료 표에서 S&P 500 편입·편출 이벤트를 추출한다."""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from lxml import html

ACTION_MAP = {"addition": "ADD", "deletion": "REMOVE"}
REQUIRED_HEADERS = {"effective date", "index name", "action", "company name", "ticker"}


class OfficialEventExtractionError(RuntimeError):
    pass


def normalize_cell(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split()).strip()


def parse_effective_date(value: str) -> str:
    normalized = re.sub(r"\bSept(?:\.|\b)", "Sep", normalize_cell(value)).replace(".", "")
    normalized = re.sub(r"([A-Za-z])(\d)", r"\1 \2", normalized)
    normalized = re.sub(r",\s*", ", ", normalized)
    for pattern in (
        "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y", "%d-%b-%y",
    ):
        try:
            return datetime.strptime(normalized, pattern).date().isoformat()
        except ValueError:
            continue
    raise OfficialEventExtractionError(f"unsupported effective date: {value}")


def extract_table_events(
    content: bytes,
    *,
    announcement_date: str,
    source_url: str,
    source_sha256: str,
) -> tuple[list[dict], list[dict]]:
    document = html.fromstring(content)
    events = []
    unresolved = []
    for table in document.xpath("//table"):
        rows = table.xpath(".//tr")
        if not rows:
            continue
        header = [normalize_cell(cell.text_content()).lower() for cell in rows[0].xpath("./th|./td")]
        if not REQUIRED_HEADERS.issubset(header):
            continue
        positions = {name: header.index(name) for name in REQUIRED_HEADERS}
        inherited_effective_date = ""
        for row in rows[1:]:
            cells = [normalize_cell(cell.text_content()) for cell in row.xpath("./th|./td")]
            if len(cells) <= max(positions.values()):
                continue
            date_cell = cells[positions["effective date"]]
            if date_cell.lower() == "effective date":
                continue
            if date_cell:
                if date_cell.upper() == "TBA":
                    unresolved.append({
                        "announcement_date": announcement_date,
                        "ticker": cells[positions["ticker"]].upper().strip(),
                        "reason": "EFFECTIVE_DATE_TBA",
                        "source_url": source_url,
                        "source_sha256": source_sha256,
                    })
                    inherited_effective_date = ""
                    continue
                inherited_effective_date = parse_effective_date(date_cell)
            if not inherited_effective_date:
                raise OfficialEventExtractionError("table row cannot inherit an effective date")
            if cells[positions["index name"]].upper().replace("®", "") != "S&P 500":
                continue
            action_text = cells[positions["action"]].lower()
            if action_text not in ACTION_MAP:
                raise OfficialEventExtractionError(f"unsupported action: {action_text}")
            ticker = cells[positions["ticker"]].upper().strip()
            if not ticker:
                raise OfficialEventExtractionError("empty ticker in official table")
            events.append(
                {
                    "announcement_date": announcement_date,
                    "effective_date": inherited_effective_date,
                    "action": ACTION_MAP[action_text],
                    "ticker": ticker,
                    "company_name": cells[positions["company name"]],
                    "source_url": source_url,
                    "source_sha256": source_sha256,
                    "extraction_method": "OFFICIAL_TABLE_V1",
                    "review_status": "STRUCTURE_VERIFIED",
                }
            )
    return events, unresolved


def extract_corpus(corpus_dir: Path) -> tuple[list[dict], dict]:
    corpus = Path(corpus_dir)
    with (corpus / "release_index.csv").open(encoding="utf-8", newline="") as handle:
        releases = list(csv.DictReader(handle))
    events = []
    unresolved = []
    table_documents = 0
    for release in releases:
        evidence = list((corpus / "evidence").glob(f"{release['source_sha256']}.*"))
        if len(evidence) != 1:
            raise OfficialEventExtractionError(f"missing evidence: {release['source_sha256']}")
        if evidence[0].suffix != ".html":
            continue
        extracted, unresolved_rows = extract_table_events(
            evidence[0].read_bytes(),
            announcement_date=release["published_date"],
            source_url=release["source_url"],
            source_sha256=release["source_sha256"],
        )
        if extracted:
            table_documents += 1
            events.extend(extracted)
        unresolved.extend(unresolved_rows)
    identities = Counter(
        (row["effective_date"], row["action"], row["ticker"]) for row in events
    )
    # 동일 이벤트가 후속 보도자료에 반복되면 최초의 확정 발표를 원장에 남긴다.
    canonical = {}
    for row in sorted(events, key=lambda item: item["announcement_date"]):
        canonical.setdefault(
            (row["effective_date"], row["action"], row["ticker"]), row
        )
    resolved_tickers = {row["ticker"] for row in canonical.values()}
    remaining_unresolved = [
        row for row in unresolved if row["ticker"] not in resolved_tickers
    ]
    return list(canonical.values()), {
        "release_documents": len(releases),
        "table_documents": table_documents,
        "event_rows": len(events),
        "unique_events": len(identities),
        "corroborated_event_keys": sum(count > 1 for count in identities.values()),
        "unresolved_rows": len(unresolved),
        "remaining_unresolved_rows": len(remaining_unresolved),
        "ready_for_ledger": (
            bool(events)
            and not remaining_unresolved
        ),
    }


def write_events(path: Path, events: list[dict]) -> None:
    if not events:
        raise OfficialEventExtractionError("no official table events found")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(events[0]))
        writer.writeheader()
        writer.writerows(sorted(
            events, key=lambda row: (row["effective_date"], row["action"], row["ticker"])
        ))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    events, audit = extract_corpus(args.corpus_dir)
    write_events(args.output, events)
    print(audit)


if __name__ == "__main__":
    main()
