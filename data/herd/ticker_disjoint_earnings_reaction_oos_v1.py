"""Run the locked earnings-reaction hypothesis on a ticker-disjoint history."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from herd.fixed_policy_economic_engine import evaluate_fixed_policy
from herd.profit_take_opportunity_ceiling_v1 import measure_entry
from herd.rush_negative_earnings_reaction_oos_v1 import evaluate
from herd.vnext_competing_path_economic_label_v1 import (
    classify_competing_path,
    load_contract as load_path_contract,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
OUTPUT_PATH = ROOT / "data/reports/ticker_disjoint_earnings_reaction_oos_v1.csv"
REPORT_PATH = ROOT / "data/reports/ticker_disjoint_earnings_reaction_oos_v1.json"
PROMOTION_PATH = ROOT / "data/reports/rush_earnings_prospective_confirmation_gate_v1.json"
ET = ZoneInfo("America/New_York")


class TickerDisjointEarningsOosError(RuntimeError):
    """Raised when a locked input, event time, or execution boundary drifts."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if (
        contract.get("protocol_version") != "TICKER_DISJOINT_EARNINGS_REACTION_OOS_V1"
        or contract.get("status") != "LOCKED_BEFORE_HISTORICAL_REACTION_RESULTS"
        or contract["economic_policy"]["policy"] != "TRIM_REENTER_63"
        or contract["operational_action_ratio"] != 0.0
    ):
        raise TickerDisjointEarningsOosError("historical OOS protocol is not locked")
    for item in contract["inputs"]:
        source = (ROOT / item["path"]).resolve()
        if not source.is_relative_to(ROOT) or not source.is_file():
            raise TickerDisjointEarningsOosError(f"missing locked input: {item['path']}")
        if _sha256(source) != item["sha256"]:
            raise TickerDisjointEarningsOosError(f"locked input changed: {item['path']}")
    return contract


def collapse_quarterly_disclosures(events: pd.DataFrame) -> pd.DataFrame:
    """Keep the first filing that makes one ticker-quarter's results public."""
    rows = events.copy()
    rows["accepted_at"] = pd.to_datetime(rows["accepted_at"], utc=True)
    rows["report_date"] = rows["report_date"].fillna("").astype(str)
    rows = rows.sort_values(["ticker", "accepted_at", "event_id"])
    keep: list[int] = []
    last_by_key: dict[tuple[str, str], pd.Timestamp] = {}
    for index, row in rows.iterrows():
        report_date = row["report_date"].strip()
        if not report_date:
            keep.append(index)
            continue
        key = (str(row["ticker"]), report_date)
        previous = last_by_key.get(key)
        if previous is None or (row["accepted_at"] - previous).days > 7:
            keep.append(index)
            last_by_key[key] = row["accepted_at"]
    return rows.loc[keep].sort_values(["accepted_at", "event_id"]).reset_index(drop=True)


def reaction_sessions(
    sessions: pd.DatetimeIndex, accepted_at: pd.Timestamp
) -> tuple[int, int] | None:
    accepted = pd.Timestamp(accepted_at)
    if accepted.tzinfo is None:
        raise TickerDisjointEarningsOosError("SEC acceptance must be timezone-aware")
    local = accepted.tz_convert(ET)
    normalized = sessions.tz_localize(None).normalize()
    event_day = local.tz_localize(None).normalize()
    start = int(normalized.searchsorted(event_day, side="left"))
    if (
        start < len(normalized)
        and normalized[start] == event_day
        and local.time() >= time(9, 30)
    ):
        start += 1
    if start == 0 or start + 2 >= len(normalized):
        return None
    return start - 1, start + 2


def _load_price(manifest_path: Path, ticker: str) -> pd.DataFrame:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    item = manifest["files"].get(ticker)
    if item is None:
        raise TickerDisjointEarningsOosError(f"price missing: {ticker}")
    path = manifest_path.parent / item["path"]
    if _sha256(path) != item["sha256"]:
        raise TickerDisjointEarningsOosError(f"price hash changed: {ticker}")
    frame = pd.read_csv(path, compression="gzip", parse_dates=["Date"])
    frame = frame.sort_values("Date").drop_duplicates("Date", keep="last")
    return frame.set_index("Date")


