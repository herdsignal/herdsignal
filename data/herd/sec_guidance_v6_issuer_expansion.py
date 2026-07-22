"""V6 독립 원문 검증용 신규 기업과 8-K accession을 결과 비관측 상태로 고정한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

import pandas as pd

from herd.sec_8k_guidance_corpus_v1 import build_catalog, collect_documents
from herd.sec_master_index import resolve_user_agent


PROTOCOL = Path(__file__).with_suffix(".json")


def _priority(value: str, namespace: str) -> str:
    return hashlib.sha256(f"{namespace}:{value}".encode()).hexdigest()


def _exclusions(protocol: dict) -> tuple[set[str], set[str]]:
    tickers: set[str] = set()
    accessions: set[str] = set()
    for path in protocol["exclude_issuer_universes"]:
        tickers.update(pd.read_csv(path)["ticker"].astype(str))
    for path in protocol["review_ledgers"]:
        review = pd.read_csv(path)
        tickers.update(review["ticker"].astype(str))
        accessions.update(review["accession_number"].astype(str))
    return tickers, accessions


def select_expansion(protocol: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    metadata = pd.read_csv(protocol["locked_metadata_universe"], dtype={"cik": str})
    excluded_tickers, excluded_accessions = _exclusions(protocol)
    unseen = metadata.loc[~metadata["ticker"].astype(str).isin(excluded_tickers)].copy()
    runtime = dict(protocol)
    with tempfile.TemporaryDirectory(prefix="herd-v6-universe-") as directory:
        temporary = Path(directory) / "universe.csv"
        unseen.to_csv(temporary, index=False, lineterminator="\n")
        runtime["universe"] = str(temporary)
        catalog, base_report = build_catalog(runtime)
    catalog = catalog.loc[~catalog["accession_number"].astype(str).isin(excluded_accessions)].copy()
    counts = catalog.groupby("ticker").size().rename("eligible_filings").reset_index()
    counts = counts.loc[counts["eligible_filings"] >= protocol["minimum_eligible_filings_per_ticker"]].copy()
    counts["selection_priority"] = counts["ticker"].map(lambda ticker: _priority(str(ticker), "V6_ISSUER"))
    eligible = unseen.merge(counts, on="ticker", validate="one_to_one")

    # 섹터를 순환한 뒤 고정 해시 순서로 채워 특정 산업 문법에 쏠리지 않게 한다.
    groups = [group.sort_values("selection_priority") for _, group in eligible.groupby("gics_sector", sort=True)]
    selected_indexes: list[int] = []
    cursors = [0] * len(groups)
    while len(selected_indexes) < min(protocol["target_tickers"], len(eligible)):
        added = False
        for position, group in enumerate(groups):
            if cursors[position] >= len(group):
                continue
            selected_indexes.append(group.index[cursors[position]])
            cursors[position] += 1
            added = True
            if len(selected_indexes) >= protocol["target_tickers"]:
                break
        if not added:
            break
    selected = eligible.loc[selected_indexes].drop(columns="selection_priority").sort_values("ticker").reset_index(drop=True)
    selected_tickers = set(selected["ticker"].astype(str))
    sampled = catalog.loc[catalog["ticker"].astype(str).isin(selected_tickers)].copy()
    sampled["selection_priority"] = sampled.apply(
        lambda row: _priority(f'{row["ticker"]}:{row["accession_number"]}', "V6_ACCESSION"), axis=1,
    )
    sampled = (
        sampled.sort_values(["ticker", "selection_priority"])
        .groupby("ticker", group_keys=False)
        .head(protocol["collection_filings_per_ticker"])
        .drop(columns="selection_priority")
        .sort_values(["accepted_at", "ticker", "accession_number"])
        .reset_index(drop=True)
    )
    report = {
        "report_version": "herd-sec-guidance-v6-issuer-expansion-v1",
        "scope": protocol["scope"],
        "locked_metadata_tickers": int(metadata["ticker"].nunique()),
        "excluded_tickers": len(excluded_tickers),
        "excluded_accessions": len(excluded_accessions),
        "unseen_metadata_tickers": int(unseen["ticker"].nunique()),
        "eligible_tickers": len(eligible),
        "selected_tickers": len(selected),
        "selected_sectors": int(selected["gics_sector"].nunique()) if not selected.empty else 0,
        "selected_filings": len(sampled),
        "selection_used_guidance_text": False,
        "selection_used_parser_output": False,
        "selection_used_price_outcomes": False,
        "base_catalog_report": base_report,
        "operational_action_ratio": 0.0,
    }
    return selected, sampled, report


def select_supplement(protocol: dict, collected_universe: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """최초 잠긴 120개 모집단에서 1차 수집에 포함되지 않은 적격 기업만 반환한다."""
    expanded_protocol = dict(protocol)
    expanded_protocol["target_tickers"] = 10_000
    universe, catalog, report = select_expansion(expanded_protocol)
    collected = set(pd.read_csv(collected_universe)["ticker"].astype(str))
    universe = universe.loc[~universe["ticker"].astype(str).isin(collected)].copy()
    catalog = catalog.loc[catalog["ticker"].astype(str).isin(set(universe["ticker"].astype(str)))].copy()
    report.update({
        "report_version": "herd-sec-guidance-v6-issuer-supplement-v1",
        "previously_collected_tickers": len(collected),
        "selected_tickers": int(universe["ticker"].nunique()),
        "selected_sectors": int(universe["gics_sector"].nunique()) if not universe.empty else 0,
        "selected_filings": len(catalog),
    })
    return universe.reset_index(drop=True), catalog.reset_index(drop=True), report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--collect-snapshot-id")
    parser.add_argument("--supplement-after", type=Path)
    parser.add_argument("--output-root", type=Path, default=Path("data/reference/sec"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    universe, catalog, report = (
        select_supplement(protocol, args.supplement_after)
        if args.supplement_after else select_expansion(protocol)
    )
    args.universe.parent.mkdir(parents=True, exist_ok=True)
    universe.to_csv(args.universe, index=False, lineterminator="\n")
    catalog.to_csv(args.catalog, index=False, lineterminator="\n")
    report["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    report["universe_sha256"] = hashlib.sha256(args.universe.read_bytes()).hexdigest()
    report["catalog_sha256"] = hashlib.sha256(args.catalog.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.collect_snapshot_id:
        print(collect_documents(
            catalog, protocol, args.output_root, args.collect_snapshot_id,
            resolve_user_agent(args.env_file),
        ))


if __name__ == "__main__":
    main()
