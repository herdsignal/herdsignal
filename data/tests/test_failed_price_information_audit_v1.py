import json
from pathlib import Path

import pandas as pd

from herd.failed_price_information_audit_v1 import audit, load_protocol


def test_protocol_never_revives_rejected_features():
    protocol = load_protocol()
    assert "COMBINE_REJECTED_FEATURES" in protocol["forbidden"]
    assert protocol["policy"]["herd_formula_change_allowed"] is False


def test_audit_detects_stable_duplicate_without_outcomes(monkeypatch, tmp_path: Path):
    panel = tmp_path / "panel.csv"
    other = tmp_path / "other.csv"
    protocol_path = tmp_path / "protocol.json"
    rows = []
    for fold in range(3):
        for index in range(220):
            rows.append({
                "ticker": f"T{index % 20}",
                "episode_id": f"{fold}-{index}",
                "last_observed_session": f"202{fold}-01-01",
                "fold_id": fold,
                "a": index,
                "b": index * 2,
                "c": (index * 17) % 31,
            })
    pd.DataFrame(rows).to_csv(panel, index=False)
    pd.DataFrame({"ticker": ["X"]}).to_csv(other, index=False)
    source = load_protocol()
    source["comparable_panel"]["path"] = "panel.csv"
    source["comparable_panel"]["features"] = [
        {"id": "A", "column": "a", "role": "x"},
        {"id": "B", "column": "b", "role": "x"},
        {"id": "C", "column": "c", "role": "y"},
    ]
    source["non_comparable_families"] = [
        {"id": "OTHER", "path": "other.csv", "reason": "different"}
    ]
    protocol_path.write_text(json.dumps(source), encoding="utf-8")
    monkeypatch.setattr(
        "herd.failed_price_information_audit_v1.ROOT", tmp_path
    )
    report = audit(protocol_path)
    assert report["family_redundant"] is True
    assert report["stable_redundant_pairs"][0]["left"] == "a"
    assert report["feature_admission_count"] == 0
    assert report["outcome_used_for_selection"] is False
