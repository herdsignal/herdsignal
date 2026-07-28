"""독립 OOS 가설 판정을 하나의 변경 불가 증거 원장으로 통합한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
REPORT_PATH = ROOT / "data/reports/evidence_admission_registry_v10.json"
VERSION = "HERD_EVIDENCE_ADMISSION_V10"


class EvidenceAdmissionV10Error(ValueError):
    """증거 출처나 승격 경계가 바뀐 경우."""


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_hashed(item: dict[str, str]) -> dict[str, Any]:
    path = (ROOT / item["path"]).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise EvidenceAdmissionV10Error(f"missing input: {item['path']}")
    if _hash(path) != item["sha256"]:
        raise EvidenceAdmissionV10Error(f"input changed: {item['path']}")
    return json.loads(path.read_text())


def build_report(output_path: Path = REPORT_PATH) -> dict[str, Any]:
    contract = json.loads(CONTRACT_PATH.read_text())
    if (
        contract.get("registry_version") != VERSION
        or contract.get("status")
        != "LOCKED_BEFORE_CONSOLIDATED_ADMISSION_RESULT"
    ):
        raise EvidenceAdmissionV10Error("registry is not locked")
    firewall = contract["firewall"]
    if (
        firewall["blind_holdout_access"] is not False
        or firewall["completed_cycle_allowed"] is not False
        or firewall["operational_action"] != "HOLD"
        or firewall["operational_action_ratio"] != 0.0
    ):
        raise EvidenceAdmissionV10Error("action firewall was widened")

    failed_map, family_oos = [
        _read_hashed(item) for item in contract["inputs"]
    ]
    experiments = failed_map["experiments"]
    if any(item["decision"] != "REJECTED" for item in experiments):
        raise EvidenceAdmissionV10Error(
            "failed-hypothesis map contains a non-rejected decision"
        )
    for item in experiments:
        source = item["source"]
        path = (ROOT / source["path"]).resolve()
        if not path.is_file() or _hash(path) != source["sha256"]:
            raise EvidenceAdmissionV10Error(
                f"hypothesis source changed: {item['id']}"
            )
    admitted = family_oos["admitted_families"]
    if (
        admitted
        or family_oos["combination_allowed"] is not False
        or family_oos["direction_evidence_admitted"] is not False
    ):
        raise EvidenceAdmissionV10Error(
            "family OOS result widened admission authority"
        )

    report = {
        "report_version": VERSION,
        "status": "NO_INDEPENDENT_PROFIT_TAKE_EVIDENCE_ADMITTED",
        "adjudicated_hypotheses": len(experiments),
        "rejected_hypotheses": [item["id"] for item in experiments],
        "tested_state_families": sorted(
            family_oos["universe_results"]["PRIMARY"].keys()
        ),
        "admitted_families": [],
        "combination_allowed": False,
        "next_gate": "NEW_ECONOMIC_INFORMATION_ON_NEW_OOS_SAMPLE",
        "completed_cycle_allowed": False,
        "blind_holdout_access": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(build_report(), indent=2))
