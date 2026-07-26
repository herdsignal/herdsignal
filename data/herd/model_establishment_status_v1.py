"""1~9 통합 모델 확립 파이프라인의 재현 가능한 최종 상태를 검증한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
STATUS_PATH = Path(__file__).with_suffix(".json")
STATUS_VERSION = "HERD_MODEL_ESTABLISHMENT_STATUS_V1"


class ModelEstablishmentStatusError(ValueError):
    """통합 상태와 고정 단계 산출물이 달라졌을 때 발생한다."""


def validate_status(status: dict[str, Any]) -> dict[str, Any]:
    if (
        status.get("status_version") != STATUS_VERSION
        or status.get("overall_decision")
        != "STATE_OBSERVATION_ONLY_NO_ADOPTABLE_ACTION_CANDIDATE"
    ):
        raise ModelEstablishmentStatusError("integrated status is invalid")

    stages = status["stages"]
    if [stage["id"] for stage in stages] != list(range(1, 10)):
        raise ModelEstablishmentStatusError("stage order is incomplete")
    for stage in stages:
        path = (ROOT / stage["path"]).resolve()
        if (
            not path.is_relative_to(ROOT)
            or not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != stage["sha256"]
        ):
            raise ModelEstablishmentStatusError(f"stage artifact changed: {stage['id']}")

    facts = status["facts"]
    if (
        facts.get("direction_evidence_admitted") != 0
        or facts.get("risk_context_admitted") != 1
        or facts.get("blind_holdout_evaluations") != 0
        or facts.get("survivorship_safe") is not False
        or facts.get("operational_action_ratio") != 0.0
    ):
        raise ModelEstablishmentStatusError("research authority was widened")

    if set(status["next_research"]["forbidden"]) != {
        "RETUNE_FAILED_THRESHOLDS_ON_SAME_OOS",
        "COMBINE_REJECTED_FEATURES",
        "OPEN_BLIND_HOLDOUT",
        "ENABLE_OPERATIONAL_BUY_OR_PROFIT_TAKE",
    }:
        raise ModelEstablishmentStatusError("next-research safety boundary changed")

    return {
        "status_version": STATUS_VERSION,
        "stages_verified": len(stages),
        "overall_decision": status["overall_decision"],
        **facts,
        "next_priority": status["next_research"]["priority"],
    }


if __name__ == "__main__":
    print(json.dumps(validate_status(json.loads(STATUS_PATH.read_text())), indent=2))
