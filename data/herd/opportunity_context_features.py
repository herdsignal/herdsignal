"""가격 후보에 SEC PIT 기업 불일치와 시점 이전 시장·섹터 국면을 연결한다."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

from herd.profit_take_measurements_v2 import expanding_percentile
from herd.validation_universe import TICKER_SECTOR_ETF


CONTRACT_PATH = Path(__file__).with_name("opportunity_context_features_v1.json")


def load_contract(path: Path = CONTRACT_PATH) -> tuple[dict, dict]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("feature_version") != "HERD_OPPORTUNITY_CONTEXT_FEATURES_V1" \
            or contract.get("status") != "LOCKED_BEFORE_V3_OOS_RESULTS":
        raise ValueError("context feature contract is not locked")
    if contract.get("missing_policy", {}).get("missing_business") != "UNKNOWN_NOT_ZERO" \
            or "USE_POST_SIGNAL_DATA" not in contract.get("forbidden", []):
        raise ValueError("unsafe context feature contract")
    return contract, {"feature_version": contract["feature_version"], "locked": True}


def build_market_history(spy: pd.DataFrame) -> pd.DataFrame:
    frame = spy.sort_values("Date").set_index("Date")
    close = frame["Adj Close"]
    returns = close.pct_change(fill_method=None)
    volatility = returns.rolling(63).std(ddof=1) * np.sqrt(252)
    output = pd.DataFrame(index=frame.index)
    output["market_volatility_percentile"] = expanding_percentile(volatility, minimum_history=756)
    output["market_drawdown_63d"] = close / close.rolling(63).max() - 1
    prior_drawdown = output["market_drawdown_63d"].shift(21)
    output["market_rebound_after_stress"] = ((close.pct_change(21, fill_method=None) > 0) & (prior_drawdown <= -0.10)).astype(float)
    output["spy_return_63d"] = close.pct_change(63, fill_method=None)
    return output


def _latest_business(business: pd.DataFrame, ticker: str, date: pd.Timestamp) -> pd.Series | None:
    rows = business[(business["ticker"] == ticker) & (business["month_end"] <= date)]
    return rows.sort_values("month_end").iloc[-1] if not rows.empty else None


def build_context_features(
    price_features: pd.DataFrame,
    business: pd.DataFrame,
    spy: pd.DataFrame,
    sector_frames: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    price_features = price_features.copy()
    price_features["signal_date"] = pd.to_datetime(price_features["signal_date"])
    business = business.copy()
    business["month_end"] = pd.to_datetime(business["month_end"])
    market = build_market_history(spy)
    rows = []
    for event in price_features.itertuples(index=False):
        signal = pd.Timestamp(event.signal_date)
        market_rows = market.loc[market.index <= signal]
        sector = sector_frames[TICKER_SECTOR_ETF[event.ticker]].sort_values("Date").set_index("Date")["Adj Close"]
        sector_rows = sector.loc[sector.index <= signal]
        business_row = _latest_business(business, event.ticker, signal)
        if market_rows.empty or len(sector_rows) < 64:
            continue
        context = market_rows.iloc[-1]
        flag_count = np.nan if business_row is None or business_row["guard_state"] == "UNKNOWN" else float(business_row["flag_count"])
        rows.append(event._asdict() | {
            "business_state": "UNKNOWN" if business_row is None else business_row["guard_state"],
            "business_entity_type": "UNKNOWN" if business_row is None else business_row["entity_type"],
            "business_deterioration_count": flag_count,
            "business_unknown": float(not np.isfinite(flag_count)),
            "price_business_divergence": (
                max(float(event.capital_gain_overhang_proxy), 0.0) * flag_count / 4.0
                if np.isfinite(flag_count) else np.nan
            ),
            "market_volatility_percentile": context["market_volatility_percentile"],
            "market_drawdown_63d": context["market_drawdown_63d"],
            "market_rebound_after_stress": context["market_rebound_after_stress"],
            "sector_relative_return_63d": float(
                sector_rows.iloc[-1] / sector_rows.iloc[-64] - 1 - context["spy_return_63d"]
            ),
        })
    return pd.DataFrame(rows)


def _load_frames(snapshot: Path) -> dict[str, pd.DataFrame]:
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    frames = {}
    for ticker, item in manifest["files"].items():
        with gzip.open(snapshot / item["path"], "rt", encoding="utf-8") as stream:
            frames[ticker] = pd.read_csv(stream, parse_dates=["Date"])
    return frames


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--price-features", type=Path, required=True)
    parser.add_argument("--business-features", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load_contract()
    frames = _load_frames(args.snapshot)
    result = build_context_features(
        pd.read_csv(args.price_features), pd.read_csv(args.business_features), frames["SPY"], frames
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)
    print(json.dumps({"rows": len(result), "business_unknown": int(result["business_unknown"].sum())}, indent=2))


if __name__ == "__main__":
    main()
