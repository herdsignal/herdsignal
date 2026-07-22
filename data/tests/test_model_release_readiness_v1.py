import json
from pathlib import Path

from herd.model_release_readiness_v1 import evaluate


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "data/herd/model_release_readiness_v1.json").read_text())


def test_release_gate_keeps_holdout_sealed_and_production_disabled() -> None:
    report = evaluate(PROTOCOL)
    assert report["status"] == "RESEARCH_BLOCKED_NO_RELEASABLE_MODEL"
    assert report["checks"]["candidate_exists"] is False
    assert report["checks"]["direction_evidence_admitted"] is False
    assert report["checks"]["completed_cycle_passed"] is False
    assert report["checks"]["base_and_stress_costs_passed"] is False
    assert report["checks"]["walk_forward_and_era_validation_passed"] is False
    assert report["checks"]["survivorship_safe"] is False
    assert report["checks"]["blind_holdout_still_sealed"] is True
    assert report["legacy_generalization_reused_for_new_candidate"] is False
    assert report["blind_holdout_evaluation_count"] == 0
    assert report["blind_holdout_access"] is False
    assert report["production_signal_allowed"] is False
    assert report["operational_action_ratio"] == 0
