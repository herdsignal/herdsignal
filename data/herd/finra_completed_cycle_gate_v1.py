"""상류 행동 없는 후보가 완결 사이클로 승격되지 않았는지 검증한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
GATE_PATH = Path(__file__).with_suffix(".json")
VERSION = "HERD_FINRA_COMPLETED_CYCLE_GATE_V1"


class FinraCompletedCycleGateError(ValueError):
    """불완전한 행동 후보가 완결 사이클로 승격된 경우."""


def validate_gate(gate: dict[str, Any]) -> dict[str, Any]:
    if gate.get("gate_version") != VERSION or gate.get("status") != "BLOCKED_UPSTREAM_ACTIONS_UNAVAILABLE":
        raise FinraCompletedCycleGateError("cycle gate is not blocked")
    dependencies = []
    for specification in gate["dependencies"]:
        path = (ROOT / specification["path"]).resolve()
        if hashlib.sha256(path.read_bytes()).hexdigest() != specification["sha256"]:
            raise FinraCompletedCycleGateError("cycle dependency changed")
        dependencies.append(json.loads(path.read_text()))
    decision = gate["decision"]
    if (
        dependencies[0]["decision"]["trade_rows"] != 0
        or dependencies[1]["decision"]["reentry_rows"] != 0
        or decision["completed_cycles"] != 0
        or decision["benchmark_comparisons"] != 0
        or decision["candidate_passed"] is not False
        or decision["candidate_promotable"] is not False
        or decision["blind_holdout_access"] is not False
        or decision["operational_action_ratio"] != 0.0
    ):
        raise FinraCompletedCycleGateError("incomplete candidate was promoted")
    return {"gate_version": VERSION, **decision}


if __name__ == "__main__":
    print(json.dumps(validate_gate(json.loads(GATE_PATH.read_text())), indent=2))
