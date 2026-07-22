"""V5 parser 검증 전용으로 섹터 균형 미검수 기업과 적격 8-K를 고정한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from herd.sec_8k_guidance_corpus_v1 import build_catalog, collect_documents
from herd.sec_master_index import resolve_user_agent


PROTOCOL = Path(__file__).with_suffix(".json")


def _priority(ticker: str, purpose: str) -> str:
    return hashlib.sha256(f"{purpose}:{ticker}".encode()).hexdigest()


def select_metadata_universe(protocol: dict) -> tuple[pd.DataFrame, dict]:
    source = pd.read_csv(protocol["candidate_universe"], dtype={"cik": str})
    source = source.loc[source["eligible"].eq(True) & source["cik"].notna()].copy()
    excluded = set()
    for path in [*protocol["exclude_universes"], *protocol["review_ledgers"]]:
        excluded.update(pd.read_csv(path)["ticker"].astype(str))
    source = source.loc[~source["ticker"].astype(str).isin(excluded)].copy()
    source["selection_priority"] = source["ticker"].map(lambda value: _priority(str(value), "V5_METADATA"))
    groups = [group.sort_values("selection_priority") for _, group in source.groupby("gics_sector", sort=True)]
    selected: list[int] = []
    cursors = [0] * len(groups)
    while len(selected) < min(protocol["metadata_target_tickers"], len(source)):
        added = False
        for group_index, group in enumerate(groups):
            if cursors[group_index] >= len(group):
                continue
            selected.append(group.index[cursors[group_index]])
            cursors[group_index] += 1
            added = True
            if len(selected) >= protocol["metadata_target_tickers"]:
                break
        if not added:
            break
    output = source.loc[selected, ["ticker", "cik", "gics_sector"]].copy()
    output["cik"] = output["cik"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(10)
    output["cik_link_status"] = "UNIQUE_CIK_NAME_CANDIDATE"
    output = output.sort_values("ticker").reset_index(drop=True)
    return output, {
        "eligible_unseen_tickers": len(source),
        "selected_metadata_tickers": len(output),
        "selected_sectors": int(output["gics_sector"].nunique()),
        "selection_used_guidance_text": False,
        "selection_used_parser_output": False,
        "selection_used_price_outcomes": False,
        "scope": protocol["scope"],
    }


def select_filing_universe(protocol: dict, metadata_universe: Path, submission_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    runtime = dict(protocol)
    runtime["universe"] = str(metadata_universe)
    runtime["submission_roots"] = [str(submission_root)]
    catalog, base_report = build_catalog(runtime)
    counts = catalog.groupby("ticker").size().rename("eligible_filings").reset_index()
    counts = counts.loc[counts["eligible_filings"] >= protocol["minimum_eligible_filings_per_ticker"]].copy()
    counts["selection_priority"] = counts["ticker"].map(lambda value: _priority(str(value), "V5_FILINGS"))
    metadata = pd.read_csv(metadata_universe, dtype={"cik": str})
    eligible = metadata.merge(counts, on="ticker", validate="one_to_one")
    eligible = eligible.sort_values(["eligible_filings", "selection_priority"], ascending=[False, True])
    selected = eligible.head(protocol["filing_target_tickers"]).copy()
    selected_tickers = set(selected["ticker"])
    sampled = catalog.loc[catalog["ticker"].isin(selected_tickers)].copy()
    sampled["selection_priority"] = sampled.apply(
        lambda row: _priority(f'{row["ticker"]}:{row["accession_number"]}', "V5_ACCESSION"), axis=1,
    )
    sampled = (
        sampled.sort_values(["ticker", "selection_priority"])
        .groupby("ticker", group_keys=False)
        .head(protocol["collection_filings_per_ticker"])
        .drop(columns="selection_priority")
        .sort_values(["accepted_at", "ticker", "accession_number"])
        .reset_index(drop=True)
    )
    return selected.drop(columns="selection_priority"), sampled, {
        "metadata_tickers": int(metadata["ticker"].nunique()),
        "eligible_tickers": len(eligible),
        "selected_filing_tickers": len(selected),
        "selected_filings": len(sampled),
        "base_catalog_report": base_report,
        "selection_used_guidance_text": False,
        "selection_used_parser_output": False,
        "selection_used_price_outcomes": False,
        "scope": protocol["scope"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["metadata", "filings"])
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--selected-universe", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--submission-root", type=Path)
    parser.add_argument("--collect-snapshot-id")
    parser.add_argument("--output-root", type=Path, default=Path("data/reference/sec"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if args.stage == "metadata":
        universe, report = select_metadata_universe(protocol)
        universe.to_csv(args.universe, index=False, lineterminator="\n")
    else:
        if not args.catalog or not args.submission_root or not args.selected_universe:
            parser.error("filings stage requires --catalog, --selected-universe and --submission-root")
        universe, catalog, report = select_filing_universe(protocol, args.universe, args.submission_root)
        universe.to_csv(args.selected_universe, index=False, lineterminator="\n")
        catalog.to_csv(args.catalog, index=False, lineterminator="\n")
        if args.collect_snapshot_id:
            runtime = dict(protocol)
            runtime["universe"] = str(args.universe)
            print(collect_documents(catalog, runtime, args.output_root, args.collect_snapshot_id, resolve_user_agent(args.env_file)))
    report["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    report["operational_action_ratio"] = 0.0
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
