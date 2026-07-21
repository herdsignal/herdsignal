"""51개 종목의 실적·가이던스 8-K 후보를 색인하고 SEC 원문을 고정한다."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from herd.sec_master_index import resolve_user_agent


PROTOCOL = Path(__file__).with_suffix(".json")
ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,100}$")


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _columns(payload: dict) -> dict:
    return payload.get("filings", {}).get("recent", payload)


def _history_path(raw: Path, cik10: str, name: str) -> Path:
    return raw / f"CIK{cik10}-history-{name}"


def locate_submissions(cik10: str, roots: list[Path]) -> tuple[Path, list[Path]]:
    for raw in roots:
        primary = raw / f"CIK{cik10}-submissions.json"
        if not primary.exists():
            continue
        payload = json.loads(primary.read_text(encoding="utf-8"))
        history = []
        for item in payload.get("filings", {}).get("files", []):
            path = _history_path(raw, cik10, item["name"])
            if path.exists():
                history.append(path)
        return primary, history
    raise FileNotFoundError(f"CIK{cik10}: submissions not found")


def filing_rows(payload: dict) -> list[dict]:
    columns = _columns(payload)
    count = len(columns.get("form", []))
    required = ["accessionNumber", "filingDate", "acceptanceDateTime", "form", "primaryDocument"]
    if any(len(columns.get(name, [])) != count for name in required):
        raise ValueError("incomplete SEC submission columns")
    items = columns.get("items", [""] * count)
    if len(items) != count:
        raise ValueError("incomplete SEC items column")
    return [{name: columns[name][index] for name in required} | {"items": items[index]} for index in range(count)]


def build_catalog(protocol: dict) -> tuple[pd.DataFrame, dict]:
    universe = pd.read_csv(protocol["universe"], dtype={"cik": str})[["ticker", "cik"]].drop_duplicates()
    roots = [Path(path) for path in protocol["submission_roots"]]
    start, end = protocol["period"]["start"], protocol["period"]["end"]
    eligible_forms, eligible_items = set(protocol["eligible_forms"]), tuple(protocol["eligible_items"])
    rows, missing = [], []
    for record in universe.sort_values("ticker").itertuples(index=False):
        cik10 = str(record.cik).zfill(10)
        try:
            primary, history = locate_submissions(cik10, roots)
        except FileNotFoundError:
            missing.append({"ticker": record.ticker, "cik": cik10})
            continue
        payloads = [json.loads(primary.read_text(encoding="utf-8"))]
        payloads.extend(json.loads(path.read_text(encoding="utf-8")) for path in history)
        seen = set()
        for payload in payloads:
            for filing in filing_rows(payload):
                accession = filing["accessionNumber"]
                if accession in seen or filing["form"] not in eligible_forms:
                    continue
                if not start <= filing["filingDate"] <= end:
                    continue
                item_tokens = {token.strip() for token in str(filing["items"]).split(",")}
                matched = sorted(set(eligible_items) & item_tokens)
                if not matched:
                    continue
                if not filing["acceptanceDateTime"] or not ACCESSION.fullmatch(accession):
                    continue
                seen.add(accession)
                accession_compact = accession.replace("-", "")
                archive_dir = f"{protocol['download']['archive_base']}/{int(cik10)}/{accession_compact}"
                rows.append({
                    "ticker": record.ticker, "cik": cik10, "accession_number": accession,
                    "form": filing["form"], "filing_date": filing["filingDate"],
                    "accepted_at": filing["acceptanceDateTime"], "items": ",".join(matched),
                    "primary_document": filing["primaryDocument"], "archive_dir": archive_dir,
                    "index_json_url": f"{archive_dir}/index.json",
                    "classification_status": "NOT_CLASSIFIED",
                })
    frame = pd.DataFrame(rows).sort_values(["accepted_at", "ticker", "accession_number"]).reset_index(drop=True)
    report = {
        "report_version": "herd-sec-8k-guidance-candidate-catalog-v1",
        "universe_tickers": int(universe["ticker"].nunique()),
        "tickers_with_submissions": int(universe["ticker"].nunique() - len(missing)),
        "missing_submissions": missing,
        "eligible_filings": len(frame),
        "tickers_with_eligible_filings": int(frame["ticker"].nunique()) if not frame.empty else 0,
        "first_accepted_at": str(frame["accepted_at"].min()) if not frame.empty else None,
        "last_accepted_at": str(frame["accepted_at"].max()) if not frame.empty else None,
        "guidance_direction_classified": 0,
        "operational_action_ratio": 0.0,
    }
    return frame, report


def _text_document(name: str, item: dict, config: dict) -> bool:
    lowered = name.lower()
    return (
        Path(lowered).suffix in set(config["extensions"])
        and not any(pattern in lowered for pattern in config["exclude_filename_patterns"])
        and not re.fullmatch(r"\d{10}-\d{2}-\d{6}\.txt", lowered)
        and int(item.get("size") or 0) <= int(config["maximum_text_document_bytes"])
    )


def collect_documents(catalog: pd.DataFrame, protocol: dict, output_root: Path,
                      snapshot_id: str, user_agent: str,
                      seed_corpus: Path | None = None) -> Path:
    if not SAFE_ID.fullmatch(snapshot_id):
        raise ValueError("unsafe snapshot id")
    final = output_root / snapshot_id
    if final.exists():
        raise FileExistsError(final)
    for stale in output_root.glob(f".{snapshot_id}.tmp-*"):
        shutil.rmtree(stale, ignore_errors=True)
    temp = output_root / f".{snapshot_id}.tmp-{uuid.uuid4().hex}"
    raw = temp / "raw"
    raw.mkdir(parents=True)
    index_rows, failures = [], []
    seed_accessions: set[str] = set()
    if seed_corpus:
        seed_index = pd.read_csv(seed_corpus / "index.csv", dtype={"cik": str})
        seed_index = seed_index.loc[
            seed_index["document_role"].eq("PRIMARY")
            | seed_index["document_name"].map(
                lambda name: _text_document(str(name), {"size": 0}, protocol["download"])
            )
        ].copy()
        index_rows = seed_index.to_dict("records")
        seed_accessions = set(seed_index["accession_number"].astype(str))
        seed_paths = set(seed_index["path"].astype(str))
        for relative in sorted(seed_paths):
            source = seed_corpus / relative
            (raw / source.name).hardlink_to(source)
    delay = max(
        float(protocol["download"]["minimum_request_interval_seconds"]),
        0.20 if seed_corpus else 0.0,
    )
    request_lock, file_lock = threading.Lock(), threading.Lock()
    next_request_at = [0.0]
    local = threading.local()

    def get(url: str, timeout: int) -> requests.Response:
        if not hasattr(local, "session"):
            local.session = requests.Session()
            local.session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
        with request_lock:
            wait = next_request_at[0] - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            next_request_at[0] = time.monotonic() + delay
        for attempt in range(4):
            response = local.session.get(url, timeout=timeout)
            if response.status_code < 400:
                return response
            if response.status_code not in {403, 404, 429, 500, 502, 503, 504} or attempt == 3:
                response.raise_for_status()
            time.sleep(2 ** attempt)
        raise RuntimeError("unreachable request retry state")

    def collect_one(filing) -> tuple[list[dict], dict | None]:
        collected = []
        try:
            directory = get(filing.index_json_url, 60).json()["directory"]["item"]
            names = {filing.primary_document}
            names.update(item["name"] for item in directory if _text_document(item["name"], item, protocol["download"]))
            for name in sorted(names):
                url = f"{filing.archive_dir}/{name}"
                content = get(url, 90).content
                digest = _sha256_bytes(content)
                path = raw / f"{digest}.gz"
                with file_lock:
                    if not path.exists():
                        with gzip.open(path, "wb", compresslevel=6) as stream:
                            stream.write(content)
                collected.append({
                    "ticker": filing.ticker, "cik": filing.cik,
                    "accession_number": filing.accession_number, "accepted_at": filing.accepted_at,
                    "items": filing.items, "document_name": name,
                    "document_role": "PRIMARY" if name == filing.primary_document else "TEXT_ATTACHMENT",
                    "source_url": url, "source_sha256": digest, "source_bytes": len(content),
                    "path": f"raw/{path.name}", "classification_status": "NOT_CLASSIFIED",
                })
            return collected, None
        except Exception as error:
            status = getattr(getattr(error, "response", None), "status_code", None)
            return [], {
                "accession_number": filing.accession_number,
                "error": type(error).__name__, "http_status": status,
            }

    try:
        filings = [row for row in catalog.itertuples(index=False) if row.accession_number not in seed_accessions]
        with ThreadPoolExecutor(max_workers=2 if seed_corpus else 4) as executor:
            futures = [executor.submit(collect_one, filing) for filing in filings]
            for position, future in enumerate(as_completed(futures), start=1):
                collected, failure = future.result()
                index_rows.extend(collected)
                if failure:
                    failures.append(failure)
                if position % 100 == 0:
                    print(f"collected filing indexes: {position}/{len(filings)}", flush=True)
        index_rows.sort(key=lambda row: (row["accepted_at"], row["ticker"], row["accession_number"], row["document_name"]))
        pd.DataFrame(index_rows).to_csv(temp / "index.csv", index=False, lineterminator="\n")
        manifest = {
            "format_version": "herd-sec-8k-guidance-pit-corpus-v1",
            "snapshot_id": snapshot_id, "created_at": datetime.now(timezone.utc).isoformat(),
            "filings_requested": len(catalog),
            "filings_collected": len(set(row["accession_number"] for row in index_rows)),
            "documents": len(index_rows), "bytes": sum(row["source_bytes"] for row in index_rows),
            "failures": failures, "user_agent_configured": True,
            "seed_corpus": str(seed_corpus) if seed_corpus else None,
            "seed_filings": len(seed_accessions),
            "guidance_direction_classified": 0, "operational_action_ratio": 0.0,
        }
        (temp / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        output_root.mkdir(parents=True, exist_ok=True)
        temp.rename(final)
        return final
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--collect-snapshot-id")
    parser.add_argument("--output-root", type=Path, default=Path("data/reference/sec"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--seed-corpus", type=Path)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    catalog, report = build_catalog(protocol)
    args.catalog.parent.mkdir(parents=True, exist_ok=True)
    catalog.to_csv(args.catalog, index=False, lineterminator="\n")
    report["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.collect_snapshot_id:
        print(collect_documents(
            catalog, protocol, args.output_root, args.collect_snapshot_id,
            resolve_user_agent(args.env_file), args.seed_corpus,
        ))


if __name__ == "__main__":
    main()
