"""상태 관찰 축적과 행동 후보 shadow 개방을 분리해 판정한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
REPORT_PATH = ROOT / "data/reports/prospective_readiness_gate_v2.json"
VERSION = "HERD_PROSPECTIVE_READINESS_GATE_V2"


class ProspectiveReadinessGateError(ValueError):
    pass


def _load(item: dict[str, str]) -> dict[str, Any]:
    path = (ROOT / item["path"]).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ProspectiveReadinessGateError(f"missing input: {item['path']}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
        raise ProspectiveReadinessGateError(f"input changed: {item['path']}")
    return json.loads(path.read_text())


def build_report(output_path: Path = REPORT_PATH) -> dict[str, Any]:
    contract = json.loads(CONTRACT_PATH.read_text())
    if (
        contract.get("gate_version") != VERSION
        or contract.get("status") != "LOCKED_BEFORE_READINESS_RESULT"
    ):
        raise ProspectiveReadinessGateError("readiness gate is not locked")
    cycle, bridge, protocol = [_load(item) for item in contract["inputs"]]
    state_ready = (
        bridge["historical_context"]["ready"] is True
        and bridge["candidate_selection"] is False
    )
    action_ready = (
        cycle["status"] == "READY_FOR_COMPLETED_CYCLE"
        and protocol["current_readiness"] != "BLOCKED_BY_PREHOLDOUT_DECISION"
    )
    if action_ready:
        raise ProspectiveReadinessGateError(
            "action shadow must be opened by a separate human-approved release"
        )
    prospective = bridge["prospective"]
    report = {
        "report_version": VERSION,
        "status": "STATE_OBSERVATION_ACTIVE_ACTION_SHADOW_BLOCKED",
        "state_observation_collection": state_ready,
        "action_candidate_shadow": False,
        "observation_dates": prospective["observation_dates"],
        "observation_records": prospective["observation_records"],
        "matured_outcomes": prospective["matured_outcomes"],
        "comparison_ready_by_horizon":
            prospective["comparison_ready_by_horizon"],
        "drift_monitor_status": "NOT_APPLICABLE_NO_ACTION_CANDIDATE",
        "next_gate": "INDEPENDENT_PROFIT_TAKE_AND_REENTRY_EVIDENCE",
        "blind_holdout_access": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(build_report(), indent=2))
