"""Verify disputed former-constituent ticker/CIK identities from SEC cover pages."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from herd.sec_master_index import resolve_user_agent
from herd.sec_targeted_cover_corpus_v2 import extract_tagged_trading_symbols, submission_rows


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")
SNAPSHOT_ROOT = ROOT / "data/reference/sec/former-constituent-identity-v1-20260803"
OUTPUT = ROOT / "data/reports/former_constituent_sec_identity_corrections_v1.csv"
REPORT = ROOT / "data/reports/former_constituent_sec_identity_corrections_v1.json"


class FormerConstituentIdentityError(RuntimeError):
    """Raised when SEC identity evidence is incomplete or mutable."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_protocol(path: Path = PROTOCOL, *, require_mapping: bool = False) -> dict[str, Any]:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if (
        protocol.get("protocol_version") != "FORMER_CONSTITUENT_SEC_IDENTITY_CORRECTIONS_V1"
        or protocol.get("status") != "LOCKED_BEFORE_SEC_PRIMARY_COLLECTION"
        or protocol.get("operational_action_ratio") != 0.0
    ):
        raise FormerConstituentIdentityError("identity protocol is not locked")
    for key in ("candidate_input",):
        source = ROOT / protocol[key]["path"]
        if not source.is_file() or sha256(source) != protocol[key]["sha256"]:
            raise FormerConstituentIdentityError(f"locked input changed: {key}")
    mapping = ROOT / protocol["current_sec_mapping"]["path"]
    if require_mapping and (not mapping.is_file() or sha256(mapping) != protocol["current_sec_mapping"]["sha256"]):
        raise FormerConstituentIdentityError("local SEC discovery mapping is missing or changed")
    return protocol


def discover_disagreements(protocol: dict[str, Any]) -> pd.DataFrame:
    candidates = pd.read_csv(ROOT / protocol["candidate_input"]["path"], dtype={"cik": str})
    mapping = pd.read_csv(ROOT / protocol["current_sec_mapping"]["path"], dtype={"cik": str})
    mapping["ticker"] = mapping["ticker"].astype(str).str.upper()
    if mapping["ticker"].duplicated().any():
        raise FormerConstituentIdentityError("current SEC mapping contains duplicate tickers")
    current = mapping.set_index("ticker")["cik"].astype(str).str.zfill(10)
    candidates["candidate_cik"] = candidates["cik"].astype(str).str.zfill(10)
    candidates["current_sec_cik"] = candidates["ticker"].map(current)
    disagreements = candidates[
        candidates["current_sec_cik"].notna()
        & candidates["candidate_cik"].ne(candidates["current_sec_cik"])
    ].copy()
    return disagreements[["ticker", "candidate_cik", "current_sec_cik", "verified_removal_date"]]


def _request(session: requests.Session, url: str) -> bytes:
    response = session.get(url, timeout=90)
    response.raise_for_status()
    time.sleep(0.12)
    return response.content


def _filings_around(payload: dict, event_date: date, forms: set[str], window_days: int) -> list[dict]:
    rows = submission_rows(payload)
    eligible = [
        row for row in rows
        if row["form"] in forms
        and abs((date.fromisoformat(row["filing_date"]) - event_date).days) <= window_days
    ]
    before = sorted(
        (row for row in eligible if row["filing_date"] <= event_date.isoformat()),
        key=lambda row: row["filing_date"], reverse=True,
    )[:2]
    after = sorted(
        (row for row in eligible if row["filing_date"] > event_date.isoformat()),
        key=lambda row: row["filing_date"],
    )[:2]
    return sorted(before + after, key=lambda row: row["filing_date"])


