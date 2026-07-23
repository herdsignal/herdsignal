import json
from pathlib import Path

import pandas as pd
import pytest

from herd.sec_guidance_lower_oos_v2 import _forward_path, run


ROOT = Path(__file__).resolve().parents[2]


def test_forward_path_uses_first_strictly_later_session_adjusted_open():
    frame = pd.DataFrame({
        "Date": pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"]),
        "Adj Open": [10.0, 20.0, 22.0],
        "Adj Close": [11.0, 22.0, 19.8],
    }).set_index("Date")
    result = _forward_path(
        frame, pd.Timestamp("2026-01-02T20:00:00Z"), horizon=2
    )
    assert result["execution_session"] == pd.Timestamp("2026-01-05")
    assert result["terminal_return"] == pytest.approx(-0.01)
    assert result["max_drawdown"] == pytest.approx(-0.1)


def test_live_oos_keeps_action_authority_blocked(monkeypatch):
    monkeypatch.chdir(ROOT)
    protocol = json.loads(
        (ROOT / "data/herd/sec_guidance_lower_oos_v2.json").read_text(
            encoding="utf-8"
        )
    )
    panel, issuer_effects, report = run(protocol)
    assert not panel.empty
    assert not issuer_effects.empty
    assert report["price_outcomes_observed"] is True
    assert report["operational_action_authority"] is False
    assert report["operational_action_ratio"] == 0.0
    assert report["blind_holdout_access"] is False
    assert report["decision"] in {
        "ADMIT_FUNDAMENTAL_DAMAGE_VETO_CANDIDATE",
        "REJECT_GUIDANCE_LOWER_HYPOTHESIS",
    }


def test_report_matches_locked_gate_without_threshold_tuning():
    report = json.loads(
        (ROOT / "data/reports/sec_guidance_lower_oos_v2.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["adoption_gate_passed"] == all(report["gate_checks"].values())
    assert report["operational_action_authority"] is False
