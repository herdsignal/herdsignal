"""잠긴 Rush·실적 반응 가설을 전향 OOS 사건에서만 평가한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_name(
    "rush_negative_earnings_reaction_preregistration_v1.json"
)
DEFAULT_INPUT = ROOT / "data/runtime/action-research/rush-negative-earnings-reaction-v1.csv"
DEFAULT_REPORT = ROOT / "data/reports/rush_negative_earnings_reaction_oos_v1.json"
REQUIRED_COLUMNS = {
    "event_id", "ticker", "sector_etf", "sec_accepted_at",
    "reaction_confirmation_session", "state_observation_date", "herd_stage",
    "stock_reaction_3s", "sector_reaction_3s", "outcome_maturity_date",
    "outcome_label", "completed_cycle", "hold_terminal_value",
    "candidate_terminal_value_base", "candidate_terminal_value_stress",
    "base_round_trip_cost_bps", "stress_round_trip_cost_bps",
}


class ProspectiveHypothesisError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def load_protocol(path: Path = PROTOCOL_PATH) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    authority = protocol.get("authority", {})
    sample = protocol.get("sample_contract", {})
    if (
        protocol.get("status") != "LOCKED_BEFORE_PROSPECTIVE_OUTCOMES"
        or sample.get("allowed_role") != "PROSPECTIVE_ONLY"
        or sample.get("historical_backfill_allowed") is not False
        or authority.get("direction_evidence_admitted") is not False
        or authority.get("candidate_action_enabled") is not False
        or authority.get("operational_action") != "HOLD"
        or float(authority.get("operational_action_ratio", -1)) != 0.0
        or authority.get("blind_holdout_access") is not False
    ):
        raise ProspectiveHypothesisError("action hypothesis protocol is not fail-closed")
    return protocol


def _waiting(protocol: dict, input_path: Path) -> dict:
    return {
        "report_version": "RUSH_NEGATIVE_EARNINGS_REACTION_OOS_V1",
        "status": "WAITING_FOR_PROSPECTIVE_OOS",
        "hypothesis_id": protocol["single_hypothesis"]["id"],
        "input_path": _display_path(input_path),
        "mature_events": 0,
        "passed": False,
        "direction_evidence_admitted": False,
        "candidate_action_enabled": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
    }


def evaluate(frame: pd.DataFrame, protocol: dict) -> dict:
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ProspectiveHypothesisError(f"prospective columns missing: {sorted(missing)}")
    if frame["event_id"].duplicated().any():
        raise ProspectiveHypothesisError("duplicate prospective event_id")

    rows = frame.copy()
    for column in (
        "sec_accepted_at", "reaction_confirmation_session",
        "state_observation_date", "outcome_maturity_date",
    ):
        rows[column] = pd.to_datetime(rows[column], utc=True, errors="coerce")
    if rows[list((
        "sec_accepted_at", "reaction_confirmation_session",
        "state_observation_date", "outcome_maturity_date",
    ))].isna().any().any():
        raise ProspectiveHypothesisError("invalid prospective timestamps")

    first_date = pd.Timestamp(
        protocol["sample_contract"]["first_eligible_event_date"], tz="UTC"
    )
    if rows["sec_accepted_at"].dt.normalize().lt(first_date).any():
        raise ProspectiveHypothesisError("historical backfill is forbidden")
    hypothesis = protocol["single_hypothesis"]
    if rows["herd_stage"].ne(hypothesis["required_state"]).any():
        raise ProspectiveHypothesisError("non-Rush row entered the candidate ledger")
    if rows["state_observation_date"].gt(rows["reaction_confirmation_session"]).any():
        raise ProspectiveHypothesisError("state was observed after reaction confirmation")
    if rows["sec_accepted_at"].gt(rows["reaction_confirmation_session"]).any():
        raise ProspectiveHypothesisError("reaction was confirmed before SEC acceptance")
    if rows["outcome_maturity_date"].le(rows["reaction_confirmation_session"]).any():
        raise ProspectiveHypothesisError("outcome maturity does not follow confirmation")
    if "state_age_sessions" in rows:
        age = pd.to_numeric(rows["state_age_sessions"], errors="coerce")
        maximum_age = hypothesis["state_maximum_age_sessions"]
    else:
        # Backward-compatible fallback for early prospective fixtures that did not
        # persist the exchange-session distance explicitly.
        age = (
            rows["reaction_confirmation_session"].dt.normalize()
            - rows["state_observation_date"].dt.normalize()
        ).dt.days
        maximum_age = hypothesis["state_maximum_age_sessions"] + 2
    if age.isna().any() or age.gt(maximum_age).any():
        raise ProspectiveHypothesisError("Rush state is too old for the event")

    numeric = (
        "stock_reaction_3s", "sector_reaction_3s", "hold_terminal_value",
        "candidate_terminal_value_base", "candidate_terminal_value_stress",
        "base_round_trip_cost_bps", "stress_round_trip_cost_bps",
    )
    for column in numeric:
        rows[column] = pd.to_numeric(rows[column], errors="coerce")
    if rows[["stock_reaction_3s", "sector_reaction_3s"]].isna().any().any():
        raise ProspectiveHypothesisError("reaction values must be finite")
    gate = protocol["evaluation_gate"]
    if (
        rows["base_round_trip_cost_bps"].ne(gate["required_round_trip_cost_bps"]).any()
        or rows["stress_round_trip_cost_bps"].ne(gate["stress_round_trip_cost_bps"]).any()
    ):
        raise ProspectiveHypothesisError("locked cost assumptions changed")
    rows["residual_reaction_3s"] = (
        rows["stock_reaction_3s"] - rows["sector_reaction_3s"]
    )
    if rows["residual_reaction_3s"].gt(hypothesis["negative_reaction_maximum"]).any():
        raise ProspectiveHypothesisError("row does not meet the locked negative reaction")

    matured = rows[
        rows["outcome_label"].fillna("").ne("")
        & rows["completed_cycle"].astype(str).str.lower().isin({"true", "1"})
    ].copy()
    terminal_columns = [
        "hold_terminal_value", "candidate_terminal_value_base",
        "candidate_terminal_value_stress",
    ]
    if (
        matured[terminal_columns].isna().any().any()
        or matured[terminal_columns].le(0).any().any()
    ):
        raise ProspectiveHypothesisError("mature cycle terminal values must be positive")
    allowed_labels = {
        *protocol["outcome_contract"]["adverse_labels"],
        *protocol["outcome_contract"]["benign_labels"],
    }
    if not set(matured["outcome_label"]).issubset(allowed_labels):
        raise ProspectiveHypothesisError("unknown outcome label")
    matured["wealth_delta"] = (
        matured["candidate_terminal_value_base"] - matured["hold_terminal_value"]
    )
    matured["stress_wealth_delta"] = (
        matured["candidate_terminal_value_stress"] - matured["hold_terminal_value"]
    )
    matured["year"] = matured["sec_accepted_at"].dt.year
    matured["adverse"] = matured["outcome_label"].isin(
        protocol["outcome_contract"]["adverse_labels"]
    )
    yearly = matured.groupby("year").agg(
        events=("event_id", "count"),
        median_wealth_delta=("wealth_delta", "median"),
    ) if not matured.empty else pd.DataFrame()

    checks = {
        "mature_events": len(matured) >= gate["minimum_mature_events"],
        "distinct_tickers": matured["ticker"].nunique() >= gate["minimum_distinct_tickers"],
        "calendar_years": matured["year"].nunique() >= gate["minimum_calendar_years"],
        "positive_years": (
            int((yearly["median_wealth_delta"] > 0).sum()) >= gate["minimum_positive_years"]
            if not yearly.empty else False
        ),
        "adverse_precision": (
            float(matured["adverse"].mean()) >= gate["minimum_adverse_path_precision"]
            if not matured.empty else False
        ),
        "terminal_wealth": (
            float(matured["wealth_delta"].median()) > gate["minimum_median_terminal_wealth_delta"]
            if not matured.empty else False
        ),
        "stress_terminal_wealth": (
            float(matured["stress_wealth_delta"].median())
            > gate["minimum_median_stress_terminal_wealth_delta"]
            if not matured.empty else False
        ),
        "positive_completed_cycle_rate": (
            float(matured["stress_wealth_delta"].gt(0).mean())
            >= gate["minimum_positive_completed_cycle_rate"]
            if not matured.empty else False
        ),
    }
    passed = all(checks.values())
    return {
        "report_version": "RUSH_NEGATIVE_EARNINGS_REACTION_OOS_V1",
        "status": "PROSPECTIVE_GATE_PASSED" if passed else "PROSPECTIVE_GATE_NOT_PASSED",
        "hypothesis_id": hypothesis["id"],
        "rows": len(rows),
        "mature_events": len(matured),
        "distinct_tickers": int(matured["ticker"].nunique()),
        "calendar_years": int(matured["year"].nunique()) if not matured.empty else 0,
        "adverse_path_precision": float(matured["adverse"].mean()) if not matured.empty else None,
        "median_terminal_wealth_delta": float(matured["wealth_delta"].median()) if not matured.empty else None,
        "median_stress_terminal_wealth_delta": float(matured["stress_wealth_delta"].median()) if not matured.empty else None,
        "checks": checks,
        "passed": passed,
        "direction_evidence_admitted": passed,
        "candidate_action_enabled": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
        "survivorship_safe": False,
    }


def run(input_path: Path = DEFAULT_INPUT, protocol_path: Path = PROTOCOL_PATH) -> dict:
    protocol = load_protocol(protocol_path)
    if not input_path.is_file():
        return _waiting(protocol, input_path)
    result = evaluate(pd.read_csv(input_path), protocol)
    result["input_path"] = _display_path(input_path)
    result["input_sha256"] = _sha256(input_path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    result = run(args.input, args.protocol)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
