"""고정 S1 상태 사건을 과거 가격에 재생하는 설명 전용 원장을 만든다."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
TRANSITION_REPORT_PATH = ROOT / "data/reports/herd_transition_s1.json"
STATE_CONTRACT_PATH = ROOT / "data/herd/herd_state_s1.json"
DEFAULT_LEDGER_PATH = ROOT / "data/reports/historical_s1_replay_v1.csv.gz"
DEFAULT_REPORT_PATH = ROOT / "data/reports/historical_s1_replay_v1.json"
VERSION = "HERD_HISTORICAL_S1_REPLAY_V1"
LOCKED_HORIZONS = [5, 10, 20, 21, 40, 60, 63, 126, 130]
PROSPECTIVE_COMPARISON_HORIZONS = [21, 63, 126]
ROLE_MANIFEST_KEYS = {
    "PRIMARY": "primary_snapshot_manifest",
    "INDEPENDENT_CURRENT_CONSTITUENTS": "independent_snapshot_manifest",
}


class HistoricalS1ReplayError(RuntimeError):
    """고정 입력, 사건 중복 또는 행동 차단 계약이 깨졌을 때 발생한다."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise HistoricalS1ReplayError(f"missing replay input: {relative}")
    return path


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    boundary = contract.get("claim_boundary", {})
    if (
        contract.get("contract_version") != VERSION
        or contract.get("status") != "LOCKED_DESCRIPTIVE_REPLAY_ONLY"
        or contract["event_contract"].get("collapse_calendar_days") != 42
        or contract["outcome_contract"].get("horizons_sessions")
        != LOCKED_HORIZONS
        or contract["outcome_contract"].get(
            "prospective_comparison_horizons_sessions"
        ) != PROSPECTIVE_COMPARISON_HORIZONS
        or boundary.get("descriptive_outcomes_only") is not True
        or boundary.get("point_in_time_price_calculation") is not True
        or boundary.get("point_in_time_membership") is not False
        or boundary.get("candidate_selection") is not False
        or boundary.get("direction_prediction") is not False
        or boundary.get("buy_or_profit_take_authority") is not False
        or boundary.get("operational_action") != "HOLD"
        or float(boundary.get("operational_action_ratio", -1)) != 0.0
        or boundary.get("blind_holdout_access") is not False
        or boundary.get("survivorship_safe") is not False
    ):
        raise HistoricalS1ReplayError("historical replay contract is not locked")
    return contract


def _era(signal_date: pd.Timestamp, contract: dict[str, Any]) -> str:
    for era in contract["era_contract"]:
        if era["start_year"] <= signal_date.year <= era["end_year"]:
            return str(era["id"])
    raise HistoricalS1ReplayError(
        f"signal date is outside locked eras: {signal_date.date()}"
    )


