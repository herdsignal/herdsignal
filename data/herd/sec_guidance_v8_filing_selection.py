"""V7 선택 accession을 제외한 다음 해시 구간의 적격 8-K를 고정한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from herd.sec_8k_guidance_corpus_v1 import build_catalog, collect_documents
from herd.sec_guidance_v7_filing_selection import BASE, SUBMISSIONS, UNIVERSE
from herd.sec_master_index import resolve_user_agent


V7_CATALOG = Path("data/reports/sec_guidance_v7_filing_catalog.csv")
SELECTION_SALT = "HERD_SEC_GUIDANCE_V8_SECOND_WAVE_V1"


def select_filings() -> tuple[pd.DataFrame, dict, dict]:
    protocol = json.loads(BASE.read_text())
    protocol["download"] = dict(protocol["download"])
    protocol["download"]["include_filename_patterns"] = [
        "ex99", "exhibit99", "earn", "release", "presentation", "investor", "slides", "guidance", "outlook",
    ]
    protocol["download"]["minimum_request_interval_seconds"] = 0.125
    protocol["download"]["maximum_workers"] = 4
    protocol["download"]["checkpoint_every_filings"] = 50
    protocol["download"]["throttle_cooldown_seconds"] = 30.0
    protocol["universe"] = str(UNIVERSE)
    protocol["submission_roots"] = [str(SUBMISSIONS)]
    catalog, base_report = build_catalog(protocol)
    prior = set(pd.read_csv(V7_CATALOG)["accession_number"].astype(str))
    remaining = catalog.loc[~catalog["accession_number"].astype(str).isin(prior)].copy()
    remaining["priority"] = remaining.apply(lambda row: hashlib.sha256(
        f'{SELECTION_SALT}:{row["ticker"]}:{row["accession_number"]}'.encode()
    ).hexdigest(), axis=1)
    selected = (
        remaining.sort_values(["ticker", "priority"])
        .groupby("ticker", group_keys=False)
        .head(protocol["collection_filings_per_ticker"])
        .drop(columns="priority")
        .sort_values(["accepted_at", "ticker"])
        .reset_index(drop=True)
    )
    report = {
        "report_version": "herd-sec-guidance-v8-filing-selection-v1",
        "scope": "PARSER_VALIDATION_ONLY",
        "catalog_filings": len(catalog),
        "v7_accessions_excluded": len(prior),
        "remaining_filings": len(remaining),
        "selected_filings": len(selected),
        "selected_tickers": int(selected["ticker"].nunique()),
        "maximum_filings_per_ticker": protocol["collection_filings_per_ticker"],
        "selection_used_guidance_text": False,
        "selection_used_parser_output": False,
        "selection_used_price_outcomes": False,
        "base_catalog_report": base_report,
        "operational_action_ratio": 0.0,
    }
    return selected, report, protocol


def select_completion_filings() -> tuple[pd.DataFrame, dict, dict]:
    """라벨 확인 전, V7 제외 모집단에서 1차 미수집 accession을 전부 반환한다."""
    selected, initial_report, protocol = select_filings()
    initial = set(selected["accession_number"].astype(str))
    catalog, _ = build_catalog(protocol)
    v7 = set(pd.read_csv(V7_CATALOG)["accession_number"].astype(str))
    completion = catalog.loc[
        ~catalog["accession_number"].astype(str).isin(v7 | initial)
    ].sort_values(["accepted_at", "ticker"]).reset_index(drop=True)
    report = {
        "report_version": "herd-sec-guidance-v8-coverage-completion-v1",
        "scope": "PARSER_VALIDATION_ONLY",
        "selection_reason": "EXHAUST_REMAINING_OUTCOME_BLIND_ELIGIBLE_ACCESSIONS",
        "v7_accessions_excluded": len(v7),
        "initial_v8_accessions_excluded": len(initial),
        "selected_filings": len(completion),
        "selected_tickers": int(completion["ticker"].nunique()),
        "selection_used_guidance_text": False,
        "selection_used_parser_output": False,
        "selection_used_source_review_labels": False,
        "selection_used_price_outcomes": False,
        "initial_selection_report": initial_report,
        "operational_action_ratio": 0.0,
    }
    return completion, report, protocol


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--collect-snapshot-id")
    parser.add_argument("--complete-coverage", action="store_true")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    catalog, report, protocol = (
        select_completion_filings() if args.complete_coverage else select_filings()
    )
    catalog.to_csv(args.catalog, index=False, lineterminator="\n")
    report["base_protocol_sha256"] = hashlib.sha256(BASE.read_bytes()).hexdigest()
    report["v7_catalog_sha256"] = hashlib.sha256(V7_CATALOG.read_bytes()).hexdigest()
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