def _adjusted_execution_prices(frame: pd.DataFrame) -> pd.DataFrame:
    ratio = frame["Adj Close"].astype(float) / frame["Close"].astype(float)
    adjusted = pd.DataFrame({
        "Open": frame["Open"].astype(float) * ratio,
        "Close": frame["Adj Close"].astype(float),
    }, index=frame.index)
    return adjusted.replace([np.inf, -np.inf], np.nan).dropna()


def _opportunity_prices(frame: pd.DataFrame) -> pd.DataFrame:
    ratio = frame["Adj Close"].astype(float) / frame["Close"].astype(float)
    return pd.DataFrame({
        "Date": frame.index,
        "AdjustedOpen": frame["Open"].astype(float) * ratio,
        "AdjustedClose": frame["Adj Close"].astype(float),
    }).reset_index(drop=True)


def _outcome_label(frame: pd.DataFrame, confirmation: pd.Timestamp) -> str:
    path = classify_competing_path(frame, confirmation, load_path_contract())
    if path.status == "RIGHT_CENSORED":
        return "RIGHT_CENSORED"
    if path.terminal_path == "STRUCTURAL_BREAK":
        return "STRUCTURAL_BREAK"
    ceiling_contract = json.loads(
        (ROOT / "data/herd/profit_take_opportunity_ceiling_v1.json").read_text()
    )
    opportunity = measure_entry(_opportunity_prices(frame), confirmation, ceiling_contract)
    if opportunity is None:
        return "RIGHT_CENSORED"
    if bool(opportunity["stress_constrained_available"]):
        return "ECONOMIC_REBUY_OPPORTUNITY"
    if path.terminal_path == "CONTINUATION":
        return "HEALTHY_CONTINUATION"
    return "NO_ECONOMIC_EDGE"


