"""Form 4 비정례 다중 매도–S1 Rush 단일 가설의 변경 방지 계약."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")
VERSION = "HERD_SEC_FORM4_NONROUTINE_SALE_RUSH_PREREGISTRATION_V1"


class Form4SaleRushPreregistrationError(ValueError):
    """사전등록 입력 또는 연구 경계가 바뀐 경우."""


def validate_preregistration(protocol: dict[str, Any]) -> dict[str, Any]:
    if (
        protocol.get("protocol_version") != VERSION
        or protocol.get("status") != "LOCKED_BEFORE_FEATURE_OUTCOME_JOIN"
    ):
        raise Form4SaleRushPreregistrationError("hypothesis is not locked")

    for specification in protocol["inputs"]:
        path = (ROOT / specification["path"]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise Form4SaleRushPreregistrationError(
                f"missing input: {specification['path']}"
            )
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != specification["sha256"]:
            raise Form4SaleRushPreregistrationError(
                f"hash mismatch: {specification['path']}"
            )

    exposure = protocol["exposure"]
    outcome = protocol["outcome"]
    gate = protocol["adoption_gate"]
    boundary = protocol["decision_boundary"]
    if (
        exposure["lookback_calendar_days"] != 30
        or exposure["minimum_distinct_reporting_owners"] != 2
        or exposure["same_day_use_forbidden"] is not True
        or exposure["transaction_amount_or_owner_role_weighting"] != "NONE"
        or outcome["horizon_sessions"] != 63
        or outcome["outcome_must_end_inside_fold"] is not True
        or len(protocol["oos_folds"]) != 4
        or gate["minimum_pooled_adverse_risk_difference"] != 0.05
        or gate["minimum_pooled_relative_risk"] != 1.25
        or boundary["single_hypothesis_only"] is not True
        or boundary["threshold_retuning_after_results"] is not False
        or boundary["combine_with_rejected_features"] is not False
        or boundary["historical_pass_can_authorize_action"] is not False
        or boundary["blind_holdout_access"] is not False
        or boundary["survivorship_safe"] is not False
        or boundary["operational_action_ratio"] != 0.0
    ):
        raise Form4SaleRushPreregistrationError("research boundary was widened")

    return {
        "protocol_version": VERSION,
        "hypothesis": exposure["name"],
        "lookback_calendar_days": exposure["lookback_calendar_days"],
        "minimum_distinct_reporting_owners": exposure[
            "minimum_distinct_reporting_owners"
        ],
        "folds": len(protocol["oos_folds"]),
        "outcome_peeking": False,
        "action_authority": False,
        "operational_action_ratio": 0.0,
    }


if __name__ == "__main__":
    print(
        json.dumps(
            validate_preregistration(json.loads(PROTOCOL_PATH.read_text())),
            indent=2,
        )
    )
