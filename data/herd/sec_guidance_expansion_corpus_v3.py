"""새 기업 8-K corpus용 유니버스를 고정하고 SEC 문서를 수집한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import pandas as pd

from herd.sec_8k_guidance_corpus_v1 import build_catalog, collect_documents
from herd.sec_master_index import resolve_user_agent


PROTOCOL = Path(__file__).with_suffix(".json")
CIK_FILE = re.compile(r"CIK(\d{10})-submissions\.json$")


def candidate_universe(protocol: dict) -> pd.DataFrame:
    mapping = pd.read_csv(protocol["current_ticker_map"], dtype={"cik": str})
    mapping["cik"] = mapping["cik"].str.zfill(10)
    excluded = set(pd.read_csv(protocol["exclude_universe"])["ticker"].astype(str))
    local_ciks = set()
    for root in protocol["submission_roots"]:
        for path in Path(root).glob("CIK*-submissions.json"):
            match = CIK_FILE.fullmatch(path.name)
            if match:
                local_ciks.add(match.group(1))
    eligible = mapping.loc[
        mapping["cik"].isin(local_ciks)
        & mapping["exchange"].isin(["NYSE", "Nasdaq"])
        & mapping["ticker"].str.fullmatch(r"[A-Z]{1,5}")
        & ~mapping["ticker"].isin(excluded)
    ].copy()
    # 복수 증권이 같은 CIK에 연결되면 짧고 일반적인 ticker 하나만 남긴다.
    eligible = eligible.sort_values(["cik", "ticker"], key=lambda column: column.str.len() if column.name == "ticker" else column)
    return eligible.drop_duplicates("cik")[["ticker", "cik"]].sort_values("ticker").reset_index(drop=True)


def select_expansion(protocol: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    universe = candidate_universe(protocol)
    runtime = dict(protocol)
    runtime["universe"] = "__in_memory__"
    # build_catalog의 파일 계약을 우회하지 않고 임시 universe는 호출자가 제공한다.
    temporary = Path("data/reports/sec_guidance_expansion_universe_candidates_v3.csv")
    universe.to_csv(temporary, index=False, lineterminator="\n")
    runtime["universe"] = str(temporary)
    catalog, base_report = build_catalog(runtime)
    counts = catalog.groupby("ticker").size().rename("eligible_filings").reset_index()
    counts = counts.loc[counts["eligible_filings"] >= protocol["minimum_eligible_filings_per_ticker"]]
    selected = counts.sort_values(["eligible_filings", "ticker"], ascending=[False, True]).head(protocol["target_tickers"])
    selected_tickers = set(selected["ticker"])
    selected_universe = universe.loc[universe["ticker"].isin(selected_tickers)].merge(selected, on="ticker")
    eligible_catalog = catalog.loc[catalog["ticker"].isin(selected_tickers)].copy()
    eligible_catalog["collection_priority"] = eligible_catalog.apply(
        lambda row: hashlib.sha256(f'{row["ticker"]}:{row["accession_number"]}'.encode()).hexdigest(), axis=1,
    )
    selected_catalog = (
        eligible_catalog.sort_values(["ticker", "collection_priority"])
        .groupby("ticker", group_keys=False)
        .head(protocol["collection_filings_per_ticker"])
        .drop(columns="collection_priority")
        .sort_values(["accepted_at", "ticker", "accession_number"])
        .reset_index(drop=True)
    )
    report = {
        "report_version": "herd-sec-guidance-expansion-corpus-v3",
        "candidate_tickers": len(universe),
        "selected_tickers": len(selected_universe),
        "eligible_filings_before_deterministic_sample": len(eligible_catalog),
        "selected_filings": len(selected_catalog),
        "filings_per_ticker": protocol["collection_filings_per_ticker"],
        "minimum_eligible_filings": int(selected["eligible_filings"].min()) if not selected.empty else 0,
        "selection_used_guidance_text": False,
        "selection_used_price_outcomes": False,
        "base_catalog_report": base_report,
    }
    return selected_universe, selected_catalog, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--collect-snapshot-id")
    parser.add_argument("--output-root", type=Path, default=Path("data/reference/sec"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--seed-corpus", type=Path)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    universe, catalog, report = select_expansion(protocol)
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
            catalog, runtime, args.output_root, args.collect_snapshot_id,
            resolve_user_agent(args.env_file),
            args.seed_corpus,
        ))


if __name__ == "__main__":
    main()
