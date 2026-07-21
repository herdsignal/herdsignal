"""Python v6.1 재현 규칙의 행동 빈도와 사후 가격 경로를 감사한다.

이 모듈은 Java Action Layer의 동등성 구현이 아니다. 기존 연구 재현본이 실제로
어떤 시점에 행동했고, 행동하지 않았을 때 가격 경로가 어땠는지를 고정 스냅샷에서
측정하는 기준선 진단이다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from herd.indicator_inventory import build_v4_indicator_frame
from herd.legacy_model_evaluation import v4_base_score, v61_actions
from herd.long_price_snapshot import verify_snapshot
from herd.validation_universe import SECTOR_UNIVERSE, TICKER_SECTOR_ETF, UNIVERSE_VERSION


CONTEXT_ONLY = {"SPY", "QQQ", "DIA", "IWM"}
HORIZONS = {"1m": 21, "3m": 63, "6m": 126}
EARLY_SELL_CASES = {"NVDA", "AVGO", "LLY"}


def equity_universe() -> list[str]:
    """검증 표본에서 시장 문맥 ETF를 제외한 51개 기업만 반환한다."""
    return sorted(set(TICKER_SECTOR_ETF) - CONTEXT_ONLY)


def forward_path(close: pd.Series, signal_date: pd.Timestamp) -> dict | None:
    """신호 종가 대비 1·3·6개월 종가와 구간 최대 유불리 경로를 계산한다."""
    prices = close.dropna().sort_index().astype(float)
    position = prices.index.searchsorted(pd.Timestamp(signal_date), side="right") - 1
    if position < 0 or position + max(HORIZONS.values()) >= len(prices):
        return None
    start = float(prices.iloc[position])
    result: dict[str, float | str] = {
        "signal_price": start,
        "outcome_end": prices.index[position + max(HORIZONS.values())].date().isoformat(),
    }
    for label, sessions in HORIZONS.items():
        path = prices.iloc[position + 1:position + sessions + 1] / start - 1.0
        result[f"terminal_return_{label}"] = float(path.iloc[-1])
        result[f"mae_{label}"] = float(path.min())
        result[f"mfe_{label}"] = float(path.max())
    return result


def classify_action_outcome(action: str, path: dict) -> dict:
    """6개월 경로에서 행동의 기회와 후회를 대칭적으로 표시한다.

    성공률을 매매 수익률로 오해하지 않도록 매도는 5% 이상 조정 기회, 매수는
    6개월 양(+)의 종가 수익을 각각 별도 진단 목표로 사용한다.
    """
    action = action.upper()
    if action == "SELL":
        helpful = float(path["mae_6m"]) <= -0.05
        return {
            "helpful_6m": helpful,
            "avoided_drawdown_opportunity_6m": max(0.0, -float(path["mae_6m"])),
            "foregone_terminal_upside_6m": max(0.0, float(path["terminal_return_6m"])),
        }
    if action == "BUY":
        helpful = float(path["terminal_return_6m"]) > 0.0
        return {
            "helpful_6m": helpful,
            "forward_terminal_return_6m": float(path["terminal_return_6m"]),
            "forward_drawdown_6m": float(path["mae_6m"]),
        }
    raise ValueError(f"unsupported action: {action}")


def diagnose_ticker(ticker: str, raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    frame = raw.copy()
    frame["Date"] = pd.to_datetime(frame["Date"])
    frame = frame.sort_values("Date")
    close_column = "Adj Close" if "Adj Close" in frame else "Close"
    close = frame.set_index("Date")[close_column].astype(float)
    indicators = build_v4_indicator_frame(frame)
    score = v4_base_score(indicators)
    if score.empty:
        raise ValueError("full v4 indicator history unavailable")
    aligned_close = close.loc[score.index.min():]
    decisions = v61_actions(aligned_close, score.reindex(aligned_close.index).ffill())
    decisions = decisions[(decisions["action"] != "HOLD") & (decisions["ratio"] > 0)]

    events = []
    for signal_date, decision in decisions.iterrows():
        path = forward_path(aligned_close, signal_date)
        if path is None:
            continue
        action = str(decision["action"])
        events.append({
            "ticker": ticker,
            "signal_date": pd.Timestamp(signal_date).date().isoformat(),
            "action": action,
            "ratio": float(decision["ratio"]),
            "regime": str(decision["regime"]),
            **path,
            **classify_action_outcome(action, path),
        })
    event_frame = pd.DataFrame(events)
    observed_years = max((aligned_close.index.max() - aligned_close.index.min()).days / 365.2425, 1.0)
    summary = {
        "ticker": ticker,
        "start": aligned_close.index.min().date().isoformat(),
        "end": aligned_close.index.max().date().isoformat(),
        "evaluable_events": int(len(event_frame)),
        "annualized_event_count": float(len(event_frame) / observed_years),
        "buy_events": int((event_frame.get("action") == "BUY").sum()) if not event_frame.empty else 0,
        "sell_events": int((event_frame.get("action") == "SELL").sum()) if not event_frame.empty else 0,
        "helpful_rate_6m": float(event_frame["helpful_6m"].mean()) if not event_frame.empty else None,
    }
    return event_frame, summary


def _group_summary(events: pd.DataFrame, columns: list[str]) -> list[dict]:
    if events.empty:
        return []
    rows = []
    for keys, group in events.groupby(columns, dropna=False):
        values = keys if isinstance(keys, tuple) else (keys,)
        row = dict(zip(columns, values, strict=True))
        row.update({
            "events": int(len(group)),
            "helpful_rate_6m": float(group["helpful_6m"].mean()),
            "median_terminal_return_1m": float(group["terminal_return_1m"].median()),
            "median_terminal_return_3m": float(group["terminal_return_3m"].median()),
            "median_terminal_return_6m": float(group["terminal_return_6m"].median()),
            "median_mae_6m": float(group["mae_6m"].median()),
            "median_mfe_6m": float(group["mfe_6m"].median()),
        })
        rows.append(row)
    return rows


def build_report(events: pd.DataFrame, ticker_rows: list[dict], manifest: dict, failures: dict) -> dict:
    sell = events[events["action"] == "SELL"] if not events.empty else events
    early = sell[sell["ticker"].isin(EARLY_SELL_CASES)] if not sell.empty else sell
    sectors = {ticker: group for group, tickers in SECTOR_UNIVERSE.items() for ticker in tickers}
    if not events.empty:
        events = events.assign(sector=events["ticker"].map(sectors))
    return {
        "report_version": "HERD_V61_BASELINE_DIAGNOSTIC_V1",
        "status": "RESEARCH_BASELINE_NOT_JAVA_PARITY",
        "purpose": "measure historical action frequency and counterfactual price paths before selector redesign",
        "universe_version": UNIVERSE_VERSION,
        "equity_tickers": len(equity_universe()),
        "survivorship_safe": False,
        "operational_action_authority": False,
        "data_source": {
            "snapshot_id": manifest["snapshot_id"],
            "snapshot_sha256": manifest["snapshot_sha256"],
            "coverage": manifest["research_period"],
        },
        "outcome_contract": {
            "sell_helpful": "minimum six-month return <= -5%; opportunity diagnostic, not realized profit",
            "buy_helpful": "six-month terminal return > 0%; diagnostic, not causal alpha",
            "counterfactual": "same ticker buy-and-hold path from the signal close",
        },
        "summary": {
            "evaluable_events": int(len(events)),
            "median_annualized_event_count": float(np.median([row["annualized_event_count"] for row in ticker_rows])),
            "by_action": _group_summary(events, ["action"]),
            "by_action_and_regime": _group_summary(events, ["action", "regime"]),
            "by_sector_and_action": _group_summary(events, ["sector", "action"]),
        },
        "early_sell_cases": _group_summary(early, ["ticker"]),
        "ticker_summary": ticker_rows,
        "failures": failures,
    }


def run(snapshot: Path) -> tuple[pd.DataFrame, dict]:
    tickers = equity_universe()
    manifest = verify_snapshot(snapshot)
    frames = {
        ticker: pd.read_csv(snapshot / manifest["files"][ticker]["path"], parse_dates=["Date"])
        for ticker in tickers
    }
    parts, ticker_rows, failures = [], [], {}
    for ticker in tickers:
        try:
            events, summary = diagnose_ticker(ticker, frames[ticker])
            if not events.empty:
                parts.append(events)
            ticker_rows.append(summary)
        except Exception as exc:  # full audit must preserve unavailable ticker reasons
            failures[ticker] = str(exc)
    all_events = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    return all_events, build_report(all_events, ticker_rows, manifest, failures)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--events-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    events, report = run(args.snapshot)
    args.events_output.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(args.events_output, index=False)
    args.report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
