import json
from pathlib import Path

from herd.core_direction_research_return_v1 import build


ROOT = Path(__file__).resolve().parents[2]


def test_core_return_uses_economic_targets_without_direction_labels() -> None:
    protocol = json.loads((ROOT / "data/herd/core_direction_research_return_v1.json").read_text())
    targets, report = build(protocol)
    assert targets["episode_id"].is_unique
    assert set(targets["direction_label"]) == {"NONE"}
    assert set(targets["research_use"]) == {"DISCOVERY_TARGET_DEFINITION_ONLY_NOT_OOS"}
    assert report["target_ledger_ready"] is True
    assert report["direction_evidence_admitted"] is False
    assert report["blind_holdout_opened"] is False


def test_core_return_quarantines_failed_formulas_and_sec_direction() -> None:
    protocol = json.loads((ROOT / "data/herd/core_direction_research_return_v1.json").read_text())
    _, report = build(protocol)
    assert report["failed_exact_hypotheses_quarantined"] == len(
        protocol["failed_exact_hypotheses_not_reusable"]
    )
    assert report["existing_pre_damage_features_retained"] == 0
    assert report["sec_direction_authority"] is False
    assert report["new_hypothesis_preregistered"] is False
    assert report["next_decision"] == "PREREGISTER_ONE_NEW_NONREDUNDANT_ECONOMIC_HYPOTHESIS"
    assert protocol["sample_boundary"]["economic_target_ledger_may_count_as_future_oos"] is False
    assert protocol["sample_boundary"]["new_hypothesis_requires_fresh_locked_oos_sample"] is True
