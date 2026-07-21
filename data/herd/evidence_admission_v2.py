"""V2 OOS 결과만으로 증거 채택 원장의 안전 상태를 검증한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = Path(__file__).with_name("evidence_admission_registry_v2.json")


class EvidenceAdmissionV2Error(ValueError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_evidence_admission_v2(path: Path = REGISTRY_PATH) -> tuple[dict, dict]:
    registry = json.loads(path.read_text(encoding="utf-8"))
    if registry.get("registry_version") != "HERD_EVIDENCE_ADMISSION_V2" \
            or registry.get("status") != "POST_OOS_DECISIONS_LOCKED":
        raise EvidenceAdmissionV2Error("admission registry is not locked")
    for artifact in registry.get("source_artifacts", []):
        source = (ROOT / artifact["path"]).resolve()
        if not source.is_relative_to(ROOT) or not source.is_file() \
                or _sha256(source) != artifact["sha256"]:
            raise EvidenceAdmissionV2Error(f"source artifact mismatch: {artifact['path']}")
    result = json.loads((ROOT / "data/reports/profit_take_oos_v2.json").read_text(encoding="utf-8"))
    admitted = [item for item in registry["profit_take_families"] if item["authorized"]]
    state = registry["candidate_state"]
    if len(admitted) != state["admitted_profit_take_count"] \
            or bool(result["passing_hypotheses"]) != bool(admitted):
        raise EvidenceAdmissionV2Error("admission does not match OOS result")
    if not admitted and (
        state["profit_take_authorized"]
        or state["completed_cycle_allowed"]
        or state["blind_holdout_allowed"]
        or state["operational_action_ratio"] != 0.0
    ):
        raise EvidenceAdmissionV2Error("failed evidence enabled an action")
    return registry, {
        "admitted_profit_take_count": len(admitted),
        "completed_cycle_allowed": state["completed_cycle_allowed"],
        "operational_action_ratio": state["operational_action_ratio"],
    }
