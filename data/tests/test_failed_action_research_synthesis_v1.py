import copy
import json

import pytest

from herd.failed_action_research_synthesis_v1 import (
    PROTOCOL,
    FailedActionSynthesisError,
    synthesize,
)


def test_failed_action_synthesis_blocks_new_hypothesis_and_action() -> None:
    report = synthesize()

    assert report["target_validity_audit"]["economic_opportunity_exists"] is True
    assert report["target_validity_audit"]["target_is_currently_separable"] is False
    assert report["economic_family_redundancy_audit"]["locked_rejected_experiments"] == 11
    assert report["policy_opportunity_cost_audit"][
        "all_non_control_medians_non_negative"
    ] is False
    assert report["distinct_information_availability_decision"][
        "historical_direction_source_ready_count"
    ] == 0
    assert report["next_stage"]["new_hypothesis_allowed"] is False
    assert report["operational_action_ratio"] == 0.0


def test_failed_action_synthesis_preserves_all_economic_domains() -> None:
    report = synthesize()
    domains = {
        row["domain"]: row["experiment_count"]
        for row in report["economic_family_redundancy_audit"]["domains"]
    }
    assert domains == {
        "PRICE_DERIVED": 6,
        "PUBLIC_CORPORATE_PIT": 4,
        "PERSONAL_POLICY": 1,
    }


def test_failed_action_synthesis_rejects_unlocked_protocol(tmp_path) -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    changed = copy.deepcopy(protocol)
    changed["status"] = "EDITABLE"
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(FailedActionSynthesisError, match="not locked"):
        synthesize(path)
