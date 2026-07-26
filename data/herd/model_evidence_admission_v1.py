"""서로 다른 증거군의 독립 OOS 판정을 역할별로 통합한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = Path(__file__).with_suffix(".json")
REGISTRY_VERSION = "HERD_MODEL_EVIDENCE_ADMISSION_V1"


class ModelEvidenceAdmissionError(ValueError):
    """실패한 증거를 승격하거나 역할을 바꿨을 때 발생한다."""


def _load_result(specification: dict[str, Any]) -> dict[str, Any]:
    path = (ROOT / specification["result_path"]).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ModelEvidenceAdmissionError(f"missing evidence: {specification['result_path']}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != specification["result_sha256"]:
        raise ModelEvidenceAdmissionError(f"hash mismatch: {specification['result_path']}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_registry(registry: dict[str, Any]) -> dict[str, Any]:
    if (
        registry.get("registry_version") != REGISTRY_VERSION
        or registry.get("status") != "POST_OOS_DECISIONS_PINNED"
    ):
        raise ModelEvidenceAdmissionError("evidence registry is not pinned")

    families = {family["id"]: family for family in registry["families"]}
    if len(families) != len(registry["families"]):
        raise ModelEvidenceAdmissionError("duplicate evidence family")
    results = {identifier: _load_result(specification) for identifier, specification in families.items()}

    if (
        results["PRICE_AND_RELATIVE_RUSH_TRANSITION"].get("admitted_count") != 0
        or results["PIT_INSIDER_PURCHASE_SUPPORT"].get("result", {}).get("passed") is not False
        or results["PIT_MANAGEMENT_GUIDANCE_LOWER"].get("adoption_gate_passed") is not False
        or results["EXPECTATION_AND_IDIOSYNCRATIC_DAMAGE"].get("passed_evidence_count") != 0
    ):
        raise ModelEvidenceAdmissionError("source OOS decision changed")
    if (
        results["STOCK_DOWNSIDE_RISK"].get("families", {}).get("MARKET_RISK", {}).get("decision")
        != "PASS_STOCK_DOWNSIDE_COMPONENT_TO_CAP_ABLATION"
    ):
        raise ModelEvidenceAdmissionError("risk context decision changed")

    admitted_roles = [
        family["role"] for family in families.values() if family.get("admitted") is True
    ]
    if admitted_roles != ["RISK_CAP_ABLATION_ONLY"]:
        raise ModelEvidenceAdmissionError("failed evidence was admitted or role widened")

    summary = registry["admission_summary"]
    boundary = registry["claim_boundary"]
    if (
        summary
        != {
            "direction_evidence_admitted": 0,
            "reentry_support_admitted": 0,
            "business_veto_admitted": 0,
            "risk_context_admitted": 1,
            "profit_take_gate_passed": False,
            "reentry_gate_passed": False,
        }
        or boundary.get("survivorship_safe") is not False
        or boundary.get("blind_holdout_access") is not False
        or boundary.get("operational_action_ratio") != 0.0
        or boundary.get("next_stage_may_execute_trades") is not False
    ):
        raise ModelEvidenceAdmissionError("admission boundary was widened")

    return {
        "registry_version": REGISTRY_VERSION,
        **summary,
        "admitted_roles": admitted_roles,
        "survivorship_safe": False,
        "operational_action_ratio": 0.0,
    }


def load_registry(path: Path = REGISTRY_PATH) -> tuple[dict[str, Any], dict[str, Any]]:
    registry = json.loads(path.read_text(encoding="utf-8"))
    return registry, validate_registry(registry)


if __name__ == "__main__":
    print(json.dumps(validate_registry(json.loads(REGISTRY_PATH.read_text())), indent=2))
