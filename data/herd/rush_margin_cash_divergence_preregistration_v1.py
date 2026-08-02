"""Validate the locked margin-versus-cash Rush hypothesis without opening outcomes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from herd.instrument_class_ledger_v1 import latest_pit_feature


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
REPORT_PATH = ROOT / "data/reports/rush_margin_cash_divergence_preregistration_v1.json"
CONTRACT_VERSION = "HERD_RUSH_MARGIN_CASH_DIVERGENCE_PREREGISTRATION_V1"
EXPECTED_FEATURES = {"net_margin_yoy_change", "operating_cash_flow_yoy"}
EXPECTED_FORBIDDEN = {
    "USE_PRICE_EXTENSION_OR_RSI_AS_AN_ADDITIONAL_FEATURE",
    "ADD_DEBT_GUIDANCE_FORM4_FINRA_OR_13F_AFTER_RESULTS",
    "CHANGE_SCORE_WEIGHTS_OR_PERCENTILE_AFTER_RESULTS",
    "FIT_SCALER_OR_CUTOFF_ON_TEST_DATA",
    "IMPUTE_MISSING_PIT_FEATURES",
    "USE_CURRENT_GICS_AS_POINT_IN_TIME_EVIDENCE",
    "SELECT_ANOTHER_FIXED_POLICY_AFTER_RESULTS",
    "CLAIM_SURVIVORSHIP_SAFE",
    "AUTHORIZE_OPERATIONAL_ACTION",
    "OPEN_BLIND_HOLDOUT",
}


class MarginCashPreregistrationError(RuntimeError):
    """Raised when the preregistered economic hypothesis is weakened."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise MarginCashPreregistrationError(f"missing preregistration input: {relative}")
    return path


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if (
        contract.get("contract_version") != CONTRACT_VERSION
        or contract.get("status") != "LOCKED_BEFORE_OOS_TARGET_ACCESS"
        or contract.get("hypothesis_id")
        != "RUSH_MARGIN_CASH_DIVERGENCE_RELATIVE_REBALANCE_V1"
    ):
        raise MarginCashPreregistrationError("interaction hypothesis is not locked")
    if len(contract.get("inputs", [])) != 8:
        raise MarginCashPreregistrationError("preregistration input set is incomplete")
    for item in contract["inputs"]:
        if _sha256(_rooted(item["path"])) != item.get("sha256"):
            raise MarginCashPreregistrationError(
                f"pinned preregistration input changed: {item['path']}"
            )

    hypothesis = contract.get("economic_hypothesis", {})
    if (
        hypothesis.get("state_is_population_filter_not_direction_evidence") is not True
        or set(hypothesis.get("feature_families", []))
        != {"PIT_MARGIN_TREND", "PIT_OPERATING_CASH_FLOW_TREND"}
        or hypothesis.get("feature_family_count") != 2
        or hypothesis.get("prior_failures_do_not_authorize_direction") is not True
    ):
        raise MarginCashPreregistrationError("economic hypothesis boundary changed")

    population = contract.get("population", {})
    if (
        population.get("required_security_structure_class")
        != "OPERATING_COMPANY_EQUITY"
        or population.get("required_universe_role") != "PRIMARY"
        or population.get("leveraged_or_inverse_etp_excluded") is not True
        or population.get("etfs_excluded") is not True
        or population.get("maximum_events_per_ticker_year") != 2
        or population.get("current_gics_not_used") is not True
    ):
        raise MarginCashPreregistrationError("hypothesis population changed")

    features = contract.get("point_in_time_features", {})
    if (
        set(features.get("inputs", [])) != EXPECTED_FEATURES
        or features.get("required_corpus_status") != "PIT_FACTS_READY"
        or features.get("same_day_filing_available_next_observation") is not True
        or features.get("restatement_backfill_forbidden") is not True
        or features.get("missing_policy") != "NOT_ELIGIBLE_NO_IMPUTATION"
    ):
        raise MarginCashPreregistrationError("point-in-time feature boundary changed")

    score = contract.get("score", {})
    if (
        score.get("training_winsorization") != [0.01, 0.99]
        or score.get("training_scaler") != "MEDIAN_AND_IQR"
        or score.get("zero_iqr_policy") != "FAIL_FOLD_CLOSED"
        or score.get("formula")
        != "Z_TRAIN_WINSORIZED_NET_MARGIN_YOY_CHANGE_MINUS_Z_TRAIN_WINSORIZED_OPERATING_CASH_FLOW_YOY"
        or score.get("candidate_cutoff") != "TRAINING_SCORE_90TH_PERCENTILE"
        or score.get("fixed_weights")
        != {"net_margin_yoy_change": 1.0, "operating_cash_flow_yoy": -1.0}
        or score.get("fit_model") is not False
        or score.get("hyperparameter_search") is not False
    ):
        raise MarginCashPreregistrationError("fixed interaction score changed")

    policy = contract.get("policy", {})
    if (
        policy.get("track") != "RELATIVE_REBALANCE_REVIEW"
        or policy.get("policy_id") != "TRIM_TO_SPY_HORIZON"
        or policy.get("reallocation_fraction") != 0.05
        or policy.get("destination") != "SPY"
        or policy.get("terminal_horizon_sessions") != 126
        or policy.get("cooldown_sessions") != 63
        or policy.get("base_one_way_cost_bps") != 10
        or policy.get("stress_one_way_cost_bps") != [25, 50]
        or policy.get("full_exit_forbidden") is not True
        or policy.get("leverage_forbidden") is not True
    ):
        raise MarginCashPreregistrationError("fixed relative-rebalance policy changed")

    oos = contract.get("oos_design", {})
    if (
        oos.get("test_folds") != [f"F{number:02d}" for number in range(1, 10)]
        or oos.get("purge_sessions") != 126
        or oos.get("embargo_sessions") != 20
        or oos.get("scaling_and_cutoff_fit_on_training_only") is not True
        or oos.get("same_oos_retuning_forbidden") is not True
        or oos.get("current_sample_role") != "PREHOLDOUT_FALSIFICATION_ONLY"
        or oos.get("prospective_confirmation_required_for_user_action") is not True
    ):
        raise MarginCashPreregistrationError("OOS design boundary changed")

    gates = contract.get("target_and_gates", {})
    if (
        gates.get("primary_target")
        != "NORMALIZED_NET_TERMINAL_WEALTH_DELTA_VERSUS_MATCHED_HOLD"
        or gates.get("primary_cost_bps") != 10
        or gates.get("minimum_candidates") != 15
        or gates.get("minimum_candidate_tickers") != 10
        or gates.get("minimum_directional_folds") != 6
        or gates.get("minimum_positive_net_value_rate") != 0.6
        or gates.get("maximum_one_sided_ticker_block_bootstrap_p_value") != 0.1
        or gates.get("stress_50bps_median_must_not_be_below") != 0.0
        or gates.get("compare_all_locked_fixed_baselines_on_same_candidates") is not True
        or gates.get("all_gates_required") is not True
    ):
        raise MarginCashPreregistrationError("economic adoption gates changed")
    if set(contract.get("forbidden", [])) != EXPECTED_FORBIDDEN:
        raise MarginCashPreregistrationError("preregistration forbidden set changed")
    firewall = contract.get("firewall", {})
    if (
        firewall.get("oos_target_accessed") is not False
        or firewall.get("direction_evidence_admitted") is not False
        or firewall.get("operational_action") != "HOLD"
        or firewall.get("operational_action_ratio") != 0.0
        or firewall.get("survivorship_safe") is not False
        or firewall.get("blind_holdout_access") is not False
    ):
        raise MarginCashPreregistrationError("preregistration firewall weakened")
    return contract


