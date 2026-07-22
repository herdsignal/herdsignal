"""V4 독립 정확도 표본을 위한 미검수 기업 8-K corpus를 고정·수집한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from herd.sec_8k_guidance_corpus_v1 import build_catalog, collect_documents
from herd.sec_master_index import resolve_user_agent
from herd.sec_guidance_expansion_corpus_v3 import candidate_universe


PROTOCOL = Path(__file__).with_suffix(".json")


def select_issuers(protocol: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    base_protocol = {
        "current_ticker_map": protocol["current_ticker_map"],
        "exclude_universe": protocol["base_exclude_universe"],
        "submission_roots": protocol["submission_roots"],
    }
    universe = candidate_universe(base_protocol)
    excluded_tickers = set(pd.read_csv(protocol["prior_expansion_universe"])["ticker"].astype(str))
    for path in protocol.get("additional_exclude_universes", []):
        excluded_tickers.update(pd.read_csv(path)["ticker"].astype(str))
    for path in protocol["review_ledgers"]:
        excluded_tickers.update(pd.read_csv(path)["ticker"].astype(str))
    excluded_tickers.update(pd.read_csv(protocol["frozen_pre_expansion_review_tickers"])["ticker"].astype(str))
    universe = universe.loc[~universe["ticker"].isin(excluded_tickers)].copy()

    temporary = Path("data/reports/sec_guidance_v4_issuer_candidates.csv")
    universe.to_csv(temporary, index=False, lineterminator="\n")
    runtime = dict(protocol)
    runtime["universe"] = str(temporary)
    catalog, base_report = build_catalog(runtime)
    counts = catalog.groupby("ticker").size().rename("eligible_filings").reset_index()
    counts = counts.loc[counts["eligible_filings"] >= protocol["minimum_eligible_filings_per_ticker"]]
    selected_counts = counts.sort_values(["eligible_filings", "ticker"], ascending=[False, True]).head(
        protocol["target_tickers"]
    )
    selected = universe.merge(selected_counts, on="ticker", validate="one_to_one")
    selected_tickers = set(selected["ticker"])
    sampled = catalog.loc[catalog["ticker"].isin(selected_tickers)].copy()
    sampled["selection_priority"] = sampled.apply(
        lambda row: hashlib.sha256(f'{row["ticker"]}:{row["accession_number"]}'.encode()).hexdigest(), axis=1,
    )
    sampled = (
        sampled.sort_values(["ticker", "selection_priority"])
        .groupby("ticker", group_keys=False)
        .head(protocol["collection_filings_per_ticker"])
        .drop(columns="selection_priority")
        .sort_values(["accepted_at", "ticker", "accession_number"])
        .reset_index(drop=True)
    )
    return selected.sort_values("ticker"), sampled, {
        "report_version": "herd-sec-guidance-v4-issuer-expansion-v1",
        "eligible_unseen_tickers": len(universe),
        "selected_tickers": len(selected),
        "selected_filings": len(sampled),
        "minimum_selected_filing_coverage": int(selected_counts["eligible_filings"].min()),
        "excluded_tickers": len(excluded_tickers),
        "selection_used_parser_output": False,
        "selection_used_guidance_text": False,
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
    parser.add_argument("--output-root", type=Path, default=Path("data/reference/sec"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    universe, catalog, report = select_issuers(protocol)
    args.universe.parent.mkdir(parents=True, exist_ok=True)
    universe.to_csv(args.universe, index=False, lineterminator="\n")
    catalog.to_csv(args.catalog, index=False, lineterminator="\n")
    report["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.collect_snapshot_id:
        runtime = dict(protocol)
        runtime["universe"] = str(args.universe)
        print(collect_documents(
            catalog,
            runtime,
            args.output_root,
            args.collect_snapshot_id,
            resolve_user_agent(args.env_file),
        ))


if __name__ == "__main__":
    main()