def build_panel(contract: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, int]]:
    paths = {Path(item["path"]).name: ROOT / item["path"] for item in contract["inputs"]}
    events = collapse_quarterly_disclosures(
        pd.read_csv(paths["ticker_disjoint_sec_earnings_census_v1.csv"])
    )
    states = pd.read_csv(
        paths["ticker_disjoint_earnings_oos_state_s1.csv.gz"],
        compression="gzip",
        parse_dates=["signal_date", "last_observed_session"],
    ).sort_values(["ticker", "last_observed_session"])
    universe = pd.read_csv(paths["ticker_disjoint_earnings_oos_universe_v1.csv"])
    sector_by_ticker = universe.set_index("ticker")["sector_etf"].to_dict()
    manifest_path = paths["manifest.json"]
    parent = json.loads(paths["rush_negative_earnings_reaction_preregistration_v1.json"].read_text())
    rules = contract["event_binding"]
    policy = contract["economic_policy"]
    prices: dict[str, pd.DataFrame] = {}
    records: list[dict[str, Any]] = []
    exclusions: Counter[str] = Counter()
    accepted_candidates: dict[str, list[int]] = {}

    for event in events.itertuples(index=False):
        ticker = str(event.ticker)
        sector = sector_by_ticker.get(ticker)
        if sector is None:
            exclusions["OUTSIDE_LOCKED_UNIVERSE"] += 1
            continue
        for symbol in (ticker, sector):
            if symbol not in prices:
                prices[symbol] = _load_price(manifest_path, symbol)
        stock = prices[ticker]
        sector_frame = prices[sector]
        session_pair = reaction_sessions(stock.index, pd.Timestamp(event.accepted_at))
        if session_pair is None:
            exclusions["REACTION_WINDOW_UNAVAILABLE"] += 1
            continue
        baseline_position, confirmation_position = session_pair
        if confirmation_position + int(policy["outcome_horizon_stock_sessions"]) >= len(stock):
            exclusions["RIGHT_CENSORED"] += 1
            continue
        baseline = stock.index[baseline_position]
        confirmation = stock.index[confirmation_position]
        sector_baseline_position = int(sector_frame.index.searchsorted(baseline, side="right")) - 1
        sector_confirmation_position = int(
            sector_frame.index.searchsorted(confirmation, side="right")
        ) - 1
        if sector_baseline_position < 0 or sector_confirmation_position <= sector_baseline_position:
            exclusions["SECTOR_WINDOW_UNAVAILABLE"] += 1
            continue
        stock_reaction = float(stock["Adj Close"].iloc[confirmation_position] / stock["Adj Close"].iloc[baseline_position] - 1)
        sector_reaction = float(sector_frame["Adj Close"].iloc[sector_confirmation_position] / sector_frame["Adj Close"].iloc[sector_baseline_position] - 1)
        residual = stock_reaction - sector_reaction
        if residual > float(rules["maximum_residual_reaction"]):
            exclusions["REACTION_THRESHOLD_NOT_MET"] += 1
            continue
        ticker_states = states[
            states["ticker"].eq(ticker)
            & states["last_observed_session"].le(confirmation)
        ]
        if ticker_states.empty:
            exclusions["STATE_UNAVAILABLE"] += 1
            continue
        state = ticker_states.iloc[-1]
        observed_position = int(
            stock.index.searchsorted(pd.Timestamp(state.last_observed_session), side="right")
        ) - 1
        if confirmation_position - observed_position > int(rules["maximum_state_age_stock_sessions"]):
            exclusions["STATE_TOO_OLD"] += 1
            continue
        if state.HERD_STAGE != parent["single_hypothesis"]["required_state"]:
            exclusions["NOT_RUSH"] += 1
            continue
        year_positions = accepted_candidates.setdefault(ticker, [])
        same_year = [position for position in year_positions if stock.index[position].year == confirmation.year]
        if len(same_year) >= int(rules["maximum_events_per_ticker_year"]):
            exclusions["ANNUAL_FREQUENCY_CAP"] += 1
            continue
        if year_positions and confirmation_position - year_positions[-1] < int(rules["cooldown_stock_sessions"]):
            exclusions["COOLDOWN"] += 1
            continue
        terminal = stock.index[confirmation_position + int(policy["outcome_horizon_stock_sessions"])]
        adjusted = _adjusted_execution_prices(stock)
        base = evaluate_fixed_policy(
            ticker_prices=adjusted,
            signal_date=confirmation,
            terminal_date=terminal,
            policy_id=policy["policy"],
            one_way_cost_bps=int(policy["base_round_trip_cost_bps"]) // 2,
        )
        stress = evaluate_fixed_policy(
            ticker_prices=adjusted,
            signal_date=confirmation,
            terminal_date=terminal,
            policy_id=policy["policy"],
            one_way_cost_bps=int(policy["stress_round_trip_cost_bps"]) // 2,
        )
        label = _outcome_label(stock, confirmation)
        if label == "RIGHT_CENSORED":
            exclusions["RIGHT_CENSORED_LABEL"] += 1
            continue
        year_positions.append(confirmation_position)
        records.append({
            "event_id": event.event_id,
            "ticker": ticker,
            "sector_etf": sector,
            "sec_accepted_at": event.accepted_at,
            "reaction_confirmation_session": confirmation.date().isoformat(),
            "state_observation_date": pd.Timestamp(state.last_observed_session).date().isoformat(),
            "state_age_sessions": confirmation_position - observed_position,
            "herd_stage": state.HERD_STAGE,
            "stock_reaction_3s": stock_reaction,
            "sector_reaction_3s": sector_reaction,
            "residual_reaction_3s": residual,
            "outcome_maturity_date": terminal.date().isoformat(),
            "outcome_label": label,
            "completed_cycle": True,
            "hold_terminal_value": base.hold_terminal_wealth,
            "candidate_terminal_value_base": base.policy_terminal_wealth,
            "candidate_terminal_value_stress": stress.policy_terminal_wealth,
            "base_round_trip_cost_bps": policy["base_round_trip_cost_bps"],
            "stress_round_trip_cost_bps": policy["stress_round_trip_cost_bps"],
            "policy_id": policy["policy"],
            "reentry_date": base.reentry_date,
        })
    panel = pd.DataFrame(records)
    if panel.empty:
        panel = pd.DataFrame(columns=sorted({
            "event_id", "ticker", "sector_etf", "sec_accepted_at",
            "reaction_confirmation_session", "state_observation_date", "herd_stage",
            "state_age_sessions",
            "stock_reaction_3s", "sector_reaction_3s", "residual_reaction_3s",
            "outcome_maturity_date", "outcome_label", "completed_cycle",
            "hold_terminal_value", "candidate_terminal_value_base",
            "candidate_terminal_value_stress", "base_round_trip_cost_bps",
            "stress_round_trip_cost_bps", "policy_id", "reentry_date",
        }))
    return panel.sort_values(["sec_accepted_at", "event_id"]), dict(exclusions)


