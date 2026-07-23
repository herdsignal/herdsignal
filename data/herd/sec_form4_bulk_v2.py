"""SEC 공식 분기별 내부자 거래 자료를 해시 고정 Form 4 연구 census로 만든다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import time
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import requests

from herd.sec_form4_atomic_v1 import CLASS_BY_CODE, GROUP_BY_CODE
from herd.sec_master_index import resolve_user_agent


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_name("sec_form4_research_census_v2.json")
REQUIRED_TABLES = {
    "SUBMISSION.tsv",
    "REPORTINGOWNER.tsv",
    "NONDERIV_TRANS.tsv",
    "DERIV_TRANS.tsv",
    "FOOTNOTES.tsv",
}
BASE_URLS = (
    "https://www.sec.gov/files/datastandardsinnovation/data/"
    "insider-transactions-data-sets",
    "https://www.sec.gov/files/structureddata/data/"
    "insider-transactions-data-sets",
)
TRANSACTION_TABLES = {
    "NONDERIV_TRANS.tsv": ("NONDERIV_TRANS_SK", False),
    "DERIV_TRANS.tsv": ("DERIV_TRANS_SK", True),
}
FOOTNOTE_COLUMNS = {
    "SECURITY_TITLE_FN",
    "TRANS_DATE_FN",
    "DEEMED_EXECUTION_DATE_FN",
    "EQUITY_SWAP_TRANS_CD_FN",
    "TRANS_TIMELINESS_FN",
    "TRANS_SHARES_FN",
    "TRANS_PRICEPERSHARE_FN",
    "TRANS_ACQUIRED_DISP_CD_FN",
    "SHRS_OWND_FOLWNG_TRANS_FN",
    "VALU_OWND_FOLWNG_TRANS_FN",
    "DIRECT_INDIRECT_OWNERSHIP_FN",
    "NATURE_OF_OWNERSHIP_FN",
}


class Form4BulkError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_protocol(path: Path = PROTOCOL) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_BULK_DOWNLOAD":
        raise Form4BulkError("census protocol must be locked before download")
    firewall = protocol.get("research_firewall", {})
    forbidden = set(firewall.get("forbidden", []))
    required = {
        "TREAT_ALL_SALES_AS_BEARISH",
        "USE_SAME_DAY_PRICE_EXECUTION",
        "OPEN_BLIND_HOLDOUT",
        "ENABLE_BUY_OR_PROFIT_TAKE_RECOMMENDATIONS",
    }
    if required - forbidden or firewall.get("operational_action_authority") is not False:
        raise Form4BulkError("Form 4 census authority firewall is incomplete")
    return protocol


def parse_quarter(value: str) -> tuple[int, int]:
    matched = re.fullmatch(r"(20\d{2})Q([1-4])", str(value).upper())
    if not matched:
        raise Form4BulkError(f"invalid quarter: {value}")
    return int(matched.group(1)), int(matched.group(2))


def quarters(start: str, end: str) -> list[str]:
    start_year, start_quarter = parse_quarter(start)
    end_year, end_quarter = parse_quarter(end)
    if (start_year, start_quarter) > (end_year, end_quarter):
        raise Form4BulkError("start quarter must not follow end quarter")
    result = []
    year, quarter = start_year, start_quarter
    while (year, quarter) <= (end_year, end_quarter):
        result.append(f"{year}Q{quarter}")
        quarter += 1
        if quarter == 5:
            year, quarter = year + 1, 1
    return result


def source_urls(quarter: str) -> list[str]:
    year, number = parse_quarter(quarter)
    filename = f"{year}q{number}_form345.zip"
    return [f"{base}/{filename}" for base in BASE_URLS]


def _validate_zip(path: Path) -> None:
    if not zipfile.is_zipfile(path):
        raise Form4BulkError(f"not a ZIP archive: {path}")
    with zipfile.ZipFile(path) as archive:
        missing = REQUIRED_TABLES - set(archive.namelist())
        if missing:
            raise Form4BulkError(f"bulk ZIP missing tables: {sorted(missing)}")


def download(
    output_root: Path,
    snapshot_id: str,
    *,
    protocol_path: Path = PROTOCOL,
    user_agent: str,
    session: requests.Session | None = None,
    delay_seconds: float = 0.15,
) -> Path:
    """중단 후 재개 가능한 raw ZIP 저장소를 만들고 완료 시 manifest를 잠근다."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,100}", snapshot_id):
        raise Form4BulkError("unsafe snapshot id")
    protocol = load_protocol(protocol_path)
    source = protocol["source"]
    expected = quarters(source["start_quarter"], source["end_quarter"])
    snapshot = output_root / snapshot_id
    raw = snapshot / "raw"
    manifest_path = snapshot / "manifest.json"
    state_path = snapshot / "download_state.json"
    if manifest_path.exists():
        verify_download(snapshot, protocol_path=protocol_path)
        return snapshot
    raw.mkdir(parents=True, exist_ok=True)
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    else:
        state = {
            "format_version": "herd-sec-form4-bulk-download-v2",
            "snapshot_id": snapshot_id,
            "protocol_sha256": sha256(protocol_path),
            "quarters": {},
        }
    if state.get("protocol_sha256") != sha256(protocol_path):
        raise Form4BulkError("download state protocol hash mismatch")

    client = session or requests.Session()
    client.headers.update({
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate",
    })
    for quarter in expected:
        filename = f"{quarter[:4]}q{quarter[-1]}_form345.zip"
        target = raw / filename
        recorded = state["quarters"].get(quarter)
        if recorded and target.exists() and sha256(target) == recorded["sha256"]:
            _validate_zip(target)
            continue
        temporary = target.with_suffix(".zip.part")
        errors = []
        for url in source_urls(quarter):
            try:
                response = client.get(url, timeout=120)
                response.raise_for_status()
                temporary.write_bytes(response.content)
                _validate_zip(temporary)
                temporary.replace(target)
                state["quarters"][quarter] = {
                    "url": url,
                    "sha256": sha256(target),
                    "bytes": target.stat().st_size,
                }
                state_path.write_text(
                    json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                break
            except (requests.RequestException, OSError, Form4BulkError) as error:
                temporary.unlink(missing_ok=True)
                errors.append(f"{url}: {error}")
        else:
            raise Form4BulkError(
                f"all official URLs failed for {quarter}: {'; '.join(errors)}"
            )
        if session is None:
            time.sleep(delay_seconds)

    entries = [state["quarters"][quarter] | {"quarter": quarter} for quarter in expected]
    manifest = {
        "format_version": "herd-sec-form4-bulk-download-v2",
        "snapshot_id": snapshot_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": sha256(protocol_path),
        "source_landing_page": source["landing_page"],
        "quarter_start": expected[0],
        "quarter_end": expected[-1],
        "quarter_count": len(entries),
        "quarters": entries,
        "bytes": sum(int(row["bytes"]) for row in entries),
        "price_outcomes_opened": False,
        "blind_holdout_access": False,
        "survivorship_safe": False,
        "operational_action_authority": False,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    state_path.unlink(missing_ok=True)
    verify_download(snapshot, protocol_path=protocol_path)
    return snapshot


def verify_download(snapshot: Path, *, protocol_path: Path = PROTOCOL) -> dict:
    manifest_path = snapshot / "manifest.json"
    if not manifest_path.exists():
        raise Form4BulkError("bulk download manifest missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("protocol_sha256") != sha256(protocol_path):
        raise Form4BulkError("bulk download protocol hash mismatch")
    protocol = load_protocol(protocol_path)
    expected = quarters(
        protocol["source"]["start_quarter"],
        protocol["source"]["end_quarter"],
    )
    entries = manifest.get("quarters", [])
    if [row.get("quarter") for row in entries] != expected:
        raise Form4BulkError("bulk download quarter sequence mismatch")
    for row in entries:
        filename = f"{row['quarter'][:4]}q{row['quarter'][-1]}_form345.zip"
        path = snapshot / "raw" / filename
        if not path.exists() or sha256(path) != row.get("sha256"):
            raise Form4BulkError(f"bulk ZIP hash mismatch: {row['quarter']}")
        _validate_zip(path)
    return manifest


def _normalize_cik(value: object) -> str:
    text = str(value or "").strip()
    return f"{int(text):010d}" if text else ""


def load_universe(
    independent_universe: Path,
    discovery_catalog: Path,
) -> tuple[pd.DataFrame, dict[str, str], pd.DataFrame]:
    independent = pd.read_csv(independent_universe, dtype={"cik": str})
    required = {"ticker", "cik", "eligible", "rejection_reasons"}
    if not required.issubset(independent.columns):
        raise Form4BulkError("independent universe columns are incomplete")
    eligible = independent[
        independent["eligible"].astype(str).str.lower().eq("true")
    ].copy()
    eligible["issuer_cik"] = eligible["cik"].map(_normalize_cik)
    eligible = eligible[eligible["issuer_cik"].ne("")]
    for column in ("company", "gics_sector", "sector_etf"):
        if column not in eligible:
            eligible[column] = ""
    if eligible["ticker"].duplicated().any():
        raise Form4BulkError("independent universe contains duplicate tickers")

    discovery = pd.read_csv(discovery_catalog, dtype={"issuer_cik": str})
    if not {"issuer_cik", "candidate_tickers"}.issubset(discovery.columns):
        raise Form4BulkError("discovery Form 4 catalog columns are incomplete")
    discovery_ciks = {
        _normalize_cik(value) for value in discovery["issuer_cik"] if str(value).strip()
    }
    overlap = eligible[eligible["issuer_cik"].isin(discovery_ciks)].copy()
    eligible = eligible[~eligible["issuer_cik"].isin(discovery_ciks)].copy()
    split_by_cik = {cik: "DISCOVERY_51" for cik in discovery_ciks}
    for row in eligible.itertuples(index=False):
        split_by_cik[row.issuer_cik] = "INDEPENDENT_CURRENT_CONSTITUENT"
    return eligible, split_by_cik, overlap


def _read_table(archive: zipfile.ZipFile, name: str) -> pd.DataFrame:
    with archive.open(name) as stream:
        return pd.read_csv(
            stream,
            sep="\t",
            dtype=str,
            keep_default_na=False,
            na_filter=False,
            quoting=csv.QUOTE_MINIMAL,
            low_memory=False,
        )


def _iso_date(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return datetime.strptime(text, "%d-%b-%Y").date().isoformat()


def _footnote_ids(row: pd.Series) -> list[str]:
    values: set[str] = set()
    for column in FOOTNOTE_COLUMNS & set(row.index):
        values.update(
            part.strip()
            for part in re.split(r"[,;|\s]+", str(row[column]))
            if part.strip()
        )
    return sorted(values)


def _write_frame(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def normalize(
    snapshot: Path,
    *,
    independent_universe: Path,
    discovery_catalog: Path,
    protocol_path: Path = PROTOCOL,
) -> dict:
    """공식 분기 ZIP을 선택된 issuer의 해시 고정 원자 원장으로 평탄화한다."""
    manifest = verify_download(snapshot, protocol_path=protocol_path)
    if (snapshot / "normalized_manifest.json").exists():
        return verify_normalized(snapshot, protocol_path=protocol_path)
    eligible, split_by_cik, overlap = load_universe(
        independent_universe, discovery_catalog
    )
    target_ciks = set(split_by_cik)
    submissions: list[dict] = []
    owners: list[dict] = []
    transactions: list[dict] = []
    footnotes: list[dict] = []
    submission_seen: set[str] = set()
    owner_seen: set[tuple[str, str]] = set()
    footnote_seen: set[tuple[str, str]] = set()

    for entry in manifest["quarters"]:
        quarter = entry["quarter"]
        path = snapshot / "raw" / f"{quarter[:4]}q{quarter[-1]}_form345.zip"
        with zipfile.ZipFile(path) as archive:
            submission = _read_table(archive, "SUBMISSION.tsv")
            submission["ISSUERCIK_NORM"] = submission["ISSUERCIK"].map(_normalize_cik)
            selected = submission[
                submission["ISSUERCIK_NORM"].isin(target_ciks)
                & submission["DOCUMENT_TYPE"].isin({"4", "4/A"})
            ].copy()
            accessions = set(selected["ACCESSION_NUMBER"])
            for row in selected.itertuples(index=False):
                accession = row.ACCESSION_NUMBER
                if accession in submission_seen:
                    raise Form4BulkError(f"duplicate submission accession: {accession}")
                submission_seen.add(accession)
                aff = getattr(row, "AFF10B5ONE", "")
                submissions.append({
                    "accessionNumber": accession,
                    "sourceQuarter": quarter,
                    "issuerCik": row.ISSUERCIK_NORM,
                    "issuerName": row.ISSUERNAME,
                    "issuerTradingSymbol": row.ISSUERTRADINGSYMBOL,
                    "filingDate": _iso_date(row.FILING_DATE),
                    "periodOfReport": _iso_date(row.PERIOD_OF_REPORT),
                    "documentType": row.DOCUMENT_TYPE,
                    "isAmendment": row.DOCUMENT_TYPE.endswith("/A"),
                    "aff10b5one": str(aff).strip().lower(),
                    "remarks": row.REMARKS,
                    "researchSplit": split_by_cik[row.ISSUERCIK_NORM],
                })
            if not accessions:
                continue

            owner_frame = _read_table(archive, "REPORTINGOWNER.tsv")
            owner_frame = owner_frame[owner_frame["ACCESSION_NUMBER"].isin(accessions)]
            owner_by_accession: dict[str, list[str]] = defaultdict(list)
            for row in owner_frame.itertuples(index=False):
                key = (row.ACCESSION_NUMBER, _normalize_cik(row.RPTOWNERCIK))
                if key in owner_seen:
                    continue
                owner_seen.add(key)
                owner_by_accession[row.ACCESSION_NUMBER].append(key[1])
                owners.append({
                    "accessionNumber": row.ACCESSION_NUMBER,
                    "reportingOwnerCik": key[1],
                    "reportingOwnerName": row.RPTOWNERNAME,
                    "relationship": row.RPTOWNER_RELATIONSHIP,
                    "officerTitle": row.RPTOWNER_TITLE,
                })

            note_frame = _read_table(archive, "FOOTNOTES.tsv")
            note_frame = note_frame[note_frame["ACCESSION_NUMBER"].isin(accessions)]
            notes_by_accession: dict[str, dict[str, str]] = defaultdict(dict)
            for row in note_frame.itertuples(index=False):
                key = (row.ACCESSION_NUMBER, row.FOOTNOTE_ID)
                if key in footnote_seen:
                    continue
                footnote_seen.add(key)
                notes_by_accession[row.ACCESSION_NUMBER][row.FOOTNOTE_ID] = (
                    row.FOOTNOTE_TXT
                )
                footnotes.append({
                    "accessionNumber": row.ACCESSION_NUMBER,
                    "footnoteId": row.FOOTNOTE_ID,
                    "footnoteText": row.FOOTNOTE_TXT,
                })

            for table_name, (key_column, is_derivative) in TRANSACTION_TABLES.items():
                frame = _read_table(archive, table_name)
                frame = frame[frame["ACCESSION_NUMBER"].isin(accessions)]
                for _, row in frame.iterrows():
                    accession = row["ACCESSION_NUMBER"]
                    code = row.get("TRANS_CODE", "")
                    refs = _footnote_ids(row)
                    referenced = "\n".join(
                        f"[{identifier}] "
                        f"{notes_by_accession[accession].get(identifier, '')}"
                        for identifier in refs
                    )
                    transaction_key = str(row.get(key_column, ""))
                    atomic_id = hashlib.sha256(
                        f"{accession}|{table_name}|{transaction_key}".encode()
                    ).hexdigest()
                    transactions.append({
                        "atomicTransactionId": atomic_id,
                        "accessionNumber": accession,
                        "sourceQuarter": quarter,
                        "transactionTable": table_name.removesuffix(".tsv"),
                        "transactionKey": transaction_key,
                        "isDerivative": is_derivative,
                        "transactionDate": _iso_date(row.get("TRANS_DATE", "")),
                        "transactionCode": code,
                        "economicClass": CLASS_BY_CODE.get(
                            code, "UNKNOWN_TRANSACTION_CODE"
                        ),
                        "economicGroup": GROUP_BY_CODE.get(
                            code, "UNKNOWN_TRANSACTION_CODE"
                        ),
                        "securityTitle": row.get("SECURITY_TITLE", ""),
                        "equitySwapInvolved": row.get("EQUITY_SWAP_INVOLVED", ""),
                        "transactionShares": row.get("TRANS_SHARES", ""),
                        "transactionPricePerShare": row.get(
                            "TRANS_PRICEPERSHARE", ""
                        ),
                        "acquiredDisposedCode": row.get(
                            "TRANS_ACQUIRED_DISP_CD", ""
                        ),
                        "sharesOwnedFollowingTransaction": row.get(
                            "SHRS_OWND_FOLWNG_TRANS", ""
                        ),
                        "directOrIndirectOwnership": row.get(
                            "DIRECT_INDIRECT_OWNERSHIP", ""
                        ),
                        "natureOfOwnership": row.get("NATURE_OF_OWNERSHIP", ""),
                        "footnoteIds": "|".join(refs),
                        "referencedFootnoteText": referenced,
                        "reportingOwnerCiks": "|".join(
                            sorted(owner_by_accession.get(accession, []))
                        ),
                    })

    normalized = snapshot / "normalized"
    temporary = snapshot / ".normalized.tmp"
    shutil.rmtree(temporary, ignore_errors=True)
    temporary.mkdir()
    _write_frame(temporary / "submissions.csv", submissions)
    _write_frame(temporary / "reporting_owners.csv", owners)
    _write_frame(temporary / "transactions.csv", transactions)
    _write_frame(temporary / "footnotes.csv", footnotes)
    eligible[[
        "ticker",
        "issuer_cik",
        "company",
        "gics_sector",
        "sector_etf",
    ]].to_csv(temporary / "independent_universe.csv", index=False)
    if normalized.exists():
        raise Form4BulkError("normalized directory exists without manifest")
    temporary.rename(normalized)
    files = {
        path.name: {
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(normalized.glob("*.csv"))
    }
    output = {
        "format_version": "herd-sec-form4-research-census-v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": sha256(protocol_path),
        "download_manifest_sha256": sha256(snapshot / "manifest.json"),
        "independent_universe_sha256": sha256(independent_universe),
        "discovery_catalog_sha256": sha256(discovery_catalog),
        "quarters": int(manifest["quarter_count"]),
        "selected_issuers": len(target_ciks),
        "independent_issuers": int(eligible["issuer_cik"].nunique()),
        "independent_issuer_overlap_excluded": len(overlap),
        "independent_issuer_overlap_tickers": sorted(overlap["ticker"].tolist()),
        "submissions": len(submissions),
        "reporting_owners": len(owners),
        "transactions": len(transactions),
        "footnotes": len(footnotes),
        "files": files,
        "price_outcomes_opened": False,
        "blind_holdout_access": False,
        "survivorship_safe": False,
        "operational_action_authority": False,
    }
    (snapshot / "normalized_manifest.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return verify_normalized(snapshot, protocol_path=protocol_path)


def verify_normalized(snapshot: Path, *, protocol_path: Path = PROTOCOL) -> dict:
    path = snapshot / "normalized_manifest.json"
    if not path.exists():
        raise Form4BulkError("normalized census manifest missing")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("protocol_sha256") != sha256(protocol_path):
        raise Form4BulkError("normalized census protocol hash mismatch")
    if manifest.get("download_manifest_sha256") != sha256(snapshot / "manifest.json"):
        raise Form4BulkError("normalized census download lineage mismatch")
    for name, metadata in manifest.get("files", {}).items():
        candidate = snapshot / "normalized" / Path(name).name
        if not candidate.exists() or sha256(candidate) != metadata.get("sha256"):
            raise Form4BulkError(f"normalized file hash mismatch: {name}")
    if manifest.get("operational_action_authority") is not False:
        raise Form4BulkError("normalized census must not authorize actions")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    collect_parser = sub.add_parser("download")
    collect_parser.add_argument("snapshot_id")
    collect_parser.add_argument(
        "--root",
        type=Path,
        default=ROOT / "data/reference/sec",
    )
    collect_parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    normalize_parser = sub.add_parser("normalize")
    normalize_parser.add_argument("snapshot", type=Path)
    normalize_parser.add_argument(
        "--independent-universe",
        type=Path,
        default=ROOT / "data/reports/independent_universe_v1.csv",
    )
    normalize_parser.add_argument(
        "--discovery-catalog",
        type=Path,
        default=ROOT / "data/reports/sec_form4_accession_catalog_v1.csv",
    )
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    if args.command == "download":
        result = download(
            args.root,
            args.snapshot_id,
            user_agent=resolve_user_agent(args.env_file),
        )
        print(result)
    elif args.command == "normalize":
        print(json.dumps(normalize(
            args.snapshot,
            independent_universe=args.independent_universe,
            discovery_catalog=args.discovery_catalog,
        ), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(verify_download(args.snapshot), ensure_ascii=False, indent=2))
        if (args.snapshot / "normalized_manifest.json").exists():
            print(json.dumps(
                verify_normalized(args.snapshot),
                ensure_ascii=False,
                indent=2,
            ))


if __name__ == "__main__":
    main()
