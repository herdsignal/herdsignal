"""vNext의 경쟁 경로와 5% 완결 행동의 경제 라벨을 분리한다."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from herd.opportunity_cycle_path import load_target


CONTRACT_PATH = Path(__file__).with_suffix(".json")
CONTRACT_VERSION = "HERD_VNEXT_COMPETING_PATH_ECONOMIC_LABEL_V1"
TRADING_DAYS = 252


class VNextLabelError(ValueError):
    """라벨 계약 위반이나 실행 불가능한 사건에서 발생한다."""


@dataclass(frozen=True)
class PathOutcome:
    status: str
    first_boundary: str
    terminal_path: str
    first_boundary_session: str | None
    maximum_favorable_excursion: float | None
    maximum_adverse_excursion: float | None
    terminal_return: float | None
    outcome_end: str | None


@dataclass(frozen=True)
class EconomicOutcome:
    status: str
    trim_fraction: float
    sale_execution_session: str
    sale_execution_price: float
    net_sale_cash: float
    open_trim_terminal_wealth_delta: float
    complete_cycle: bool
    reentry_execution_session: str | None
    reentry_execution_price: float | None
    reentered_shares: float | None
    share_delta: float | None
    terminal_wealth_delta: float | None
    days_out: int | None
    economic_label: str
    labels_authorize_actions: bool


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    if (
        contract.get("contract_version") != CONTRACT_VERSION
        or contract.get("status")
        != "LOCKED_BEFORE_VNEXT_JOINT_HYPOTHESIS_RESULTS"
    ):
        raise VNextLabelError("vNext label contract is not locked")
    target, _ = load_target()
    observation = contract.get("observation", {})
    if (
        observation.get("horizon_sessions") != target["path_horizon_days"]
        or observation.get("volatility_window_sessions")
        != target["signal_volatility_window_days"]
        or observation.get("execution") != "NEXT_SESSION_ADJUSTED_OPEN"
    ):
        raise VNextLabelError("parent path or execution boundary drifted")
    path_contract = contract.get("competing_path_contract", {})
    if (
        path_contract.get("threshold_source")
        != "HERD_OPPORTUNITY_CYCLE_TARGET_V1"
        or path_contract.get("large_pullback_threshold")
        != "MAX_10_PERCENT_OR_TRADABLE_PULLBACK_THRESHOLD"
        or path_contract.get("right_censored_is_not_failure_or_continuation")
        is not True
    ):
        raise VNextLabelError("competing path boundary changed")

    economic = contract.get("economic_label_contract", {})
    if (
        economic.get("trim_fraction") != 0.05
        or economic.get("maximum_cumulative_trim_fraction") != 0.15
        or economic.get("open_trim_is_success") is not False
        or economic.get("complete_cycle_requires_observable_reentry_signal")
        is not True
    ):
        raise VNextLabelError("sparse complete-cycle boundary changed")

    forbidden = set(contract.get("forbidden", []))
    required = {
        "USE_FUTURE_PATH_AS_FEATURE",
        "USE_FUTURE_LOW_AS_REENTRY",
        "OPTIMIZE_REENTRY_DATE_INSIDE_LABELER",
        "COUNT_OPEN_TRIM_AS_SUCCESS",
        "EXECUTE_ON_SIGNAL_CLOSE",
        "AUTHORIZE_OPERATIONAL_ACTION",
    }
    if not required.issubset(forbidden) or contract.get("labels_authorize_actions"):
        raise VNextLabelError("label leakage or action boundary was weakened")
    return {
        "report_version": "HERD_VNEXT_COMPETING_PATH_ECONOMIC_LABEL_AUDIT_V1",
        "status": "COMPETING_PATH_AND_ECONOMIC_LABEL_CONTRACT_VERIFIED",
        "horizon_sessions": observation["horizon_sessions"],
        "trim_fraction": economic["trim_fraction"],
        "first_boundary_is_separate_from_terminal_path": True,
        "open_trim_is_success": False,
        "future_low_reentry_allowed": False,
        "labels_authorize_actions": False,
    }


def _close_series(prices: pd.DataFrame) -> pd.Series:
    column = "Adj Close" if "Adj Close" in prices.columns else "Close"
    close = prices[column].astype(float).copy()
    close.index = pd.to_datetime(close.index)
    close = close.sort_index().dropna()
    if close.empty or (close <= 0).any() or close.index.has_duplicates:
        raise VNextLabelError("adjusted close must be positive and unique")
    return close


def _adjusted_price_frame(prices: pd.DataFrame) -> pd.DataFrame:
    required = {"Open", "Close"}
    if not required.issubset(prices.columns):
        raise VNextLabelError("prices require Open and Close")
    frame = prices.copy()
    frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index()
    adjusted_close = (
        frame["Adj Close"].astype(float)
        if "Adj Close" in frame.columns
        else frame["Close"].astype(float)
    )
    raw_close = frame["Close"].astype(float)
    frame["AdjustedOpen"] = frame["Open"].astype(float) * adjusted_close / raw_close
    frame["AdjustedClose"] = adjusted_close
    frame = frame[["AdjustedOpen", "AdjustedClose"]].dropna()
    if frame.empty or (frame <= 0).any().any() or frame.index.has_duplicates:
        raise VNextLabelError("adjusted execution prices must be positive and unique")
    return frame


def _thresholds(annualized_volatility: float) -> tuple[float, float, float]:
    pullback = max(0.05, 1.5 * annualized_volatility * np.sqrt(21 / 252))
    continuation = max(0.08, 1.5 * annualized_volatility * np.sqrt(63 / 252))
    structural = max(0.15, 2.5 * annualized_volatility * np.sqrt(63 / 252))
    return pullback, continuation, structural


def classify_competing_path(
    prices: pd.DataFrame,
    signal_session: pd.Timestamp,
    contract: dict[str, Any] | None = None,
) -> PathOutcome:
    locked = contract or load_contract()
    validate_contract(locked)
    target, _ = load_target()
    close = _close_series(prices)
    signal = pd.Timestamp(signal_session)
    position = close.index.searchsorted(signal, side="right") - 1
    history_length = target["signal_volatility_window_days"]
    horizon = target["path_horizon_days"]
    if position < history_length:
        raise VNextLabelError("insufficient pre-signal volatility history")
    if position + horizon >= len(close):
        return PathOutcome(
            status="RIGHT_CENSORED",
            first_boundary="RIGHT_CENSORED",
            terminal_path="RIGHT_CENSORED",
            first_boundary_session=None,
            maximum_favorable_excursion=None,
            maximum_adverse_excursion=None,
            terminal_return=None,
            outcome_end=None,
        )

    history = close.iloc[position - history_length : position + 1]
    volatility = float(
        history.pct_change(fill_method=None).std(ddof=1) * np.sqrt(TRADING_DAYS)
    )
    if not np.isfinite(volatility) or volatility <= 0:
        raise VNextLabelError("signal volatility is unavailable")
    pullback, continuation, structural = _thresholds(volatility)
    start = float(close.iloc[position])
    future = close.iloc[position + 1 : position + horizon + 1] / start - 1.0

    downside_hits = future[future <= -pullback]
    upside_hits = future[future >= continuation]
    downside_date = downside_hits.index.min() if not downside_hits.empty else pd.NaT
    upside_date = upside_hits.index.min() if not upside_hits.empty else pd.NaT
    if pd.notna(upside_date) and (
        pd.isna(downside_date) or upside_date < downside_date
    ):
        first_boundary = "UPSIDE_CONTINUATION"
        first_date = upside_date
    elif pd.notna(downside_date):
        first_boundary = "DOWNSIDE_PULLBACK"
        first_date = downside_date
    else:
        first_boundary = "NO_BOUNDARY"
        first_date = pd.NaT

    mae = float(future.min())
    mfe = float(future.max())
    terminal = float(future.iloc[-1])
    low_date = future.idxmin()
    recovered = bool(
        future.loc[low_date:].max()
        >= target["volatility_scaled_thresholds"]["recovery_floor"]
    )
    if (
        mae <= -structural
        and terminal
        <= target["volatility_scaled_thresholds"]["structural_terminal_ceiling"]
    ):
        terminal_path = "STRUCTURAL_BREAK"
    elif mae <= -max(0.10, pullback):
        terminal_path = "LARGE_PULLBACK"
    elif mae <= -pullback and recovered:
        terminal_path = "TRADABLE_PULLBACK"
    elif first_boundary == "UPSIDE_CONTINUATION" and terminal > 0:
        terminal_path = "CONTINUATION"
    else:
        terminal_path = "UNRESOLVED"

    return PathOutcome(
        status="RESOLVED",
        first_boundary=first_boundary,
        terminal_path=terminal_path,
        first_boundary_session=(
            str(pd.Timestamp(first_date).date()) if pd.notna(first_date) else None
        ),
        maximum_favorable_excursion=mfe,
        maximum_adverse_excursion=mae,
        terminal_return=terminal,
        outcome_end=str(future.index[-1].date()),
    )


def evaluate_trim_counterfactual(
    prices: pd.DataFrame,
    signal_session: pd.Timestamp,
    *,
    reentry_signal_session: pd.Timestamp | None = None,
    contract: dict[str, Any] | None = None,
    annual_cash_yield: float = 0.0,
) -> EconomicOutcome:
    """주어진 관측 가능 재진입 신호만 사용해 5% 행동의 경제성을 계산한다."""
    locked = contract or load_contract()
    validate_contract(locked)
    if annual_cash_yield <= -1:
        raise VNextLabelError("annual cash yield must be greater than -100%")
    rules = locked["economic_label_contract"]
    frame = _adjusted_price_frame(prices)
    signal = pd.Timestamp(signal_session)
    signal_position = frame.index.searchsorted(signal, side="right") - 1
    horizon = locked["observation"]["horizon_sessions"]
    if signal_position < 0 or signal_position + horizon >= len(frame):
        raise VNextLabelError("economic outcome horizon is unavailable")

    sale_position = signal_position + 1
    sale_date = frame.index[sale_position]
    fraction = float(rules["trim_fraction"])
    fee = float(rules["one_way_fee_bps"]) / 10_000
    slippage = float(rules["one_way_slippage_bps"]) / 10_000
    sale_price = float(frame["AdjustedOpen"].iloc[sale_position]) * (1 - slippage)
    gross_sale = fraction * sale_price
    net_sale_cash = gross_sale * (1 - fee)
    terminal_position = signal_position + horizon
    terminal_price = float(frame["AdjustedClose"].iloc[terminal_position])
    days_in_cash = terminal_position - sale_position
    terminal_cash = net_sale_cash * (
        (1 + annual_cash_yield) ** (days_in_cash / TRADING_DAYS)
    )
    open_trim_delta = terminal_cash - fraction * terminal_price

    if reentry_signal_session is None:
        return EconomicOutcome(
            status="OPEN_TRIM_DIAGNOSTIC_ONLY",
            trim_fraction=fraction,
            sale_execution_session=str(sale_date.date()),
            sale_execution_price=sale_price,
            net_sale_cash=net_sale_cash,
            open_trim_terminal_wealth_delta=open_trim_delta,
            complete_cycle=False,
            reentry_execution_session=None,
            reentry_execution_price=None,
            reentered_shares=None,
            share_delta=None,
            terminal_wealth_delta=None,
            days_out=None,
            economic_label="INCOMPLETE_CYCLE",
            labels_authorize_actions=False,
        )

    reentry_signal = pd.Timestamp(reentry_signal_session)
    if reentry_signal <= signal:
        raise VNextLabelError("reentry signal must occur after the trim signal")
    reentry_signal_position = frame.index.searchsorted(
        reentry_signal,
        side="right",
    ) - 1
    reentry_position = reentry_signal_position + 1
    if (
        reentry_signal_position < sale_position
        or reentry_position > terminal_position
    ):
        raise VNextLabelError("reentry execution must follow sale within horizon")

    reentry_date = frame.index[reentry_position]
    cash_sessions = reentry_position - sale_position
    available_cash = net_sale_cash * (
        (1 + annual_cash_yield) ** (cash_sessions / TRADING_DAYS)
    )
    reentry_price = float(frame["AdjustedOpen"].iloc[reentry_position]) * (
        1 + slippage
    )
    reentered_shares = available_cash / (reentry_price * (1 + fee))
    share_delta = reentered_shares - fraction
    terminal_delta = share_delta * terminal_price
    return EconomicOutcome(
        status="COMPLETE_CYCLE_EVALUATED",
        trim_fraction=fraction,
        sale_execution_session=str(sale_date.date()),
        sale_execution_price=sale_price,
        net_sale_cash=net_sale_cash,
        open_trim_terminal_wealth_delta=open_trim_delta,
        complete_cycle=True,
        reentry_execution_session=str(reentry_date.date()),
        reentry_execution_price=reentry_price,
        reentered_shares=reentered_shares,
        share_delta=share_delta,
        terminal_wealth_delta=terminal_delta,
        days_out=int((reentry_date - sale_date).days),
        economic_label=(
            "POSITIVE_COMPLETE_CYCLE"
            if share_delta > 0
            else "NEGATIVE_COMPLETE_CYCLE"
        ),
        labels_authorize_actions=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate_contract(load_contract())
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
