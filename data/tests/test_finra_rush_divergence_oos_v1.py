import json

from herd.finra_rush_divergence_oos_v1 import REPORT_PATH


def test_finra_rush_oos_report_remains_non_operational():
    report = json.loads(REPORT_PATH.read_text())
    assert report["status"] == "RECENT_PREHOLDOUT_SENSITIVITY_COMPLETE"
    assert report["rows"] == 2082
    assert report["exposed_events"] == 125
    assert report["historical_gate_passed"] is False
    assert report["checks"]["minimum_directional_folds"] is False
    assert report["checks"]["minimum_risk_difference"] is False
    assert report["adoption_allowed"] is False
    assert report["prospective_confirmation_required"] is True
    assert report["survivorship_safe"] is False
    assert report["blind_holdout_access"] is False
    assert report["operational_action_ratio"] == 0.0


def test_finra_rush_oos_panel_hash_is_pinned():
    report = json.loads(REPORT_PATH.read_text())
    import hashlib
    from pathlib import Path

    root = REPORT_PATH.parents[2]
    panel = root / report["panel_path"]
    assert hashlib.sha256(panel.read_bytes()).hexdigest() == report["panel_sha256"]
