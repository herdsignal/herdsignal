import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_rejected_preholdout_result_cannot_authorize_actions():
    report = json.loads(
        (ROOT / "data/reports/vnext_preholdout_evaluation_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["status"] == "PATH_MODEL_REJECTED_PREHOLDOUT"
    assert report["decision"] == "NO_ADOPTABLE_CANDIDATE"
    assert report["operational_action_ratio"] == 0.0
    assert report["blind_holdout_access"] is False
    assert report["path_model_passed"] is False
    assert "PATH_MODEL_PREHOLDOUT_GATE_FAILED" in report["promotion_blockers"]
