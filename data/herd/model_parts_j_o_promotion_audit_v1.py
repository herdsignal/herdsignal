"""후보 부재 시 Part J~O가 권한을 넓히지 않았는지 감사한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AUDIT_PATH = Path(__file__).with_suffix(".json")
VERSION = "HERD_MODEL_PARTS_J_O_PROMOTION_AUDIT_V1"


class ModelPartsJOPromotionAuditError(ValueError):
    """후보 없이 모델 또는 운영 행동이 승격된 경우."""


def validate_audit(audit: dict[str, Any]) -> dict[str, Any]:
    if (
        audit.get("audit_version") != VERSION
        or audit.get("status") != "STATE_OBSERVATION_ONLY_NO_ACTION_CANDIDATE"
    ):
        raise ModelPartsJOPromotionAuditError("promotion audit status changed")
    loaded = {}
    for specification in audit["inputs"]:
        path = (ROOT / specification["path"]).resolve()
        if hashlib.sha256(path.read_bytes()).hexdigest() != specification["sha256"]:
            raise ModelPartsJOPromotionAuditError("promotion input changed")
        loaded[path.name] = json.loads(path.read_text())
    parts = audit["parts"]
    decision = audit["decision"]
    if (
        loaded["finra_completed_cycle_gate_v1.json"]["decision"]["candidate_promotable"] is not False
        or loaded["survivorship_readiness_v2.json"]["decision"]["survivorship_safe"] is not False
        or parts["J_COMBINATION"]["candidate_combinations"] != 0
        or parts["J_COMBINATION"]["executed"] is not False
        or parts["K_GENERALIZATION"]["evaluations"] != 0
        or parts["L_BLIND_HOLDOUT"]["access_count"] != 0
        or parts["L_BLIND_HOLDOUT"]["opened"] is not False
        or parts["M_SHADOW"]["action_shadow_enabled"] is not False
        or parts["N_PERSONALIZATION"]["action_model_personalized"] is not False
        or parts["O_MVP"]["buy_or_profit_take_recommendation"] is not False
        or decision["new_model_name"] != "UNASSIGNED_UNTIL_PROMOTION"
        or decision["survivorship_safe"] is not False
        or decision["blind_holdout_access"] is not False
        or decision["operational_action_ratio"] != 0.0
    ):
        raise ModelPartsJOPromotionAuditError("unsupported action model was promoted")
    return {
        "audit_version": VERSION,
        "completed_parts": list(parts),
        "mvp_scope": parts["O_MVP"]["allowed_scope"],
        "new_model_name": decision["new_model_name"],
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
    }


if __name__ == "__main__":
    print(json.dumps(validate_audit(json.loads(AUDIT_PATH.read_text())), indent=2))