def collect(
    *,
    snapshot_root: Path = SNAPSHOT_ROOT,
    output: Path = OUTPUT,
    report_path: Path = REPORT,
    env_file: Path = ROOT / ".env",
) -> dict[str, Any]:
    protocol = load_protocol(require_mapping=True)
    if snapshot_root.exists():
        raise FormerConstituentIdentityError("immutable identity snapshot already exists")
    disagreements = discover_disagreements(protocol)
    if disagreements.empty:
        raise FormerConstituentIdentityError("no ticker/CIK disagreement to verify")
    raw = snapshot_root / "raw"
    raw.mkdir(parents=True)
    session = requests.Session()
    session.headers.update({"User-Agent": resolve_user_agent(env_file), "Accept-Encoding": "gzip, deflate"})
    forms = set(protocol["verification"]["eligible_forms"])
    window_days = int(protocol["verification"]["window_days"])
    artifacts: list[dict[str, Any]] = []
    corrections: list[dict[str, Any]] = []

    for row in disagreements.itertuples(index=False):
        cik = str(row.current_sec_cik).zfill(10)
        submissions_url = protocol["official_sources"]["submissions"].format(cik=cik)
        submissions_content = _request(session, submissions_url)
        submissions_path = raw / f"CIK{cik}.json"
        submissions_path.write_bytes(submissions_content)
        payload = json.loads(submissions_content)
        event_date = date.fromisoformat(row.verified_removal_date)
        filings = _filings_around(payload, event_date, forms, window_days)
        evidence = []
        for filing in filings:
            accession = filing["accession_number"].replace("-", "")
            url = protocol["official_sources"]["primary_document"].format(
                cik=int(cik), accession=accession, document=filing["primary_document"]
            )
            content = _request(session, url)
            digest = hashlib.sha256(content).hexdigest()
            document = raw / f"{digest}.html"
            document.write_bytes(content)
            symbols = extract_tagged_trading_symbols(content)
            evidence.append({**filing, "symbols": symbols, "source_url": url, "source_sha256": digest})
            artifacts.append({"path": document.relative_to(snapshot_root).as_posix(), "sha256": digest, "url": url})
        before = [item for item in evidence if item["filing_date"] <= row.verified_removal_date and row.ticker in item["symbols"]]
        after = [item for item in evidence if item["filing_date"] > row.verified_removal_date and row.ticker in item["symbols"]]
        if not before or not after:
            raise FormerConstituentIdentityError(f"SEC tagged-symbol continuity incomplete for {row.ticker}")
        corrections.append({
            "ticker": row.ticker,
            "event_candidate_cik": str(row.candidate_cik).zfill(10),
            "verified_cik": cik,
            "verified_removal_date": row.verified_removal_date,
            "before_accession": before[0]["accession_number"],
            "before_filing_date": before[0]["filing_date"],
            "after_accession": after[0]["accession_number"],
            "after_filing_date": after[0]["filing_date"],
            "identity_basis": "SEC_PRIMARY_COVER_TAGGED_SYMBOL_CONTINUITY",
        })
        artifacts.append({"path": submissions_path.relative_to(snapshot_root).as_posix(), "sha256": sha256(submissions_path), "url": submissions_url})

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(corrections[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(corrections, key=lambda item: item["ticker"]))
    manifest = {
        "format_version": "FORMER_CONSTITUENT_SEC_IDENTITY_SNAPSHOT_V1",
        "protocol_sha256": sha256(PROTOCOL),
        "artifacts": sorted(artifacts, key=lambda item: item["path"]),
    }
    (snapshot_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    report = {
        "report_version": "FORMER_CONSTITUENT_SEC_IDENTITY_CORRECTIONS_V1",
        "status": "SEC_PRIMARY_IDENTITY_CORRECTIONS_READY",
        "disagreements": len(disagreements),
        "verified_corrections": len(corrections),
        "tickers": sorted(item["ticker"] for item in corrections),
        "corrections_path": str(output.relative_to(ROOT)),
        "corrections_sha256": sha256(output),
        "snapshot_manifest_sha256": sha256(snapshot_root / "manifest.json"),
        "future_price_outcomes_read": False,
        "future_earnings_outcomes_read": False,
        "operational_action_ratio": 0.0,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def verify(output: Path = OUTPUT, report_path: Path = REPORT) -> dict[str, Any]:
    load_protocol(require_mapping=False)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows = pd.read_csv(output, dtype={"event_candidate_cik": str, "verified_cik": str})
    if sha256(output) != report["corrections_sha256"] or len(rows) != report["verified_corrections"]:
        raise FormerConstituentIdentityError("published identity corrections changed")
    if rows["ticker"].duplicated().any() or rows["verified_cik"].duplicated().any():
        raise FormerConstituentIdentityError("ambiguous identity correction")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "verify"))
    args = parser.parse_args()
    print(json.dumps(collect() if args.command == "collect" else verify(), ensure_ascii=False, indent=2))
