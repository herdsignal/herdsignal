"""방향 증거 없이 5% 익절 시뮬레이션이 실행되지 않았는지 검증한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
GATE_PATH = Path(__file__).with_suffix(".json")
VERSION = "HERD_FINRA_FIVE_PERCENT_TRIM_GATE_V1"


class FinraFivePercentTrimGateError(ValueError):
    """방향 게이트 실패 후 거래가 실행된 경우."""


def validate_gate(gate: dict[str, Any]) -> dict[str, Any]:
    if (
        gate.get("gate_version") != VERSION
        or gate.get("status") != "BLOCKED_DIRECTION_EVIDENCE_FAILED"
    ):
        raise FinraFivePercentTrimGateError("trim gate is not fail-closed")
    specification = gate["input"]
    path = (ROOT / specification["path"]).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise FinraFivePercentTrimGateError("missing direction report")
    if hashlib.sha256(path.read_bytes()).hexdigest() != specification["sha256"]:
        raise FinraFivePercentTrimGateError("direction report hash changed")
    report = json.loads(path.read_text())
    decision = gate["decision"]
    if (
        report["historical_gate_passed"] is not False
        or decision["simulation_executed"] is not False
        or decision["trade_rows"] != 0
        or decision["buy_and_hold_comparison_executed"] is not False
        or decision["cost_stress_executed"] is not False
        or decision["candidate_passed"] is not False
        or decision["blind_holdout_access"] is not False
        or decision["operational_action_ratio"] != 0.0
    ):
        raise FinraFivePercentTrimGateError("failed direction evidence reached trading")
    return {"gate_version": VERSION, **decision}


if __name__ == "__main__":
    print(json.dumps(validate_gate(json.loads(GATE_PATH.read_text())), indent=2))
