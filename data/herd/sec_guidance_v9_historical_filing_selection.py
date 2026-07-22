"""V9 독립 검증용 2010~2016년 적격 8-K를 결과 비관측 순서로 고정한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from herd.sec_8k_guidance_corpus_v1 import build_catalog, collect_documents
from herd.sec_guidance_v7_filing_selection import BASE, SUBMISSIONS, UNIVERSE
from herd.sec_master_index import resolve_user_agent


SELECTION_SALT = "HERD_SEC_GUIDANCE_V9_HISTORICAL_HOLDOUT_V1"
START = "2010-01-01"
END = "2016-07-17"
MINIMUM_FILINGS = 8
MAXIMUM_FILINGS = 24


def select_filings() -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    protocol = json.loads(BASE.read_text())
    protocol["period"] = {"start": START, "end": END}
    protocol["minimum_eligible_filings_per_ticker"] = MINIMUM_FILINGS
    protocol["collection_filings_per_ticker"] = MAXIMUM_FILINGS
    protocol["universe"] = str(UNIVERSE)
    protocol["submission_roots"] = [str(SUBMISSIONS)]
    protocol["download"] = dict(protocol["download"])
    protocol["download"].update({
        "include_filename_patterns": [
            "ex99", "exhibit99", "earn", "release", "presentation", "investor",
            "slides", "guidance", "outlook",
        ],
        "minimum_request_interval_seconds": 0.125,
        "maximum_workers": 4,
        "checkpoint_every_filings": 50,
        "throttle_cooldown_seconds": 30.0,
    })
    catalog, base_report = build_catalog(protocol)
    counts = catalog.groupby("ticker").size().rename("eligible_filings").reset_index()
    eligible = counts.loc[counts["eligible_filings"] >= MINIMUM_FILINGS]
    universe = pd.read_csv(UNIVERSE, dtype={"cik": str}).merge(
        eligible, on="ticker", validate="one_to_one",
    )
    selected = catalog.loc[catalog["ticker"].isin(set(universe["ticker"]))].copy()
    selected["priority"] = selected.apply(lambda row: hashlib.sha256(
        f'{SELECTION_SALT}:{row["ticker"]}:{row["accession_number"]}'.encode()
    ).hexdigest(), axis=1)
    selected = (
        selected.sort_values(["ticker", "priority"])
        .groupby("ticker", group_keys=False).head(MAXIMUM_FILINGS)
        .drop(columns="priority")
        .sort_values(["accepted_at", "ticker"]).reset_index(drop=True)
    )
    report = {
        "report_version": "herd-sec-guidance-v9-historical-filing-selection-v1",
        "scope": "PARSER_VALIDATION_ONLY",
        "period": protocol["period"],
        "eligible_tickers": len(universe),
        "selected_filings": len(selected),
        "selected_tickers": int(selected["ticker"].nunique()),
        "minimum_eligible_filings_per_ticker": MINIMUM_FILINGS,
        "maximum_filings_per_ticker": MAXIMUM_FILINGS,
        "selection_used_guidance_text": False,
        "selection_used_parser_output": False,
        "selection_used_source_review_labels": False,
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
        print(collect_documents(
            catalog, protocol, Path("data/reference/sec"), args.collect_snapshot_id,
            resolve_user_agent(args.env_file),
        ))


if __name__ == "__main__":
    main()
