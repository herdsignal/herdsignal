"""Opportunity Cycle 후보의 시점 이전 상승 품질·집중·가격경로 feature를 만든다."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

from herd.validation_universe import TICKER_SECTOR_ETF


CONTRACT_PATH = Path(__file__).with_name("opportunity_price_features_v1.json")


def load_contract(path: Path = CONTRACT_PATH) -> tuple[dict, dict]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("feature_version") != "HERD_OPPORTUNITY_PRICE_FEATURES_V1" \
            or contract.get("status") != "LOCKED_BEFORE_V3_OOS_RESULTS":
        raise ValueError("opportunity price feature contract is not locked")
    if contract.get("availability") != "SIGNAL_DATE_OR_EARLIER_ONLY" \
            or contract.get("adjustment", {}).get("capital_gain_overhang_is_proxy") is not True:
        raise ValueError("unsafe price feature contract")
    return contract, {"feature_version": contract["feature_version"], "locked": True}


def _trend_quality(close: pd.Series) -> float:
    values = np.log(close.to_numpy(dtype=float))
    x = np.arange(len(values), dtype=float)
    slope, intercept = np.polyfit(x, values, 1)
    fitted = intercept + slope * x
    total = float(np.square(values - values.mean()).sum())
    r_squared = 1.0 - float(np.square(values - fitted).sum()) / total if total > 0 else 0.0
    return float(max(0.0, r_squared) if slope > 0 else 0.0)


def calculate_price_features_at(
    stock: pd.DataFrame,
    sector: pd.DataFrame,
    signal_date: pd.Timestamp,
) -> dict | None:
    stock = stock[stock["Date"] <= signal_date].sort_values("Date")
    sector = sector[sector["Date"] <= signal_date].sort_values("Date")
    if len(stock) < 127 or len(sector) < 64:
        return None
    stock = stock.tail(127).copy()
    factor = stock["Adj Close"] / stock["Close"].replace(0, np.nan)
    adjusted_open = stock["Open"] * factor
    adjusted_close = stock["Adj Close"]
    daily_return = adjusted_close.pct_change(fill_method=None)
    positive = daily_return.tail(126).clip(lower=0).dropna()
    positive_sum = float(positive.sum())
    concentration = float(positive.nlargest(5).sum() / positive_sum) if positive_sum > 0 else np.nan

    intraday = np.log(adjusted_close / adjusted_open)
    overnight = np.log(adjusted_open / adjusted_close.shift(1))
    denominator = float(intraday.tail(63).abs().sum() + overnight.tail(63).abs().sum())
    intraday_share = float(intraday.tail(63).sum() / denominator) if denominator > 0 else np.nan
    overnight_share = float(overnight.tail(63).sum() / denominator) if denominator > 0 else np.nan

    volume_window = stock.tail(126)
    volume_sum = float(volume_window["Volume"].sum())
    reference = float((volume_window["Adj Close"] * volume_window["Volume"]).sum() / volume_sum) if volume_sum > 0 else np.nan
    overhang = float(volume_window["Adj Close"].iloc[-1] / reference - 1) if reference > 0 else np.nan

    sector_returns = sector.set_index("Date")["Adj Close"].pct_change(fill_method=None).tail(63)
    stock_returns = stock.set_index("Date")["Adj Close"].pct_change(fill_method=None).tail(63)
    aligned = pd.concat([stock_returns.rename("stock"), sector_returns.rename("sector")], axis=1).dropna()
    alignment = float(aligned["stock"].corr(aligned["sector"])) if len(aligned) >= 40 else np.nan
    return {
        "trend_quality": _trend_quality(stock.tail(126)["Adj Close"]),
        "sector_alignment": alignment,
        "return_concentration": concentration,
        "intraday_return_share": intraday_share,
        "overnight_return_share": overnight_share,
        "capital_gain_overhang_proxy": overhang,
    }


def build_price_features(paths: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for event in paths.itertuples(index=False):
        result = calculate_price_features_at(
            frames[event.ticker], frames[TICKER_SECTOR_ETF[event.ticker]], pd.Timestamp(event.signal_date)
        )
        if result is not None:
            rows.append(event._asdict() | result)
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
    parser.add_argument("--paths", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load_contract()
    result = build_price_features(pd.read_csv(args.paths), _load_frames(args.snapshot))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)
    print(json.dumps({"rows": len(result), "tickers": result["ticker"].nunique()}, indent=2))


if __name__ == "__main__":
    main()
