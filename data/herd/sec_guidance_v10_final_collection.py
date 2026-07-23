"""고정한 V10 신규 기업에서 결과 비관측 8-K 원문 수집 목록을 만든다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from herd.sec_8k_guidance_corpus_v1 import build_catalog, collect_documents
from herd.sec_master_index import resolve_user_agent


PROTOCOL = Path(__file__).with_suffix(".json")


def select_filings(protocol: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    expansion = json.loads(Path(protocol["expansion_contract"]).read_text())
    runtime = {
        **expansion,
        "universe": protocol["universe"],
        "submission_roots": [protocol["submission_root"]],
        "download": protocol["download"],
    }
    catalog, base_report = build_catalog(runtime)
    counts = catalog.groupby("ticker").size().rename("eligible_filings").reset_index()
    counts = counts.loc[
        counts["eligible_filings"] >= expansion["minimum_eligible_filings_per_ticker"]
    ].copy()
    counts["issuer_priority"] = counts["ticker"].map(
        lambda ticker: hashlib.sha256(
            f'{protocol["selection_salt"]}:{ticker}'.encode()
        ).hexdigest()
    )
    eligible = counts.sort_values("issuer_priority").head(protocol["filing_target_tickers"])
    universe = pd.read_csv(protocol["universe"], dtype={"cik": str}).merge(
        eligible, on="ticker", validate="one_to_one",
    )
    selected_tickers = set(universe["ticker"].astype(str))
    selected = catalog.loc[catalog["ticker"].astype(str).isin(selected_tickers)].copy()
    selected["filing_priority"] = selected.apply(
        lambda row: hashlib.sha256(
            f'{protocol["selection_salt"]}:{row["ticker"]}:{row["accession_number"]}'.encode()
        ).hexdigest(),
        axis=1,
    )
    selected = (
        selected.sort_values(["ticker", "filing_priority"])
        .groupby("ticker", group_keys=False).head(expansion["collection_filings_per_ticker"])
        .drop(columns="filing_priority")
        .sort_values(["accepted_at", "ticker"]).reset_index(drop=True)
    )
    report = {
        "report_version": "herd-sec-guidance-v10-final-collection-v1",
        "scope": protocol["scope"],
        "metadata_tickers": base_report["universe_tickers"],
        "eligible_tickers": len(counts),
        "selected_tickers": len(universe),
        "selected_filings": len(selected),
        "minimum_eligible_filings_per_ticker": expansion["minimum_eligible_filings_per_ticker"],
        "maximum_filings_per_ticker": expansion["collection_filings_per_ticker"],
        "selection_used_guidance_text": False,
        "selection_used_parser_output": False,
        "selection_used_source_review_labels": False,
        "selection_used_price_outcomes": False,
        "base_catalog_report": base_report,
        "operational_action_ratio": 0.0,
    }
    return universe.sort_values("issuer_priority"), selected, report, runtime


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--collect-snapshot-id")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    universe, catalog, report, runtime = select_filings(protocol)
    universe.to_csv(args.universe, index=False, lineterminator="\n")
    catalog.to_csv(args.catalog, index=False, lineterminator="\n")
    report["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    report["universe_sha256"] = hashlib.sha256(args.universe.read_bytes()).hexdigest()
    report["catalog_sha256"] = hashlib.sha256(args.catalog.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.collect_snapshot_id:
        print(collect_documents(
            catalog, runtime, Path("data/reference/sec"), args.collect_snapshot_id,
            resolve_user_agent(args.env_file),
        ))


if __name__ == "__main__":
    main()
