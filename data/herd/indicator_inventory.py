"""HERD v4/v6.1 지표 인벤토리와 중복성 감사 도구.

운영 코드에 흩어진 입력을 한곳에 명시하고, point-in-time 방식으로 만든
지표 시계열의 Spearman 상관관계를 이용해 중복 후보를 찾는다.
이 모듈은 모델 점수를 변경하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from collectors.stock_collector import collect
from config.settings import HERD_WEIGHTS
from herd.validation_universe import TICKERS as VALIDATION_TICKERS
from indicators.wilder_rsi import wilder_rsi


@dataclass(frozen=True)
class IndicatorSpec:
    key: str
    model: str
    family: str
    formula: str
    horizon: str
    normalization: str
    weight: float | None
    source: str
    point_in_time_status: str
    operating_status: str
    duplicate_risk: str


V4_INVENTORY = (
    IndicatorSpec("monthly_rsi", "v4 base", "price_momentum", "14-month RSI",
                  "14 months", "expanding own-history percentile",
                  HERD_WEIGHTS["monthly_rsi"], "adjusted OHLCV / yfinance",
                  "available", "active", "high: weekly RSI, price position"),
    IndicatorSpec("weekly_rsi", "v4 base", "price_momentum", "14-week RSI",
                  "14 weeks", "expanding own-history percentile",
                  HERD_WEIGHTS["weekly_rsi"], "adjusted OHLCV / yfinance",
                  "available", "active", "high: monthly RSI, price position"),
    IndicatorSpec("position_52w", "v4 base", "price_position",
                  "(close-252d low)/(252d high-252d low)", "252 trading days",
                  "expanding own-history percentile", HERD_WEIGHTS["52w_position"],
                  "adjusted OHLCV / yfinance", "available", "active",
                  "high: RSI, MA200 deviation"),
    IndicatorSpec("ma200_deviation", "v4 base", "price_trend",
                  "(close/SMA200)-1", "200 trading days",
                  "expanding own-history percentile", HERD_WEIGHTS["ma200_deviation"],
                  "adjusted OHLCV / yfinance", "available", "active",
                  "high: 52w position, weekly MA"),
    IndicatorSpec("volume_strength", "v4 base", "participation",
                  "SMA5(volume)/SMA20(volume)", "5/20 trading days",
                  "expanding own-history percentile", HERD_WEIGHTS["volume_strength"],
                  "adjusted volume / yfinance", "available", "disabled(weight=0)",
                  "low"),
    IndicatorSpec("ma200_weekly", "v4 base", "price_trend",
                  "weekly close/SMA200w", "200 weeks; shorter listing uses available history",
                  "expanding own-history percentile", HERD_WEIGHTS["ma200_weekly"],
                  "adjusted OHLCV / yfinance", "available", "active",
                  "high: MA200 deviation, RSI"),
    IndicatorSpec("eps_multiplier", "v4 multiplier", "fundamental_event",
                  "latest consecutive 2-4 quarterly EPS beats/misses", "latest 4 quarters",
                  "fixed multiplier 0.85-1.15", None, "Finnhub stock/earnings",
                  "unavailable: announcement date absent", "latest score only",
                  "medium: also reused inside v6.1 trend quality"),
    IndicatorSpec("sector_multiplier", "v4 multiplier", "relative_strength",
                  "stock return - sector ETF return", "90 calendar/trading observations",
                  "fixed multiplier 0.90-1.10", None, "yfinance + Finnhub sector",
                  "partially available", "latest score only",
                  "medium: reused inside v6.1 trend quality"),
)


V61_INVENTORY = (
    IndicatorSpec("stabilized_herd", "v6.1", "state_stability",
                  "keep previous side within ±2pt boundary crossing", "previous observation",
                  "rule", None, "herd_scores DB", "available", "active",
                  "derived directly from v4"),
    IndicatorSpec("trend_quality", "v6.1", "price_trend",
                  "MA200w + MA200 deviation + 52w position + sector + EPS rules",
                  "mixed", "0-100 rule score", None, "herd_indicators DB",
                  "mixed", "active", "very high: reuses five v4 inputs"),
    IndicatorSpec("herd_momentum", "v6.1", "score_momentum",
                  "HERD 5d/20d change and acceleration", "5/20 calendar days",
                  "threshold score 15/30/50/70/85", None, "herd_scores DB",
                  "available", "active", "very high: derivative of v4"),
    IndicatorSpec("lifecycle", "v6.1", "state_duration",
                  "same signal duration buckets 1-5/6-20/21-45/>45d", "1-45+ days",
                  "ratio multiplier 0.65/1.0/0.82/0.55", None, "herd_scores DB",
                  "available", "active", "medium: derived from v4 stage"),
    IndicatorSpec("data_quality", "v6.1", "reliability",
                  "freshness/completeness quality score", "latest data",
                  "ratio gate", None, "service data checks", "available", "active gate",
                  "not directional; must stay outside HERD"),
    IndicatorSpec("investor_profile", "v6.1", "personal",
                  "strategy/risk/horizon/liquidity limits", "user setting",
                  "ratio cap", None, "user DB", "not market data", "active",
                  "must stay outside HERD"),
    IndicatorSpec("portfolio_context", "v6.1", "personal",
                  "holding/target/cash context", "current portfolio",
                  "ratio cap", None, "user DB", "not market data", "active",
                  "must stay outside HERD"),
    IndicatorSpec("cooldown", "v6.1", "execution",
                  "recent same-direction action limit", "recent actions",
                  "ratio gate", None, "signal journal DB", "available", "active",
                  "execution rule, not HERD evidence"),
)


def inventory() -> list[dict]:
    return [asdict(item) for item in (*V4_INVENTORY, *V61_INVENTORY)]


def _expanding_percentile(series: pd.Series, min_periods: int) -> pd.Series:
    """현재값의 과거 포함 백분위. 미래 관측값을 사용하지 않는다."""
    return series.expanding(min_periods=min_periods).apply(
        lambda values: pd.Series(values).rank(pct=True).iloc[-1] * 100.0,
        raw=False,
    )


def build_v4_indicator_frame(df: pd.DataFrame) -> pd.DataFrame:
    """OHLCV에서 v4 가격 지표와 같은 의미의 PIT 감사 시계열을 만든다."""
    data = df.copy()
    if "Date" in data.columns:
        data["Date"] = pd.to_datetime(data["Date"])
        data = data.set_index("Date")
    data.index = pd.to_datetime(data.index)
    data = data.sort_index()

    close = data["Close"].astype(float)
    high = data["High"].astype(float)
    low = data["Low"].astype(float)
    volume = data["Volume"].astype(float)

    weekly_close = close.resample("W").last().dropna()
    monthly_close = close.resample("ME").last().dropna()
    weekly_rsi_raw = wilder_rsi(weekly_close, 14)
    monthly_rsi_raw = wilder_rsi(monthly_close, 14)

    weekly_rsi = _expanding_percentile(weekly_rsi_raw, 14).reindex(data.index, method="ffill")
    monthly_rsi = _expanding_percentile(monthly_rsi_raw, 14).reindex(data.index, method="ffill")

    range_52w = high.rolling(252).max() - low.rolling(252).min()
    raw_52w = (close - low.rolling(252).min()) / range_52w.replace(0, float("nan"))
    position_52w = _expanding_percentile(raw_52w, 20)

    ma200 = close.rolling(200).mean()
    raw_ma200_dev = close / ma200.replace(0, float("nan")) - 1.0
    ma200_deviation = _expanding_percentile(raw_ma200_dev, 20)

    raw_volume = volume.rolling(5).mean() / volume.rolling(20).mean().replace(0, float("nan"))
    volume_strength = _expanding_percentile(raw_volume, 20)

    weekly_ma200 = weekly_close.rolling(200).mean()
    raw_weekly_ma = weekly_close / weekly_ma200.replace(0, float("nan"))
    ma200_weekly = _expanding_percentile(raw_weekly_ma, 20).reindex(data.index, method="ffill")

    return pd.DataFrame({
        "monthly_rsi": monthly_rsi,
        "weekly_rsi": weekly_rsi,
        "position_52w": position_52w,
        "ma200_deviation": ma200_deviation,
        "volume_strength": volume_strength,
        "ma200_weekly": ma200_weekly,
    }).dropna(how="all")


def correlation_audit(frame: pd.DataFrame, threshold: float = 0.70) -> dict:
    usable = frame.dropna()
    correlation = usable.corr(method="spearman")
    pairs: list[dict] = []
    columns = list(correlation.columns)
    for left_index, left in enumerate(columns):
        for right in columns[left_index + 1:]:
            value = float(correlation.loc[left, right])
            if abs(value) >= threshold:
                pairs.append({
                    "left": left,
                    "right": right,
                    "spearman": round(value, 4),
                    "severity": "critical" if abs(value) >= 0.85 else "high",
                })
    pairs.sort(key=lambda item: abs(item["spearman"]), reverse=True)
    return {
        "observations": int(len(usable)),
        "threshold": threshold,
        "correlation": correlation.round(4).to_dict(),
        "duplicate_candidates": pairs,
    }


def run(tickers: list[str], period: str, threshold: float) -> dict:
    ticker_reports: dict[str, dict] = {}
    combined: list[pd.DataFrame] = []
    failures: dict[str, str] = {}
    for ticker in tickers:
        try:
            frame = build_v4_indicator_frame(collect(ticker, period=period))
            ticker_reports[ticker] = correlation_audit(frame, threshold)
            combined.append(frame.assign(ticker=ticker).set_index("ticker", append=True))
        except Exception as exc:  # CLI audit must report every unavailable ticker
            failures[ticker] = str(exc)

    pooled = correlation_audit(pd.concat(combined).reset_index(level="ticker", drop=True), threshold) if combined else None
    return {
        "inventory": inventory(),
        "settings": {"period": period, "threshold": threshold, "tickers": tickers},
        "ticker_reports": ticker_reports,
        "pooled_report": pooled,
        "failures": failures,
        "limitations": [
            "correlation frame audits price-derived v4 inputs only",
            "EPS and sector multipliers require point-in-time histories and are excluded",
            "weekly MA audit starts after a full 200-week history; production short-history fallback is separately flagged",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tickers",
        help="comma-separated tickers; omitted means the fixed 55-ticker validation universe",
    )
    parser.add_argument("--period", default="10y")
    parser.add_argument("--threshold", type=float, default=0.70)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    tickers = (
        [ticker.strip().upper() for ticker in args.tickers.split(",") if ticker.strip()]
        if args.tickers else VALIDATION_TICKERS
    )
    report = run(tickers, args.period, args.threshold)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
