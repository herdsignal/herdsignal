"""FINRA–Rush 단일 가설의 사전등록 경계를 검증한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")
VERSION = "HERD_FINRA_RUSH_DIVERGENCE_PREREGISTRATION_V1"


class FinraRushDivergencePreregistrationError(ValueError):
    """사전등록이 변조됐거나 행동 권한을 넓힌 경우."""


def validate_preregistration(protocol: dict[str, Any]) -> dict[str, Any]:
    if (
        protocol.get("protocol_version") != VERSION
        or protocol.get("status") != "LOCKED_BEFORE_FEATURE_OUTCOME_JOIN"
    ):
        raise FinraRushDivergencePreregistrationError("hypothesis is not preregistered")
    for specification in protocol["inputs"]:
        path = (ROOT / specification["path"]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise FinraRushDivergencePreregistrationError(f"missing input: {specification['path']}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != specification["sha256"]:
            raise FinraRushDivergencePreregistrationError(f"hash mismatch: {specification['path']}")
    exposure = protocol["exposure"]
    evaluation = protocol["evaluation"]
    boundary = protocol["decision_boundary"]
    if (
        len(exposure["conditions_all_required"]) != 3
        or exposure["same_day_use_forbidden"] is not True
        or evaluation["prospective_confirmation_required_for_adoption"] is not True
        or evaluation["interim_outcome_peeking_forbidden"] is not True
        or boundary["one_hypothesis_only"] is not True
        or boundary["threshold_retuning_after_results"] is not False
        or boundary["combine_with_rejected_features"] is not False
        or boundary["historical_pass_can_authorize_action"] is not False
        or boundary["blind_holdout_access"] is not False
        or boundary["operational_action_ratio"] != 0.0
    ):
        raise FinraRushDivergencePreregistrationError("research boundary was widened")
    return {
        "protocol_version": VERSION,
        "hypothesis": exposure["name"],
        "conditions": len(exposure["conditions_all_required"]),
        "historical_role": evaluation["historical_role"],
        "prospective_confirmation_months": evaluation["minimum_prospective_months"],
        "outcome_peeking": False,
        "historical_action_authority": False,
        "operational_action_ratio": 0.0,
    }


if __name__ == "__main__":
    print(json.dumps(validate_preregistration(json.loads(PROTOCOL_PATH.read_text())), indent=2))
