"""SEC ticker/CIK와 filing 이력을 point-in-time 증거로 정규화한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
FORMAT_VERSION = "herd-sec-reference-v1"
CORPORATE_ACTION_FORMS = {"25", "25-NSE", "8-K", "8-K/A", "DEFM14A", "S-4", "S-4/A"}


class SecReferenceError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def download_sec_json(url: str, destination: Path, *, user_agent: str) -> None:
    if "@" not in user_agent or len(user_agent) < 10:
        raise SecReferenceError("SEC user agent must identify an application and contact")
    response = requests.get(
        url,
        headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    Path(destination).write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def normalize_ticker_mapping(payload: dict) -> list[dict]:
    expected = ["cik", "name", "ticker", "exchange"]
    if payload.get("fields") != expected or not isinstance(payload.get("data"), list):
        raise SecReferenceError("unexpected SEC ticker mapping schema")
    rows = []
    seen = set()
    for values in payload["data"]:
        row = dict(zip(expected, values, strict=True))
        cik = int(row["cik"])
        ticker = str(row["ticker"]).upper()
        identity = (cik, ticker, row["exchange"])
        if identity in seen:
            raise SecReferenceError(f"duplicate SEC mapping: {identity}")
        seen.add(identity)
        rows.append(
            {
                "cik": f"{cik:010d}",
                "ticker": ticker,
                "company_name": str(row["name"]).strip(),
                "exchange": str(row["exchange"]).strip(),
                "validity": "CURRENT_ASSOCIATION_ONLY",
            }
        )
    return sorted(rows, key=lambda row: (row["ticker"], row["cik"]))


def extract_submission_evidence(payload: dict) -> tuple[list[dict], list[dict]]:
    cik = f"{int(payload['cik']):010d}"
    former_names = [
        {
            "cik": cik,
            "former_name": item["name"],
            "from": item.get("from", ""),
            "to": item.get("to", ""),
        }
        for item in payload.get("formerNames", [])
    ]
    recent = payload.get("filings", {}).get("recent", {})
    required = {"accessionNumber", "filingDate", "acceptanceDateTime", "form", "primaryDocument"}
    if not required.issubset(recent):
        raise SecReferenceError(f"{cik}: incomplete submissions schema")
    length = len(recent["accessionNumber"])
    evidence = []
    for position in range(length):
        form = recent["form"][position]
        if form not in CORPORATE_ACTION_FORMS:
            continue
        evidence.append(
            {
                "cik": cik,
                "company_name": payload.get("name", ""),
                "form": form,
                "filing_date": recent["filingDate"][position],
                "accepted_at": recent["acceptanceDateTime"][position],
                "accession_number": recent["accessionNumber"][position],
                "primary_document": recent["primaryDocument"][position],
                "items": (
                    recent.get("items", [""] * length)[position]
                    if position < len(recent.get("items", []))
                    else ""
                ),
                "evidence_type": (
                    "DELISTING_NOTICE" if form in {"25", "25-NSE"}
                    else "CORPORATE_ACTION_CANDIDATE"
                ),
                "classification_status": "REQUIRES_DOCUMENT_REVIEW",
            }
        )
    return former_names, evidence


def create_mapping_snapshot(
    snapshot_id: str,
    source_json: Path,
    *,
    root: Path,
    created_at: datetime | None = None,
) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,80}", snapshot_id):
        raise SecReferenceError("unsafe snapshot id")
    final = Path(root) / snapshot_id
    if final.exists():
        raise SecReferenceError(f"snapshot already exists: {final}")
    payload = json.loads(Path(source_json).read_text(encoding="utf-8"))
    rows = normalize_ticker_mapping(payload)
    temp = Path(root) / f".{snapshot_id}.tmp-{uuid.uuid4().hex}"
    temp.mkdir(parents=True)
    try:
        mapping = temp / "ticker_cik_current.csv"
        with mapping.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        body = {
            "format_version": FORMAT_VERSION,
            "snapshot_id": snapshot_id,
            "created_at": (created_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
            "source": {
                "url": SEC_TICKERS_URL,
                "sha256": _sha256(source_json),
                "warning": "SEC does not guarantee accuracy or scope; current association only",
            },
            "rows": len(rows),
            "unique_ciks": len({row["cik"] for row in rows}),
            "unique_tickers": len({row["ticker"] for row in rows}),
            "artifact": {
                "path": mapping.name,
                "bytes": mapping.stat().st_size,
                "sha256": _sha256(mapping),
            },
            "point_in_time_ready": False,
        }
        manifest = {**body, "snapshot_sha256": hashlib.sha256(_canonical_json(body)).hexdigest()}
        (temp / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        Path(root).mkdir(parents=True, exist_ok=True)
        temp.rename(final)
        return final
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch-mapping")
    fetch.add_argument("destination", type=Path)
    fetch.add_argument("--user-agent", required=True)
    create = sub.add_parser("create-mapping")
    create.add_argument("snapshot_id")
    create.add_argument("source_json", type=Path)
    create.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "reference" / "sec",
    )
    args = parser.parse_args()
    if args.command == "fetch-mapping":
        download_sec_json(SEC_TICKERS_URL, args.destination, user_agent=args.user_agent)
    else:
        print(create_mapping_snapshot(args.snapshot_id, args.source_json, root=args.root))


if __name__ == "__main__":
    main()
