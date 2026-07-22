"""V7 독립 기업의 적격 8-K를 기업별 고정 상한으로 선택한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from herd.sec_8k_guidance_corpus_v1 import build_catalog, collect_documents
from herd.sec_master_index import resolve_user_agent


BASE = Path("data/herd/sec_guidance_v5_broad_expansion.json")
UNIVERSE = Path("data/reports/sec_guidance_v7_independent_universe.csv")
SUBMISSIONS = Path("data/reference/sec/sec-guidance-v7-independent-meta-201-20260722/raw")


def select_filings() -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    protocol = json.loads(BASE.read_text())
    protocol["download"] = dict(protocol["download"])
    protocol["download"]["include_filename_patterns"] = [
        "ex99", "exhibit99", "earn", "release", "presentation", "investor", "slides", "guidance", "outlook",
    ]
    protocol["universe"] = str(UNIVERSE)
    protocol["submission_roots"] = [str(SUBMISSIONS)]
    catalog, base_report = build_catalog(protocol)
    counts = catalog.groupby("ticker").size().rename("eligible_filings").reset_index()
    counts = counts.loc[counts["eligible_filings"] >= protocol["minimum_eligible_filings_per_ticker"]]
    universe = pd.read_csv(UNIVERSE, dtype={"cik": str}).merge(counts, on="ticker", validate="one_to_one")
    tickers = set(universe["ticker"].astype(str))
    selected = catalog.loc[catalog["ticker"].astype(str).isin(tickers)].copy()
    selected["priority"] = selected.apply(lambda row: hashlib.sha256(
        f'V7:{row["ticker"]}:{row["accession_number"]}'.encode()
    ).hexdigest(), axis=1)
    selected = selected.sort_values(["ticker", "priority"]).groupby("ticker", group_keys=False).head(
        protocol["collection_filings_per_ticker"]
    ).drop(columns="priority").sort_values(["accepted_at", "ticker"]).reset_index(drop=True)
    report = {
        "report_version": "herd-sec-guidance-v7-filing-selection-v1",
        "scope": "PARSER_VALIDATION_ONLY",
        "input_tickers": 201,
        "eligible_tickers": len(universe),
        "eligible_sectors": int(universe["gics_sector"].nunique()),
        "selected_filings": len(selected),
        "maximum_filings_per_ticker": protocol["collection_filings_per_ticker"],
        "attachment_selection": "PRIMARY_PLUS_DETERMINISTIC_EARNINGS_EX99_FILENAMES",
        "selection_used_guidance_text": False,
        "selection_used_parser_output": False,
        "selection_used_price_outcomes": False,
        "base_catalog_report": base_report,
        "operational_action_ratio": 0.0,
    }
    return universe.sort_values("ticker"), selected, report, protocol


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--collect-snapshot-id")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    universe, catalog, report, protocol = select_filings()
    universe.to_csv(args.universe, index=False, lineterminator="\n")
    catalog.to_csv(args.catalog, index=False, lineterminator="\n")
    report["base_protocol_sha256"] = hashlib.sha256(BASE.read_bytes()).hexdigest()
    report["universe_sha256"] = hashlib.sha256(args.universe.read_bytes()).hexdigest()
    report["catalog_sha256"] = hashlib.sha256(args.catalog.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.collect_snapshot_id:
        print(collect_documents(catalog, protocol, Path("data/reference/sec"), args.collect_snapshot_id, resolve_user_agent(args.env_file)))


if __name__ == "__main__":
    main()
