import pandas as pd

from herd.reentry_worthwhile_target_v1 import build_target, load_target


def test_target_exports_no_future_oracle_fields_and_excludes_ambiguous_paths():
    events = pd.DataFrame([
        {"ticker": "A", "episode_id": "A1", "signal_date": "2020-01-01", "path_label": "LARGE_PULLBACK", "stress_constrained_available": True, "stress_constrained_reentry_date": "2020-02-01"},
        {"ticker": "B", "episode_id": "B1", "signal_date": "2020-01-01", "path_label": "CONTINUATION", "stress_constrained_available": False, "stress_constrained_reentry_date": None},
        {"ticker": "C", "episode_id": "C1", "signal_date": "2020-01-01", "path_label": "UNRESOLVED", "stress_constrained_available": False, "stress_constrained_reentry_date": None},
    ])
    safe, report = build_target(events, load_target())
    assert safe.columns.tolist() == ["ticker", "episode_id", "signal_date", "target_label"]
    assert safe["target_label"].tolist() == ["REENTRY_WORTHWHILE", "HOLD_WINNER"]
    assert "stress_constrained_reentry_date" not in safe
    assert report["excluded_events"] == 1
    assert report["future_outcome_columns_exported"] is False
