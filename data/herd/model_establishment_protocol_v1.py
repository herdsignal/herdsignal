"""차세대 HERD 1~9 통합 연구 계약의 불변 조건을 검증한다."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROTOCOL_PATH = Path(__file__).with_suffix(".json")
PROTOCOL_VERSION = "HERD_MODEL_ESTABLISHMENT_V1"


class ModelEstablishmentProtocolError(ValueError):
    """모델 목표·안전 경계·채택 기준이 완화됐을 때 발생한다."""


def load_protocol(path: Path = PROTOCOL_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_protocol(protocol: dict[str, Any]) -> dict[str, Any]:
    if (
        protocol.get("protocol_version") != PROTOCOL_VERSION
        or protocol.get("status") != "LOCKED_BEFORE_INTEGRATED_PIPELINE_RESULTS"
    ):
        raise ModelEstablishmentProtocolError("integrated protocol is not locked")

    mission = protocol.get("mission", {})
    if (
        mission.get("objective")
        != "IMPROVE_TERMINAL_WEALTH_OR_SHARE_COUNT_VERSUS_MATCHED_BUY_AND_HOLD"
        or mission.get("default_action") != "HOLD"
        or mission.get("state_is_not_action") is not True
    ):
        raise ModelEstablishmentProtocolError("service mission changed")

    action = protocol.get("action_boundary", {})
    if (
        action.get("initial_fraction") != 0.05
        or action.get("maximum_cumulative_fraction", 1) > 0.15
        or action.get("full_exit_forbidden") is not True
        or action.get("leverage_forbidden") is not True
        or action.get("profit_take_without_reentry_is_incomplete") is not True
        or action.get("operational_action_ratio_before_promotion") != 0.0
    ):
        raise ModelEstablishmentProtocolError("action safety boundary weakened")

    steps = protocol.get("pipeline", [])
    if [step.get("id") for step in steps] != list(range(1, 10)):
        raise ModelEstablishmentProtocolError("pipeline order changed")

    evaluation = protocol.get("evaluation", {})
    if (
        evaluation.get("minimum_complete_oos_folds", 0) < 4
        or evaluation.get("minimum_oos_years", 0) < 5
        or evaluation.get("minimum_median_upside_capture", 0) < 0.85
        or evaluation.get("minimum_average_equity_exposure", 0) < 0.80
        or evaluation.get("maximum_pbo", 1) > 0.20
        or evaluation.get("minimum_deflated_sharpe_probability", 0) < 0.95
    ):
        raise ModelEstablishmentProtocolError("adoption gate weakened")

    boundaries = protocol.get("research_boundaries", {})
    required_true = {
        "public_research_only",
        "point_in_time_required",
        "survivorship_safe_required_for_promotion",
        "failed_hypothesis_relabeling_forbidden",
        "threshold_retuning_on_same_oos_forbidden",
        "high_herd_alone_is_not_profit_take",
        "weekly_rsi_alone_is_not_profit_take",
        "mdd_improvement_alone_is_not_success",
        "missing_metric_is_failure",
    }
    if not all(boundaries.get(key) is True for key in required_true):
        raise ModelEstablishmentProtocolError("research boundary weakened")
    if boundaries.get("blind_holdout_access") is not False:
        raise ModelEstablishmentProtocolError("blind holdout was opened")

    baseline = protocol.get("current_baseline", {})
    if (
        baseline.get("current_action_candidate") is not None
        or baseline.get("current_decision") != "NO_ADOPTABLE_ACTION_CANDIDATE"
        or baseline.get("operational_action_ratio") != 0.0
    ):
        raise ModelEstablishmentProtocolError("unverified action was promoted")

    return {
        "protocol_version": PROTOCOL_VERSION,
        "locked": True,
        "pipeline_steps": 9,
        "default_action": "HOLD",
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
    }


if __name__ == "__main__":
    print(json.dumps(validate_protocol(load_protocol()), indent=2))
