"""기업 자체 과거 대비 밸류에이션·기대 확장을 측정한다."""

from __future__ import annotations

import argparse
import gzip
import json
from datetime import date, datetime, time, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from herd.expectation_business_features_v1 import _share_facts
from herd.sec_price_fold_link import _load_cik_facts


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")


def load_protocol(path: Path = PROTOCOL_PATH) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_MEASUREMENT_OUTPUT":
        raise ValueError("valuation expectation protocol must be locked")
    if "EXPENSIVE_ALONE_CREATES_SELL" not in protocol.get("forbidden", []):
        raise ValueError("valuation action boundary weakened")
    return protocol


def shares_as_of(facts: list[dict], as_of: datetime) -> float | None:
    visible = [row for row in facts if row["accepted_at"] <= as_of and row["period_end"] <= as_of.date()]
    if not visible:
        return None
    latest = max(visible, key=lambda row: (row["period_end"], -row["priority"], row["accepted_at"]))
    return float(latest["value"])


def prior_window_percentile(values: pd.Series, window: int = 60, minimum: int = 36) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    result = pd.Series(np.nan, index=values.index, dtype=float)
    for position, current in enumerate(numeric):
        history = numeric.iloc[max(0, position - window):position].dropna()
        if pd.notna(current) and len(history) >= minimum:
            result.iloc[position] = float((history <= current).mean())
    return result


def _monthly_prices(snapshot: Path, tickers: set[str]) -> pd.DataFrame:
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    rows = []
    for ticker in sorted(tickers):
        item = manifest["files"].get(ticker)
        if not item:
            continue
        with gzip.open(snapshot / item["path"], "rt", encoding="utf-8") as stream:
            frame = pd.read_csv(stream, parse_dates=["Date"])
        frame["month_end"] = frame["Date"].dt.to_period("M").dt.to_timestamp("M")
        monthly = frame.sort_values("Date").groupby("month_end").tail(1)
        for _, row in monthly.iterrows():
            rows.append({"ticker": ticker, "month_end": row["month_end"], "adjusted_close": row["Adj Close"], "unadjusted_close": row["Close"]})
    return pd.DataFrame(rows)


def build(features: pd.DataFrame, protocol: dict) -> tuple[pd.DataFrame, dict]:
    frame = features.copy()
    frame["month_end"] = pd.to_datetime(frame["month_end"])
    tickers = set(frame["ticker"])
    frame = frame.merge(_monthly_prices(ROOT / protocol["price_snapshot"], tickers), on=["ticker", "month_end"], how="left", validate="one_to_one")
    business_protocol = json.loads((ROOT / protocol["business_protocol"]).read_text(encoding="utf-8"))
    corpora = [ROOT / path for path in business_protocol["sec_corpora"]]
    shares = pd.Series(np.nan, index=frame.index, dtype=float)
    for (ticker, cik), group in frame.groupby(["ticker", "cik"], dropna=True):
        raw, _ = _load_cik_facts(corpora, f"{int(cik):010d}", filed_from=date(group.month_end.min().year - 2, 1, 1), filed_to=group.month_end.max().date())
        facts = _share_facts(raw, business_protocol)
        for index, month in group["month_end"].items():
            shares.loc[index] = shares_as_of(facts, datetime.combine(month.date(), time.max, tzinfo=timezone.utc))
    frame["pit_shares"] = shares
    positive_ocf = frame["operating_cash_flow_value"].where(frame["operating_cash_flow_value"] > 0)
    frame["market_cap_to_operating_cash_flow"] = frame["unadjusted_close"] * frame["pit_shares"] / positive_ocf
    frame = frame.sort_values(["ticker", "month_end"]).reset_index(drop=True)
    frame["price_return_12m"] = frame.groupby("ticker")["adjusted_close"].pct_change(12, fill_method=None)
    frame["price_revenue_expectation_gap"] = frame["price_return_12m"] - frame["revenue_yoy"]
    frame["pocf_own_history_percentile"] = frame.groupby("ticker", group_keys=False)["market_cap_to_operating_cash_flow"].apply(prior_window_percentile)
    frame["expectation_gap_own_history_percentile"] = frame.groupby("ticker", group_keys=False)["price_revenue_expectation_gap"].apply(prior_window_percentile)
    measured = ["market_cap_to_operating_cash_flow", "pocf_own_history_percentile", "price_revenue_expectation_gap", "expectation_gap_own_history_percentile"]
    report = {
        "report_version": "HERD_VALUATION_EXPECTATION_EXPANSION_V1", "status": "MEASUREMENTS_READY",
        "rows": len(frame), "tickers": int(frame.ticker.nunique()),
        "coverage": {column: float(frame[column].notna().mean()) for column in measured},
        "measurements": measured, "sell_authority": False, "operational_action_ratio": 0.0,
        "survivorship_safe": False, "claim_boundary": "OWN_HISTORY_PUBLIC_DATA_RESEARCH_ONLY",
    }
    return frame, report


def run(protocol_path: Path = PROTOCOL_PATH) -> tuple[pd.DataFrame, dict]:
    protocol = load_protocol(protocol_path)
    return build(pd.read_csv(ROOT / protocol["business_features"]), protocol)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measurements", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    frame, report = run()
    frame.to_csv(args.measurements, index=False)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
