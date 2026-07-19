"""동일 CIK의 사건 전후 SEC 표지에서 ticker 연속성 증거를 고정한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from lxml import html

from herd.spglobal_prose_event_verifier import DATE_PATTERN, parse_date_mention

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SUBMISSION_FILE_URL = "https://data.sec.gov/submissions/{name}"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
FORMS = {
    "10-K", "10-K/A", "10-Q", "10-Q/A", "8-K", "8-K/A",
    "424B3",
}
PERIODIC_FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A"}


class SecTradingSymbolError(RuntimeError):
    pass


def filing_rows(payload: dict) -> list[dict]:
    recent = payload.get("filings", {}).get("recent", payload)
    required = ("accessionNumber", "filingDate", "form", "primaryDocument")
    if not all(field in recent for field in required):
        raise SecTradingSymbolError("incomplete SEC submissions schema")
    return [
        {
            "accession_number": recent["accessionNumber"][i],
            "filing_date": recent["filingDate"][i],
            "form": recent["form"][i],
            "primary_document": recent["primaryDocument"][i],
        }
        for i in range(len(recent["accessionNumber"]))
    ]


def select_surrounding_filings(
    rows: list[dict],
    event_date: date,
    *,
    window_days: int = 240,
    filings_per_side: int = 8,
) -> list[dict]:
    eligible = [
        row for row in rows
        if row["form"] in FORMS
        and abs((date.fromisoformat(row["filing_date"]) - event_date).days)
        <= window_days
    ]
    before = sorted(
        (row for row in eligible if row["filing_date"] <= event_date.isoformat()),
        key=lambda row: row["filing_date"],
        reverse=True,
    )
    after = sorted(
        (row for row in eligible if row["filing_date"] > event_date.isoformat()),
        key=lambda row: row["filing_date"],
    )[:filings_per_side]
    periodic_before = [
        row for row in before if row["form"] in PERIODIC_FORMS
    ][:3]
    periodic_after = [
        row for row in eligible
        if row["filing_date"] > event_date.isoformat()
        and row["form"] in PERIODIC_FORMS
    ]
    periodic_after.sort(key=lambda row: row["filing_date"])
    return sorted(
        {
            row["accession_number"]: row
            for row in (
                before[:filings_per_side]
                + after
                + periodic_before
                + periodic_after[:3]
            )
        }.values(),
        key=lambda row: row["filing_date"],
    )


def extract_trading_symbols(content: bytes) -> list[str]:
    symbols = set()
    try:
        document = html.fromstring(content)
        for element in document.xpath("//*[@name]"):
            if str(element.get("name", "")).lower().endswith("tradingsymbol"):
                value = " ".join(element.text_content().split()).upper()
                if re.fullmatch(r"[A-Z0-9.-]{1,15}", value):
                    symbols.add(value)
    except (ValueError, html.etree.ParserError):
        pass
    text = " ".join(content.decode("utf-8", errors="ignore").split())
    for match in re.finditer(
        r"Trading\s+Symbol(?:\(s\))?.{0,180}?([A-Z][A-Z0-9.-]{0,14})"
        r"(?:\s|<|&)",
        text,
        re.IGNORECASE,
    ):
        candidate = match.group(1).upper()
        if candidate not in {"THE", "AND", "NONE", "N/A"}:
            symbols.add(candidate)
    return sorted(symbols)


def extract_symbol_change_dates(content: bytes, new_ticker: str) -> list[str]:
    try:
        text = " ".join(html.fromstring(content).text_content().split())
    except (ValueError, html.etree.ParserError):
        text = " ".join(content.decode("utf-8", errors="ignore").split())
    dates = set()
    for ticker_match in re.finditer(
        rf"\b{re.escape(new_ticker)}\b", text, re.IGNORECASE
    ):
        context = text[
            max(0, ticker_match.start() - 420):
            min(len(text), ticker_match.end() + 420)
        ]
        local_ticker_start = ticker_match.start() - max(0, ticker_match.start() - 420)
        ticker_anchor = context[
            max(0, local_ticker_start - 100):local_ticker_start + 100
        ]
        if not re.search(
            r"(?:ticker|trading symbol|trade under|trading under|under the symbol)",
            ticker_anchor,
            re.IGNORECASE,
        ):
            continue
        if not re.search(
            r"(?:new ticker symbol|begin trading|began trading|"
            r"commence[ds]? trading|trading under|ticker symbol change|"
            r"(?:ticker|trading symbol).{0,40}(?:change|changed)|"
            r"(?:change|changed|changing).{0,40}(?:ticker|trading symbol))",
            context,
            re.IGNORECASE,
        ):
            continue
        candidates = []
        for match in DATE_PATTERN.finditer(context):
            if not re.search(r"\b\d{4}\b", match.group()):
                continue
            try:
                parsed = parse_date_mention(match.group()).isoformat()
            except Exception:
                continue
            distance = min(
                abs(match.start() - local_ticker_start),
                abs(match.end() - local_ticker_start),
            )
            candidates.append((distance, parsed))
        if candidates:
            nearest = min(distance for distance, _ in candidates)
            dates.update(value for distance, value in candidates if distance == nearest)
    return sorted(dates)


def classify_pair(pair: dict, filings: list[dict]) -> dict:
    event_date = date.fromisoformat(pair["new_candidate_date"])
    old_ticker = pair["old_ticker"].upper()
    new_ticker = pair["new_ticker"].upper()
    old_before = any(
        row["filing_date"] <= event_date.isoformat()
        and old_ticker in row["trading_symbols"]
        for row in filings
    )
    new_after = any(
        row["filing_date"] >= event_date.isoformat()
        and new_ticker in row["trading_symbols"]
        for row in filings
    )
    raw_effective_dates = {
        value for row in filings for value in row.get("symbol_change_dates", [])
    }
    nearby_dates = {
        value for value in raw_effective_dates
        if abs((date.fromisoformat(value) - event_date).days) <= 14
    }
    resolved_date = ""
    if event_date.isoformat() in nearby_dates:
        resolved_date = event_date.isoformat()
    elif nearby_dates:
        distances = {
            value: abs((date.fromisoformat(value) - event_date).days)
            for value in nearby_dates
        }
        nearest = min(distances.values())
        nearest_dates = [value for value, distance in distances.items() if distance == nearest]
        if len(nearest_dates) == 1:
            resolved_date = nearest_dates[0]
    if old_ticker == new_ticker:
        status = "SELF_CANCELING_SOURCE_ANOMALY"
    elif old_before and new_after and resolved_date:
        status = "SEC_IDENTITY_AND_EFFECTIVE_DATE_VERIFIED"
    elif old_before and new_after:
        status = "SEC_SAME_CIK_IDENTITY_DATE_UNVERIFIED"
    else:
        status = "SEC_TRADING_SYMBOL_EVIDENCE_INCOMPLETE"
    return {
        **pair,
        "old_symbol_seen_before": old_before,
        "new_symbol_seen_after": new_after,
        "resolved_effective_date": (
            resolved_date
        ),
        "effective_date_candidates": "|".join(sorted(raw_effective_dates)),
        "identity_status": status,
        "evidence_accessions": "|".join(
            row["accession_number"] for row in filings
            if old_ticker in row["trading_symbols"]
            or new_ticker in row["trading_symbols"]
        ),
    }


def collect_evidence(
    pairs: list[dict],
    output_dir: Path,
    *,
    user_agent: str,
    delay_seconds: float = 0.12,
) -> dict:
    if "@" not in user_agent:
        raise SecTradingSymbolError("descriptive SEC user agent is required")
    destination = Path(output_dir)
    if destination.exists():
        raise SecTradingSymbolError("output directory already exists")
    raw = destination / "raw"
    raw.mkdir(parents=True)
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
    cache: dict[tuple[str, str], list[dict]] = {}
    artifacts = []
    results = []

    def fetch(url: str) -> bytes:
        response = session.get(url, timeout=90)
        response.raise_for_status()
        time.sleep(delay_seconds)
        return response.content

    for pair in pairs:
        cik = pair.get("candidate_cik", "")
        if not cik:
            continue
        key = (f"{int(cik):010d}", pair["new_candidate_date"])
        if key not in cache:
            cik10, event = key
            submissions_content = fetch(SUBMISSIONS_URL.format(cik=cik10))
            submissions = json.loads(submissions_content)
            rows = filing_rows(submissions)
            # 최근 목록이 사건까지 도달하지 않으면 공식 과거 조각을 병합한다.
            for item in submissions.get("filings", {}).get("files", []):
                if item["filingFrom"] <= event <= item["filingTo"]:
                    rows.extend(filing_rows(json.loads(fetch(
                        SUBMISSION_FILE_URL.format(name=item["name"])
                    ))))
            selected = select_surrounding_filings(rows, date.fromisoformat(event))
            evidence_rows = []
            for filing in selected:
                accession = filing["accession_number"].replace("-", "")
                url = ARCHIVE_URL.format(
                    cik=int(cik10), accession=accession,
                    document=filing["primary_document"],
                )
                content = fetch(url)
                digest = hashlib.sha256(content).hexdigest()
                path = raw / f"{digest}.html"
                path.write_bytes(content)
                artifacts.append({
                    "url": url, "path": f"raw/{path.name}",
                    "sha256": digest, "bytes": len(content),
                })
                evidence_rows.append({
                    **filing,
                    "trading_symbols": extract_trading_symbols(content),
                    "symbol_change_dates": extract_symbol_change_dates(
                        content, pair["new_ticker"].upper()
                    ),
                    "source_url": url,
                    "source_sha256": digest,
                })
            cache[key] = evidence_rows
        results.append(classify_pair(pair, cache[key]))

    evidence_path = destination / "identity_evidence.csv"
    if not results:
        raise SecTradingSymbolError("no SEC identity evidence results")
    with evidence_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    manifest = {
        "format_version": "herd-sec-trading-symbol-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pair_candidates": len(results),
        "verified_identity_changes": sum(
            row["identity_status"] == "SEC_IDENTITY_AND_EFFECTIVE_DATE_VERIFIED"
            for row in results
        ),
        "documents": len(artifacts),
        "bytes": sum(row["bytes"] for row in artifacts),
        "artifacts": artifacts,
        "identity_evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pairs", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--user-agent", required=True)
    args = parser.parse_args()
    print(json.dumps(
        collect_evidence(
            read_csv(args.pairs), args.output_dir, user_agent=args.user_agent
        ),
        ensure_ascii=False, indent=2,
    ))


if __name__ == "__main__":
    main()
