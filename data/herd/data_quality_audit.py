"""HERD 연구 데이터의 가격·기업행동·PIT·생존자 편향 준비 상태 감사."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from collectors.stock_collector import collect
from herd.point_in_time_universe import audit_survivorship_coverage, load_universe_history
from herd.validation_universe import TICKERS, UNIVERSE_VERSION

REQUIRED_PRICE_COLUMNS = ("Date", "Open", "High", "Low", "Close", "Volume")
OHLC_RELATIVE_TOLERANCE = 1e-8


def audit_price_frame(
    df: pd.DataFrame,
    *,
    as_of: date,
    minimum_rows: int = 1_000,
    maximum_staleness_days: int = 7,
) -> dict[str, Any]:
    missing_columns = [column for column in REQUIRED_PRICE_COLUMNS if column not in df.columns]
    if missing_columns:
        return {
            "status": "FAILED",
            "passed": False,
            "missing_columns": missing_columns,
            "rows": len(df),
        }

    data = df.loc[:, REQUIRED_PRICE_COLUMNS].copy()
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    numeric_columns = ["Open", "High", "Low", "Close", "Volume"]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    duplicate_dates = int(data["Date"].duplicated().sum())
    invalid_dates = int(data["Date"].isna().sum())
    null_cells = int(data[numeric_columns].isna().sum().sum())
    nonpositive_prices = int((data[["Open", "High", "Low", "Close"]] <= 0).sum().sum())
    negative_volume = int((data["Volume"] < 0).sum())
    zero_volume_ratio = float((data["Volume"] == 0).mean()) if len(data) else 1.0
    tolerance = data["Close"].abs().clip(lower=1.0) * OHLC_RELATIVE_TOLERANCE
    invalid_ohlc = int((
        (data["High"] + tolerance < data["Low"])
        | (data["High"] + tolerance < data[["Open", "Close"]].max(axis=1))
        | (data["Low"] - tolerance > data[["Open", "Close"]].min(axis=1))
    ).sum())
    ordered = bool(data["Date"].is_monotonic_increasing)
    dated = data.dropna(subset=["Date"]).sort_values("Date")
    maximum_gap_days = (
        int(dated["Date"].diff().dt.days.max())
        if len(dated) >= 2 else None
    )
    latest = dated["Date"].max().date() if len(dated) else None
    staleness_days = (as_of - latest).days if latest else None

    checks = {
        "minimum_rows": len(data) >= minimum_rows,
        "valid_dates": invalid_dates == 0,
        "unique_dates": duplicate_dates == 0,
        "chronological": ordered,
        "complete_ohlcv": null_cells == 0,
        "positive_prices": nonpositive_prices == 0,
        "valid_ohlc_bounds": invalid_ohlc == 0,
        "valid_volume": negative_volume == 0 and zero_volume_ratio <= 0.05,
        "fresh": staleness_days is not None and staleness_days <= maximum_staleness_days,
    }
    passed = all(checks.values())
    return {
        "status": "PASSED" if passed else "FAILED",
        "passed": passed,
        "rows": len(data),
        "start_date": dated["Date"].min().date().isoformat() if len(dated) else None,
        "end_date": latest.isoformat() if latest else None,
        "staleness_days": staleness_days,
        "maximum_gap_days": maximum_gap_days,
        "duplicate_dates": duplicate_dates,
        "invalid_dates": invalid_dates,
        "null_cells": null_cells,
        "nonpositive_prices": nonpositive_prices,
        "invalid_ohlc_rows": invalid_ohlc,
        "negative_volume_rows": negative_volume,
        "zero_volume_ratio": zero_volume_ratio,
        "checks": checks,
    }


def build_data_quality_report(
    price_reports: dict[str, dict[str, Any]],
    *,
    universe_history_path: Path,
    fixed_tickers: list[str],
) -> dict[str, Any]:
    records = load_universe_history(universe_history_path)
    survivorship = audit_survivorship_coverage(records, fixed_tickers)
    passed_prices = sum(report.get("passed") is True for report in price_reports.values())
    requested = len(fixed_tickers)
    price_coverage = passed_prices / requested if requested else 0.0

    corporate_actions = {
        "auto_adjusted_prices": True,
        "split_adjusted_returns_supported": True,
        "dividend_total_return_approximation_supported": True,
        "raw_close_preserved": False,
        "explicit_dividend_cashflows_preserved": False,
        "split_events_preserved": False,
        "status": "ADJUSTED_ONLY_NOT_AUDITABLE",
    }
    fundamentals = {
        "trusted_earnings_dataset_present": False,
        "announcement_dates_verified": False,
        "historical_consensus_verified": False,
        "restatement_safe": False,
        "status": "PIT_FUNDAMENTALS_NOT_READY",
    }
    price_ready = price_coverage >= 0.95
    pit_ready = survivorship["point_in_time_ready"] and fundamentals["trusted_earnings_dataset_present"]
    blocking_findings = [
        finding for finding in [
            "historical constituent file contains no records" if not records else None,
            "trusted point-in-time earnings and consensus dataset is absent",
            "adjusted OHLCV does not preserve explicit dividends, splits, or raw close",
        ] if finding
    ]
    return {
        "audit_version": "2026.07-v1",
        "universe_version": UNIVERSE_VERSION,
        "price_summary": {
            "requested_tickers": requested,
            "passed_tickers": passed_prices,
            "coverage": price_coverage,
            "status": "PRICE_READY" if price_ready else "PRICE_NOT_READY",
        },
        "price_reports": price_reports,
        "corporate_actions": corporate_actions,
        "fundamentals": fundamentals,
        "survivorship_coverage": survivorship,
        "readiness": {
            "price_only_research_ready": price_ready,
            "buy_hold_total_return_attribution_ready": False,
            "point_in_time_fundamental_model_ready": False,
            "survivorship_safe_validation_ready": pit_ready,
            "status": "PARTIAL_PRICE_ONLY" if price_ready and not pit_ready else (
                "FULL_PIT_READY" if price_ready and pit_ready else "NOT_READY"
            ),
        },
        "blocking_findings": blocking_findings,
    }


def run(period: str = "10y", as_of: date | None = None) -> dict[str, Any]:
    audit_date = as_of or date.today()
    reports: dict[str, dict[str, Any]] = {}
    for ticker in TICKERS:
        try:
            reports[ticker] = audit_price_frame(collect(ticker, period=period), as_of=audit_date)
        except Exception as exc:
            reports[ticker] = {"status": "COLLECTION_FAILED", "passed": False, "error": str(exc)}
    return build_data_quality_report(
        reports,
        universe_history_path=_DATA_DIR / "herd" / "universe_history.csv",
        fixed_tickers=TICKERS,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--period", default="10y")
    parser.add_argument("--as-of", type=date.fromisoformat)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run(args.period, args.as_of)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
