"""V3 독립 증거가 없으면 5% 사이클과 Buy & Hold 비교를 실행하지 않는다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = Path(__file__).with_name("evidence_admission_registry_v3.json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_v3_registry(path: Path = REGISTRY_PATH) -> tuple[dict, dict]:
    registry = json.loads(path.read_text(encoding="utf-8"))
    if registry.get("registry_version") != "HERD_EVIDENCE_ADMISSION_V3" \
            or registry.get("status") != "POST_OOS_DECISIONS_LOCKED":
        raise ValueError("V3 evidence registry is not locked")
    for artifact in registry["source_artifacts"]:
        source = (ROOT / artifact["path"]).resolve()
        if not source.is_relative_to(ROOT) or not source.is_file() or _sha256(source) != artifact["sha256"]:
            raise ValueError(f"V3 source mismatch: {artifact['path']}")
    result = json.loads((ROOT / "data/reports/opportunity_oos_v1.json").read_text(encoding="utf-8"))
    admission = registry["admission"]
    if admission["continuation_shields"] != result["passing_continuation_shields"] \
            or admission["pullback_evidence"] != result["passing_pullback_evidence"]:
        raise ValueError("V3 admission differs from OOS decision")
    return registry, {
        "continuation_shields": len(admission["continuation_shields"]),
        "pullback_evidence": len(admission["pullback_evidence"]),
    }


def evaluate_cycle_gate() -> dict:
    registry, audit = load_v3_registry()
    admission = registry["admission"]
    pullback_ready = bool(admission["pullback_evidence"])
    reentry_ready = bool(admission["reentry_evidence"])
    allowed = pullback_ready and reentry_ready
    return {
        "gate_version": "HERD_OPPORTUNITY_CYCLE_GATE_V3",
        "status": "READY_FOR_5_PERCENT_CYCLE" if allowed else "BLOCKED_MISSING_OPPORTUNITY_OR_REENTRY_EVIDENCE",
        "admission_audit": audit,
        "pullback_evidence_ready": pullback_ready,
        "reentry_evidence_ready": reentry_ready,
        "initial_profit_take_fraction": 0.05 if allowed else 0.0,
        "five_percent_cycle_executed": False,
        "buy_hold_comparison_executed": False,
        "blocked_experiment_is_performance_failure": False,
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = evaluate_cycle_gate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