def build_prospective_gate(passed: bool) -> dict[str, Any]:
    return {
        "report_version": "RUSH_EARNINGS_PROSPECTIVE_CONFIRMATION_GATE_V1",
        "status": (
            "PROSPECTIVE_CONFIRMATION_ACTIVE" if passed
            else "PROSPECTIVE_COLLECTION_ONLY_CONFIRMATION_BLOCKED"
        ),
        "historical_screen_passed": passed,
        "sec_append_only_collection_active": True,
        "prospective_outcomes_may_be_opened_when_mature": passed,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
        "reason": (
            "locked ticker-disjoint historical gate passed"
            if passed else "locked ticker-disjoint historical gate did not pass"
        ),
    }


def run(
    output_path: Path = OUTPUT_PATH,
    report_path: Path = REPORT_PATH,
    promotion_path: Path = PROMOTION_PATH,
) -> dict[str, Any]:
    contract = load_contract()
    panel, exclusions = build_panel(contract)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(output_path, index=False)
    parent = json.loads(
        (ROOT / "data/herd/rush_negative_earnings_reaction_preregistration_v1.json").read_text()
    )
    historical_protocol = json.loads(json.dumps(parent))
    historical_protocol["sample_contract"]["first_eligible_event_date"] = "2012-01-01"
    result = evaluate(panel, historical_protocol) if len(panel) else {
        "checks": {key: False for key in (
            "mature_events", "distinct_tickers", "calendar_years", "positive_years",
            "adverse_precision", "terminal_wealth", "stress_terminal_wealth",
            "positive_completed_cycle_rate",
        )},
        "passed": False,
        "mature_events": 0,
        "distinct_tickers": 0,
        "calendar_years": 0,
    }
    passed = bool(result["passed"])
    event_input = next(
        ROOT / item["path"]
        for item in contract["inputs"]
        if item["path"].endswith("ticker_disjoint_sec_earnings_census_v1.csv")
    )
    result.update({
        "report_version": "TICKER_DISJOINT_EARNINGS_REACTION_OOS_V1",
        "status": "HISTORICAL_FALSIFICATION_PASSED" if passed else "HISTORICAL_FALSIFICATION_FAILED",
        "historical_screen_passed": passed,
        "prospective_confirmation_allowed": passed,
        "direction_evidence_admitted": False,
        "candidate_action_enabled": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
        "survivorship_safe": False,
        "blind_holdout_access": False,
        "input_rows": len(pd.read_csv(event_input)),
        "candidate_rows": len(panel),
        "exclusions": exclusions,
        "panel_path": str(output_path.relative_to(ROOT)),
        "panel_sha256": _sha256(output_path),
    })
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    promotion = build_prospective_gate(passed)
    promotion_path.write_text(json.dumps(promotion, ensure_ascii=False, indent=2) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
