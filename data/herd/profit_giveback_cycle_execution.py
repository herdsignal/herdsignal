"""수익 반납 완결 사이클의 가격·PIT 게이트·액션 스케줄."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


class ProfitGivebackExecutionError(RuntimeError):
    """완결 사이클 실행 입력이나 시간 순서가 올바르지 않을 때 발생한다."""


def adjusted_execution_prices(raw: pd.DataFrame) -> pd.DataFrame:
    """분할·배당과 일관된 합성 시가·종가를 만든다."""
    required = {"Date", "Open", "Close", "Adj Close"}
    missing = required - set(raw.columns)
    if missing:
        raise ProfitGivebackExecutionError(
            f"missing price columns: {sorted(missing)}"
        )
    frame = raw[list(required)].copy()
    frame["Date"] = pd.to_datetime(frame["Date"])
    numeric = frame[["Open", "Close", "Adj Close"]].astype(float)
    if (
        numeric.isna().any().any()
        or not np.isfinite(numeric.to_numpy()).all()
        or (numeric <= 0).any().any()
    ):
        raise ProfitGivebackExecutionError("invalid raw execution prices")
    factor = numeric["Adj Close"] / numeric["Close"]
    adjusted = pd.DataFrame(
        {
            "Open": (numeric["Open"] * factor).to_numpy(),
            "Close": numeric["Adj Close"].to_numpy(),
        },
        index=pd.DatetimeIndex(frame["Date"]),
    ).sort_index()
    if adjusted.index.has_duplicates:
        raise ProfitGivebackExecutionError("duplicate price sessions")
    return adjusted


def latest_business_gate(
    business: pd.DataFrame,
    ticker: str,
    signal_date: pd.Timestamp,
) -> tuple[str, pd.Timestamp | None]:
    """신호일 전에 실제로 이용 가능했던 가장 최근 기업 상태를 반환한다."""
    date = pd.Timestamp(signal_date).normalize()
    rows = business[
        business["ticker"].eq(ticker)
        & business["business_available_date"].le(date)
        & business["latest_fact_accepted_at"].notna()
        & business["latest_fact_accepted_at"].dt.normalize().lt(date)
    ].sort_values(["business_available_date", "latest_fact_accepted_at"])
    if rows.empty:
        return "UNKNOWN", None
    row = rows.iloc[-1]
    return str(row["guard_state"]), pd.Timestamp(row["month_end"])


def build_action_schedule(
    *,
    policy_id: str,
    ticker: str,
    fold_id: str,
    prices: pd.DataFrame,
    events: pd.DataFrame,
    transitions: pd.DataFrame,
    business: pd.DataFrame,
    minimum_reentry_days: int,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """매도 현금이 있을 때만 확인된 회복에서 전액 재진입한다."""
    actions = pd.DataFrame(
        {"action": "HOLD", "ratio": 0.0},
        index=prices.index,
    )
    audit_rows: list[dict[str, Any]] = []
    sales = events[
        events["policy_id"].eq(policy_id)
        & events["ticker"].eq(ticker)
        & events["fold_id"].eq(fold_id)
    ].sort_values("last_observed_session")
    if sales.empty:
        return actions, audit_rows

    sell_dates: list[pd.Timestamp] = []
    for row in sales.itertuples(index=False):
        observed = pd.Timestamp(row.last_observed_session)
        if observed not in actions.index:
            raise ProfitGivebackExecutionError(
                f"trim observation is not a trading session: {ticker} {observed}"
            )
        if actions.at[observed, "action"] != "HOLD":
            raise ProfitGivebackExecutionError("duplicate policy action date")
        actions.at[observed, "action"] = "SELL"
        actions.at[observed, "ratio"] = float(row.trim_fraction)
        sell_dates.append(observed)
        audit_rows.append(
            {
                "policy_id": policy_id,
                "fold_id": fold_id,
                "ticker": ticker,
                "signal_date": pd.Timestamp(row.signal_date),
                "observed_session": observed,
                "action": "SELL",
                "ratio": float(row.trim_fraction),
                "business_gate": None,
                "business_month_end": None,
                "reason": "LOCKED_GIVEBACK_EVENT",
            }
        )

    recovery_rows = transitions[
        transitions["ticker"].eq(ticker)
        & transitions["HERD_TRANSITION"].eq("RECOVERING")
        & transitions["last_observed_session"].isin(actions.index)
    ].sort_values("last_observed_session")
    open_sale_dates: list[pd.Timestamp] = []
    timeline = sorted(
        [(date, "SELL") for date in sell_dates]
        + [
            (pd.Timestamp(row.last_observed_session), "RECOVERING")
            for row in recovery_rows.itertuples(index=False)
        ],
        key=lambda item: (item[0], 0 if item[1] == "SELL" else 1),
    )
    for date, kind in timeline:
        if kind == "SELL":
            open_sale_dates.append(date)
            continue
        if not open_sale_dates:
            continue
        if date < max(open_sale_dates) + pd.Timedelta(days=minimum_reentry_days):
            continue
        if actions.at[date, "action"] != "HOLD":
            continue
        gate, month_end = latest_business_gate(business, ticker, date)
        if gate != "PASS":
            audit_rows.append(
                {
                    "policy_id": policy_id,
                    "fold_id": fold_id,
                    "ticker": ticker,
                    "signal_date": date,
                    "observed_session": date,
                    "action": "REENTRY_BLOCKED",
                    "ratio": 0.0,
                    "business_gate": gate,
                    "business_month_end": month_end,
                    "reason": "BUSINESS_SAFETY_VETO",
                }
            )
            continue
        actions.at[date, "action"] = "BUY"
        actions.at[date, "ratio"] = 1.0
        audit_rows.append(
            {
                "policy_id": policy_id,
                "fold_id": fold_id,
                "ticker": ticker,
                "signal_date": date,
                "observed_session": date,
                "action": "BUY",
                "ratio": 1.0,
                "business_gate": gate,
                "business_month_end": month_end,
                "reason": "RECOVERING_WITH_PASS_SAFETY_GATE",
            }
        )
        open_sale_dates.clear()
    return actions, audit_rows
