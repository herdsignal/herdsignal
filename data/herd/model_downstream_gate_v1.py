"""통과 증거가 없을 때 후속 매매·모델 단계를 fail-closed로 유지한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
GATE_VERSION = "HERD_MODEL_DOWNSTREAM_GATE_V1"


class ModelDownstreamGateError(ValueError):
    """선행 게이트 없이 후속 단계가 실행 또는 승격됐을 때 발생한다."""


def _load_pinned(specification: dict[str, Any]) -> dict[str, Any]:
    path = (ROOT / specification["path"]).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ModelDownstreamGateError(f"missing dependency: {specification['path']}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != specification["sha256"]:
        raise ModelDownstreamGateError(f"hash mismatch: {specification['path']}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_downstream_gate(gate: dict[str, Any]) -> dict[str, Any]:
    if (
        gate.get("gate_version") != GATE_VERSION
        or gate.get("status") != "BLOCKED_UPSTREAM_FAIL_CLOSED"
        or gate.get("stage_id") not in {5, 6, 7, 8, 9}
    ):
        raise ModelDownstreamGateError("downstream gate is invalid")

    dependencies = [_load_pinned(item) for item in gate["dependencies"]]
    blocker = gate["blocker"]
    if blocker.get("required_value") != blocker.get("actual_value"):
        blocker_confirmed = True
    else:
        blocker_confirmed = False
    if not blocker_confirmed:
        raise ModelDownstreamGateError("declared upstream blocker is not present")

    execution = gate["execution"]
    authority = gate["authority"]
    if (
        execution.get("attempted") is not False
        or execution.get("trades_simulated") is not False
        or execution.get("parameters_selected") is not False
        or authority.get("candidate_promoted") is not False
        or authority.get("blind_holdout_access") is not False
        or authority.get("operational_action_ratio") != 0.0
    ):
        raise ModelDownstreamGateError("blocked stage executed or widened authority")

    if gate["stage_id"] == 5:
        admission = dependencies[0]["admission_summary"]
        if (
            blocker.get("field") != "direction_evidence_admitted"
            or blocker.get("actual_value") != admission["direction_evidence_admitted"]
            or blocker.get("required_value") != 1
        ):
            raise ModelDownstreamGateError("sparse profit-take blocker mismatch")

    return {
        "stage_id": gate["stage_id"],
        "stage_name": gate["stage_name"],
        "status": gate["status"],
        "blocker": blocker["field"],
        "required": blocker["required_value"],
        "actual": blocker["actual_value"],
        "trades_simulated": False,
        "candidate_promoted": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
    }


def load_downstream_gate(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    gate = json.loads(path.read_text(encoding="utf-8"))
    return gate, validate_downstream_gate(gate)
