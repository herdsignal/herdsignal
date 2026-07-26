"""검증된 익절 현금 없이 재진입 연구가 실행되지 않았는지 검증한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
GATE_PATH = Path(__file__).with_suffix(".json")
VERSION = "HERD_FINRA_CONDITIONAL_REENTRY_GATE_V1"


class FinraConditionalReentryGateError(ValueError):
    """존재하지 않는 익절 현금으로 재진입을 실행한 경우."""


def validate_gate(gate: dict[str, Any]) -> dict[str, Any]:
    if gate.get("gate_version") != VERSION or gate.get("status") != "BLOCKED_NO_VALIDATED_TRIM_CASH":
        raise FinraConditionalReentryGateError("reentry gate is not blocked")
    specification = gate["dependency"]
    path = (ROOT / specification["path"]).resolve()
    if hashlib.sha256(path.read_bytes()).hexdigest() != specification["sha256"]:
        raise FinraConditionalReentryGateError("trim dependency changed")
    trim = json.loads(path.read_text())
    decision = gate["decision"]
    if (
        trim["decision"]["trade_rows"] != 0
        or decision["eligible_cash_events"] != 0
        or decision["reentry_simulation_executed"] is not False
        or decision["reentry_rows"] != 0
        or decision["candidate_passed"] is not False
        or decision["blind_holdout_access"] is not False
        or decision["operational_action_ratio"] != 0.0
    ):
        raise FinraConditionalReentryGateError("reentry was fabricated without trim cash")
    return {"gate_version": VERSION, **decision}


if __name__ == "__main__":
    print(json.dumps(validate_gate(json.loads(GATE_PATH.read_text())), indent=2))