def _strict_bool(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    if isinstance(value, (int, np.integer)) and value in {0, 1}:
        return bool(value)
    raise HistoricalS1ReplayError(f"invalid transition boolean: {value!r}")


def extract_events(
    panel: pd.DataFrame,
    contract: dict[str, Any],
) -> pd.DataFrame:
    """주간 상태에서 최초 진입·강조 전환만 뽑고 근접 중복을 제거한다."""
    required = {
        "ticker",
        "signal_date",
        "last_observed_session",
        "HERD_STATE",
        "HERD_STAGE",
        "HERD_TRANSITION",
        "TRANSITION_EVENT",
        "sector_etf",
        "universe_role",
    }
    if not required.issubset(panel.columns):
        raise HistoricalS1ReplayError(
            f"transition columns missing: {sorted(required - set(panel.columns))}"
        )
    rows = panel.copy()
    rows["signal_date"] = pd.to_datetime(rows["signal_date"], errors="coerce")
    rows["last_observed_session"] = pd.to_datetime(
        rows["last_observed_session"], errors="coerce"
    )
    if rows[["signal_date", "last_observed_session"]].isna().any().any():
        raise HistoricalS1ReplayError("transition panel contains invalid dates")
    rows = rows.sort_values(["universe_role", "ticker", "signal_date"])
    rows["previous_stage"] = rows.groupby(
        ["universe_role", "ticker"], sort=False
    )["HERD_STAGE"].shift(1)
    stage_entries = set(contract["event_contract"]["stage_entries"])
    transition_entries = set(
        contract["event_contract"]["highlighted_transitions"]
    )
    events: list[dict[str, Any]] = []
    for row in rows.itertuples(index=False):
        kinds: list[str] = []
        if row.HERD_STAGE in stage_entries and row.HERD_STAGE != row.previous_stage:
            kinds.append(f"STAGE_ENTRY_{row.HERD_STAGE}")
        if (
            _strict_bool(row.TRANSITION_EVENT)
            and row.HERD_TRANSITION in transition_entries
        ):
            kinds.append(f"TRANSITION_{row.HERD_TRANSITION}")
        for kind in kinds:
            events.append({
                "universe_role": row.universe_role,
                "ticker": row.ticker,
                "sector_etf": row.sector_etf,
                "signal_date": row.signal_date,
                "last_observed_session": row.last_observed_session,
                "event_kind": kind,
                "herd_state": float(row.HERD_STATE),
                "herd_stage": row.HERD_STAGE,
                "herd_transition": row.HERD_TRANSITION,
            })
    if not events:
        return pd.DataFrame(columns=[
            "episode_id", "era_id", "universe_role", "ticker", "sector_etf",
            "signal_date", "last_observed_session", "event_kind", "herd_state",
            "herd_stage", "herd_transition",
        ])
    candidates = pd.DataFrame(events).sort_values(
        ["universe_role", "ticker", "event_kind", "signal_date"]
    )
    cooldown = pd.Timedelta(
        days=int(contract["event_contract"]["collapse_calendar_days"])
    )
    keep = []
    last_kept: dict[tuple[str, str, str], pd.Timestamp] = {}
    for row in candidates.itertuples(index=False):
        key = (row.universe_role, row.ticker, row.event_kind)
        previous = last_kept.get(key)
        accepted = previous is None or row.signal_date - previous > cooldown
        keep.append(accepted)
        if accepted:
            last_kept[key] = row.signal_date
    collapsed = candidates.loc[keep].copy()
    collapsed["era_id"] = collapsed["signal_date"].map(
        lambda value: _era(pd.Timestamp(value), contract)
    )
    collapsed["episode_id"] = collapsed.apply(
        lambda row: hashlib.sha256(
            "|".join([
                VERSION,
                str(row["universe_role"]),
                str(row["ticker"]),
                str(row["event_kind"]),
                pd.Timestamp(row["signal_date"]).date().isoformat(),
            ]).encode("utf-8")
        ).hexdigest()[:24],
        axis=1,
    )
    if collapsed["episode_id"].duplicated().any():
        raise HistoricalS1ReplayError("duplicate episode identity")
    return collapsed[[
        "episode_id", "era_id", "universe_role", "ticker", "sector_etf",
        "signal_date", "last_observed_session", "event_kind", "herd_state",
        "herd_stage", "herd_transition",
    ]].reset_index(drop=True)


def _adjusted_prices(path: Path, expected_hash: str) -> pd.DataFrame:
    if _sha256(path) != expected_hash:
        raise HistoricalS1ReplayError(f"price snapshot hash changed: {path}")
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        frame = pd.read_csv(stream)
    required = {"Date", "Open", "High", "Low", "Close", "Adj Close"}
    if not required.issubset(frame.columns):
        raise HistoricalS1ReplayError(f"price columns missing: {path}")
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    numeric = frame[["Open", "High", "Low", "Close", "Adj Close"]].apply(
        pd.to_numeric, errors="coerce"
    )
    factor = numeric["Adj Close"] / numeric["Close"].replace(0, np.nan)
    adjusted = pd.DataFrame({
        "Date": frame["Date"],
        "Open": numeric["Open"] * factor,
        "High": numeric["High"] * factor,
        "Low": numeric["Low"] * factor,
        "Close": numeric["Adj Close"],
    }).dropna().drop_duplicates("Date", keep="last").sort_values("Date")
    if adjusted.empty or not adjusted["Date"].is_monotonic_increasing:
        raise HistoricalS1ReplayError(f"invalid adjusted prices: {path}")
    return adjusted.reset_index(drop=True)


def attach_outcomes(
    events: pd.DataFrame,
    prices: dict[str, pd.DataFrame],
    contract: dict[str, Any],
) -> pd.DataFrame:
    """관측 이후 첫 보정 시가부터 각 고정 기간의 설명 결과를 계산한다."""
    results: list[dict[str, Any]] = []
    horizons = contract["outcome_contract"]["horizons_sessions"]
    for event in events.itertuples(index=False):
        frame = prices.get(event.ticker)
        if frame is None:
            continue
        future = frame.loc[
            frame["Date"].gt(pd.Timestamp(event.last_observed_session))
        ].reset_index(drop=True)
        if future.empty:
            continue
        entry = float(future.iloc[0]["Open"])
        if not np.isfinite(entry) or entry <= 0:
            raise HistoricalS1ReplayError(f"invalid entry price: {event.ticker}")
        for horizon in horizons:
            if len(future) < horizon:
                continue
            window = future.iloc[:horizon]
            terminal = float(window.iloc[-1]["Close"])
            result = event._asdict()
            result.update({
                "horizon_sessions": int(horizon),
                "entry_date": window.iloc[0]["Date"],
                "terminal_date": window.iloc[-1]["Date"],
                "total_return": terminal / entry - 1,
                "maximum_favorable_excursion": float(
                    (window["High"] / entry - 1).max()
                ),
                "maximum_adverse_excursion": float(
                    (window["Low"] / entry - 1).min()
                ),
                "economic_label": "NOT_ASSIGNED_DESCRIPTIVE_ONLY",
                "direction_prediction": False,
                "operational_action": "HOLD",
                "operational_action_ratio": 0.0,
            })
            results.append(result)
    return pd.DataFrame(results)


def _load_inputs(
    contract: dict[str, Any],
    contract_path: Path,
) -> tuple[pd.DataFrame, dict[tuple[str, str], pd.DataFrame], dict[str, str]]:
    transition_report = json.loads(
        TRANSITION_REPORT_PATH.read_text(encoding="utf-8")
    )
    state_contract = json.loads(STATE_CONTRACT_PATH.read_text(encoding="utf-8"))
    if (
        transition_report.get("status") != "TRANSITION_DISPLAY_READY"
        or transition_report.get("future_outcomes_read") is not False
        or float(transition_report.get("operational_action_ratio", -1)) != 0.0
    ):
        raise HistoricalS1ReplayError("transition report is not safe for replay")
    panels = []
    prices: dict[tuple[str, str], pd.DataFrame] = {}
    input_hashes = {
        "contract": _sha256(contract_path),
        "transition_report": _sha256(TRANSITION_REPORT_PATH),
        "state_contract": _sha256(STATE_CONTRACT_PATH),
    }
    for role, manifest_key in ROLE_MANIFEST_KEYS.items():
        receipt = transition_report["panels"][role]
        panel_path = _rooted(receipt["path"])
        if _sha256(panel_path) != receipt["sha256"]:
            raise HistoricalS1ReplayError(f"transition panel hash changed: {role}")
        panel = pd.read_csv(panel_path, compression="gzip")
        panels.append(panel)
        specification = state_contract["inputs"][manifest_key]
        manifest_path = _rooted(specification["path"])
        if _sha256(manifest_path) != specification["sha256"]:
            raise HistoricalS1ReplayError(f"snapshot manifest hash changed: {role}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        input_hashes[f"{role.lower()}_manifest"] = specification["sha256"]
        for ticker in panel["ticker"].unique():
            item = manifest["files"].get(ticker)
            if item is None:
                continue
            prices[(role, ticker)] = _adjusted_prices(
                manifest_path.parent / item["path"], item["sha256"]
            )
    events = extract_events(pd.concat(panels, ignore_index=True), contract)
    keyed_prices = {
        f"{role}|{ticker}": frame for (role, ticker), frame in prices.items()
    }
    return events, keyed_prices, input_hashes


def run(
    contract_path: Path = CONTRACT_PATH,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    events, keyed_prices, input_hashes = _load_inputs(contract, contract_path)
    event_parts = []
    for role, role_events in events.groupby("universe_role", sort=True):
        prices = {
            key.split("|", 1)[1]: value
            for key, value in keyed_prices.items()
            if key.startswith(f"{role}|")
        }
        event_parts.append(attach_outcomes(role_events, prices, contract))
    ledger = (
        pd.concat(event_parts, ignore_index=True)
        if event_parts else pd.DataFrame()
    )
    if (
        not ledger.empty
        and ledger.duplicated(["episode_id", "horizon_sessions"]).any()
    ):
        raise HistoricalS1ReplayError("duplicate episode horizon outcome")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = ledger_path.with_name(f".{ledger_path.name}.tmp.gz")
    ledger.to_csv(temporary, index=False, compression="gzip")
    os.replace(temporary, ledger_path)
    report = {
        "report_version": VERSION,
        "status": "DESCRIPTIVE_REPLAY_COMPLETE",
        "input_hashes": input_hashes,
        "ledger": {
            "path": str(ledger_path.relative_to(ROOT)),
            "sha256": _sha256(ledger_path),
            "rows": int(len(ledger)),
            "episodes": int(ledger["episode_id"].nunique()) if not ledger.empty else 0,
            "tickers": int(ledger["ticker"].nunique()) if not ledger.empty else 0,
        },
        "extracted_episodes": int(events["episode_id"].nunique()),
        "evaluable_episodes": (
            int(ledger["episode_id"].nunique()) if not ledger.empty else 0
        ),
        "extracted_episodes_by_role": {
            key: int(value)
            for key, value in events.groupby("universe_role")["episode_id"]
            .nunique().items()
        },
        "matured_rows_by_horizon": {
            str(int(key)): int(value)
            for key, value in ledger["horizon_sessions"].value_counts()
            .sort_index().items()
        } if not ledger.empty else {},
        "direction_prediction": False,
        "buy_or_profit_take_authority": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
        "survivorship_safe": False,
        "claim": (
            "Current-constituent historical replay for descriptive diagnosis; "
            "not a point-in-time membership backtest."
        ),
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    args = parser.parse_args()
    print(json.dumps(
        run(args.contract, args.ledger, args.report),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