def _input(contract: dict[str, Any], suffix: str) -> Path:
    matches = [item for item in contract["inputs"] if item["path"].endswith(suffix)]
    if len(matches) != 1:
        raise MarginCashPreregistrationError(f"ambiguous preregistration input: {suffix}")
    return _rooted(matches[0]["path"])


def build_feature_readiness(contract: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    events = pd.read_csv(
        _input(contract, "instrument_class_event_ledger_v1.csv.gz"),
        parse_dates=["signal_date", "observation_session"],
    )
    population = contract["population"]
    events = events.loc[
        (events["security_structure_class"] == population["required_security_structure_class"])
        & (events["universe_role"] == population["required_universe_role"])
    ].copy()
    events["calendar_year"] = events["signal_date"].dt.year
    if (
        events.groupby(["ticker", "calendar_year"]).size().max()
        > population["maximum_events_per_ticker_year"]
    ):
        raise MarginCashPreregistrationError("event action budget exceeded")

    features = pd.read_csv(
        _input(contract, "business_state_features_v2.csv"),
        parse_dates=["month_end", "latest_fact_accepted_at"],
    )
    features["ticker"] = features["ticker"].astype(str).str.upper()
    rows = []
    for event in events.itertuples(index=False):
        feature = latest_pit_feature(features, event.ticker, event.observation_session)
        ready = feature is not None and all(
            pd.notna(feature[column]) for column in EXPECTED_FEATURES
        )
        rows.append(
            {
                "ticker": event.ticker,
                "fold_id": event.fold_id,
                "signal_date": event.signal_date,
                "observation_session": event.observation_session,
                "feature_ready": ready,
                "feature_month_end": feature["month_end"] if feature is not None else pd.NaT,
                "feature_accepted_at": feature["latest_fact_accepted_at"] if feature is not None else pd.NaT,
            }
        )
    readiness = pd.DataFrame(rows)
    eligible = readiness.loc[readiness["feature_ready"]]
    fold_counts = (
        eligible.groupby("fold_id").size().reindex(contract["oos_design"]["test_folds"], fill_value=0)
    )
    checks = {
        "minimum_feature_ready_events": len(eligible)
        >= population["minimum_feature_ready_events"],
        "minimum_feature_ready_tickers": eligible["ticker"].nunique()
        >= population["minimum_feature_ready_tickers"],
        "minimum_nonempty_folds": int((fold_counts > 0).sum())
        >= population["minimum_nonempty_folds"],
    }
    summary = {
        "population_events": len(readiness),
        "feature_ready_events": len(eligible),
        "feature_ready_tickers": int(eligible["ticker"].nunique()),
        "feature_ready_fold_counts": {key: int(value) for key, value in fold_counts.items()},
        "coverage_rate": len(eligible) / len(readiness) if len(readiness) else 0.0,
        "readiness_checks": checks,
        "all_readiness_checks_passed": all(checks.values()),
    }
    return readiness, summary


def run() -> dict[str, Any]:
    contract = load_contract()
    _, readiness = build_feature_readiness(contract)
    report = {
        "report_version": CONTRACT_VERSION,
        "contract_sha256": _sha256(CONTRACT_PATH),
        "hypothesis_id": contract["hypothesis_id"],
        "status": (
            "PREREGISTERED_READY_FOR_PREHOLDOUT_OOS"
            if readiness["all_readiness_checks_passed"]
            else "PREREGISTERED_BLOCKED_INSUFFICIENT_PIT_COVERAGE"
        ),
        **readiness,
        "score_values_generated": False,
        "candidate_cutoff_fitted": False,
        "oos_target_accessed": False,
        "oos_execution_allowed": readiness["all_readiness_checks_passed"],
        "direction_evidence_admitted": False,
        "policy_promoted": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
        "survivorship_safe": False,
        "blind_holdout_access": False,
        "next_stage": (
            "IMPLEMENT_TRAIN_ONLY_SCALING_AND_TICKER_TIME_BLOCKED_OOS_EVALUATOR"
            if readiness["all_readiness_checks_passed"]
            else "EXPAND_POINT_IN_TIME_FEATURE_COVERAGE_WITHOUT_OPENING_TARGETS"
        ),
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
