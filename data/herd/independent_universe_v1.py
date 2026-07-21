"""현재 S&P 500 공개 목록에서 기존 검증군과 겹치지 않는 독립 연구군을 고정한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from herd.long_price_snapshot import create_snapshot, verify_snapshot
from herd.validation_universe import TICKER_SECTOR_ETF


SOURCE_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
OFFICIAL_METHODOLOGY_URL = "https://www.spglobal.com/spdji/en/methodology/article/sp-us-indices-methodology/"
CONTEXT_ONLY = {"SPY", "QQQ", "DIA", "IWM"}
SECTOR_ETF = {
    "Communication Services": "XLC",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Industrials": "XLI",
    "Information Technology": "XLK",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
}
MINIMUM_ROWS = 3000
MAXIMUM_START = pd.Timestamp("2012-03-01")
MINIMUM_END = pd.Timestamp("2026-07-10")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_ticker(value: str) -> str:
    """Yahoo Finance 표기와 일치하도록 미국 주식 클래스 구분점을 변환한다."""
    return str(value).strip().upper().replace(".", "-")


def fetch_source(output: Path) -> dict:
    request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "HerdSignal personal research"})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed HTTPS source
        payload = response.read()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    return {
        "url": SOURCE_URL,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "bytes": len(payload),
        "sha256": sha256(output),
    }


def load_candidates(source: Path) -> pd.DataFrame:
    frame = pd.read_csv(source, dtype={"CIK": str})
    required = {"Symbol", "Security", "GICS Sector", "CIK"}
    if not required.issubset(frame.columns):
        raise ValueError(f"constituent source missing columns: {sorted(required - set(frame.columns))}")
    frame = frame.rename(columns={
        "Symbol": "source_ticker",
        "Security": "company",
        "GICS Sector": "gics_sector",
        "CIK": "cik",
    })
    frame["ticker"] = frame["source_ticker"].map(normalize_ticker)
    frame["sector_etf"] = frame["gics_sector"].map(SECTOR_ETF)
    if frame["ticker"].duplicated().any() or frame["sector_etf"].isna().any():
        raise ValueError("duplicate ticker or unsupported GICS sector")
    excluded = set(TICKER_SECTOR_ETF) - CONTEXT_ONLY
    frame["excluded_original_universe"] = frame["ticker"].isin(excluded)
    return frame.sort_values("ticker").reset_index(drop=True)


def audit_snapshot(candidates: pd.DataFrame, snapshot: Path) -> tuple[pd.DataFrame, dict]:
    manifest = verify_snapshot(snapshot)
    rows = []
    for candidate in candidates.itertuples(index=False):
        metadata = manifest["files"].get(candidate.ticker)
        reasons = []
        if candidate.excluded_original_universe:
            reasons.append("ORIGINAL_51_OVERLAP")
        if metadata is None:
            reasons.append("PRICE_NOT_COLLECTED")
            start = end = None
            count = 0
        else:
            start, end, count = metadata["start"], metadata["end"], int(metadata["rows"])
            if count < MINIMUM_ROWS:
                reasons.append("INSUFFICIENT_SESSIONS")
            if pd.Timestamp(start) > MAXIMUM_START:
                reasons.append("HISTORY_START_TOO_LATE")
            if pd.Timestamp(end) < MINIMUM_END:
                reasons.append("STALE_PRICE_END")
        rows.append({
            "ticker": candidate.ticker,
            "source_ticker": candidate.source_ticker,
            "company": candidate.company,
            "cik": candidate.cik,
            "gics_sector": candidate.gics_sector,
            "sector_etf": candidate.sector_etf,
            "price_rows": count,
            "price_start": start,
            "price_end": end,
            "eligible": not reasons,
            "rejection_reasons": "|".join(reasons),
        })
    audit = pd.DataFrame(rows)
    eligible = audit[audit["eligible"]]
    report = {
        "report_version": "HERD_INDEPENDENT_UNIVERSE_V1",
        "status": "CURRENT_CONSTITUENTS_ROBUSTNESS_ONLY",
        "claim_boundary": "not point-in-time membership and not survivorship safe",
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_sha256": manifest["snapshot_sha256"],
        "candidate_rows": int(len(audit)),
        "original_universe_overlap": int(audit["rejection_reasons"].str.contains("ORIGINAL_51_OVERLAP").sum()),
        "eligible_tickers": int(len(eligible)),
        "minimum_target_met": bool(len(eligible) >= 100),
        "preferred_target_met": bool(len(eligible) >= 200),
        "sector_counts": eligible["gics_sector"].value_counts().sort_index().to_dict(),
        "criteria": {
            "minimum_price_rows": MINIMUM_ROWS,
            "maximum_history_start": MAXIMUM_START.date().isoformat(),
            "minimum_price_end": MINIMUM_END.date().isoformat(),
            "original_51_excluded": True,
            "current_gics_sector_etf_mapping_fixed": True,
        },
        "policy": {
            "operational_action_authority": False,
            "blind_holdout_access": False,
            "survivorship_safe": False,
        },
    }
    return audit, report


def source_manifest(source: Path, retrieval: dict | None = None) -> dict:
    frame = load_candidates(source)
    return {
        "manifest_version": "HERD_CURRENT_SP500_SOURCE_V1",
        "source": retrieval or {"url": SOURCE_URL, "sha256": sha256(source)},
        "official_methodology_url": OFFICIAL_METHODOLOGY_URL,
        "rows": int(len(frame)),
        "normalized_tickers": frame["ticker"].tolist(),
        "sector_etf_mapping": SECTOR_ETF,
        "scope": "PUBLIC_RESEARCH_ONLY_CURRENT_CONSTITUENTS",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch-source")
    fetch.add_argument("--output", type=Path, required=True)
    fetch.add_argument("--manifest-output", type=Path, required=True)
    audit = sub.add_parser("audit-snapshot")
    audit.add_argument("--source", type=Path, required=True)
    audit.add_argument("--snapshot", type=Path, required=True)
    audit.add_argument("--audit-output", type=Path, required=True)
    audit.add_argument("--report-output", type=Path, required=True)
    create = sub.add_parser("create-snapshot")
    create.add_argument("--source", type=Path, required=True)
    create.add_argument("--snapshot-id", required=True)
    create.add_argument("--root", type=Path, required=True)
    create.add_argument("--start", type=date.fromisoformat, required=True)
    create.add_argument("--end", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    if args.command == "fetch-source":
        retrieval = fetch_source(args.output)
        manifest = source_manifest(args.output, retrieval)
        args.manifest_output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    elif args.command == "audit-snapshot":
        candidates = load_candidates(args.source)
        rows, report = audit_snapshot(candidates, args.snapshot)
        args.audit_output.parent.mkdir(parents=True, exist_ok=True)
        rows.to_csv(args.audit_output, index=False)
        args.report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        candidates = load_candidates(args.source)
        independent = candidates[~candidates["excluded_original_universe"]]["ticker"].tolist()
        path = create_snapshot(
            args.snapshot_id,
            start=args.start,
            end=args.end,
            equities=independent,
            sector_etfs=tuple(SECTOR_ETF.values()),
            root=args.root,
            allow_equity_failures=True,
        )
        print(path)


if __name__ == "__main__":
    main()
