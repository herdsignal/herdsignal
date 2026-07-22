"""기존 PIT 스냅샷에 있으나 미검수인 기업을 V6 2차 원문 표본으로 고정한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path

import pandas as pd

from herd.sec_8k_guidance_corpus_v1 import build_catalog, collect_documents
from herd.sec_master_index import resolve_user_agent


PROTOCOL = Path(__file__).with_suffix(".json")


def select_second_wave(protocol: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    source = pd.read_csv(protocol["candidate_universe"], dtype={"cik": str})
    source["cik"] = source["cik"].str.replace(r"\.0$", "", regex=True).str.zfill(10)
    excluded_tickers: set[str] = set()
    excluded_accessions: set[str] = set()
    for path in protocol["exclude_issuer_universes"]:
        excluded_tickers.update(pd.read_csv(path)["ticker"].astype(str))
    for path in protocol["review_ledgers"]:
        review = pd.read_csv(path)
        excluded_tickers.update(review["ticker"].astype(str))
        excluded_accessions.update(review["accession_number"].astype(str))
    local_ciks = {
        match.group(1)
        for root in protocol["submission_roots"]
        for path in Path(root).glob("CIK*-submissions.json")
        if (match := re.fullmatch(r"CIK(\d{10})-submissions.json", path.name))
    }
    universe = source.loc[
        source["eligible"].eq(True)
        & source["cik"].isin(local_ciks)
        & ~source["ticker"].astype(str).isin(excluded_tickers),
        ["ticker", "cik", "gics_sector"],
    ].copy()
    universe["cik_link_status"] = "UNIQUE_CIK_NAME_CANDIDATE"
    runtime = dict(protocol)
    with tempfile.TemporaryDirectory(prefix="herd-v6-second-wave-") as directory:
        temporary = Path(directory) / "universe.csv"
        universe.to_csv(temporary, index=False, lineterminator="\n")
        runtime["universe"] = str(temporary)
        catalog, base_report = build_catalog(runtime)
    catalog = catalog.loc[~catalog["accession_number"].astype(str).isin(excluded_accessions)].copy()
    counts = catalog.groupby("ticker").size().rename("eligible_filings").reset_index()
    counts = counts.loc[counts["eligible_filings"] >= protocol["minimum_eligible_filings_per_ticker"]]
    selected = universe.merge(counts, on="ticker", validate="one_to_one").sort_values("ticker")
    tickers = set(selected["ticker"].astype(str))
    sampled = catalog.loc[catalog["ticker"].astype(str).isin(tickers)].copy()
    sampled["priority"] = sampled.apply(lambda row: hashlib.sha256(
        f'V6_SECOND:{row["ticker"]}:{row["accession_number"]}'.encode()
    ).hexdigest(), axis=1)
    sampled = sampled.sort_values(["ticker", "priority"]).groupby("ticker", group_keys=False).head(
        protocol["collection_filings_per_ticker"]
    ).drop(columns="priority").sort_values(["accepted_at", "ticker"]).reset_index(drop=True)
    return selected.reset_index(drop=True), sampled, {
        "report_version": "herd-sec-guidance-v6-second-wave-v1",
        "scope": protocol["scope"],
        "local_unreviewed_tickers": len(universe),
        "selected_tickers": len(selected),
        "selected_sectors": int(selected["gics_sector"].nunique()) if not selected.empty else 0,
        "selected_filings": len(sampled),
        "selection_used_guidance_text": False,
        "selection_used_parser_output": False,
        "selection_used_price_outcomes": False,
        "base_catalog_report": base_report,
        "operational_action_ratio": 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--collect-snapshot-id")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    universe, catalog, report = select_second_wave(protocol)
    universe.to_csv(args.universe, index=False, lineterminator="\n")
    catalog.to_csv(args.catalog, index=False, lineterminator="\n")
    report["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    report["universe_sha256"] = hashlib.sha256(args.universe.read_bytes()).hexdigest()
    report["catalog_sha256"] = hashlib.sha256(args.catalog.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.collect_snapshot_id:
        print(collect_documents(catalog, protocol, Path("data/reference/sec"), args.collect_snapshot_id, resolve_user_agent(args.env_file)))


if __name__ == "__main__":
    main()
