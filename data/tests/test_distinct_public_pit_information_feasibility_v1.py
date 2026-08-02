import copy
import json
from pathlib import Path

import pytest

from herd.distinct_public_pit_information_feasibility_v1 import (
    DistinctPublicPitFeasibilityError,
    PROTOCOL_PATH,
    audit,
)


def _protocol() -> dict:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def test_current_feasibility_is_fail_closed() -> None:
    report = audit(_protocol())
    assert report["price_outcomes_opened"] is False
    assert report["direction_hypothesis_allowed"] is False
    assert report["operational_action_ratio"] == 0.0
    assert report["allowed_role"] == "CORPORATE_DAMAGE_VETO_RESEARCH_ONLY"


def test_profit_take_authority_cannot_be_enabled() -> None:
    protocol = copy.deepcopy(_protocol())
    protocol["authority"]["operational_action_ratio"] = 0.05
    with pytest.raises(DistinctPublicPitFeasibilityError):
        audit(protocol)


def test_candidate_role_cannot_be_promoted_early() -> None:
    protocol = copy.deepcopy(_protocol())
    protocol["candidate"]["economic_role"] = "PROFIT_TAKE_SIGNAL"
    with pytest.raises(DistinctPublicPitFeasibilityError):
        audit(protocol)


def test_report_is_reproducible() -> None:
    expected_path = Path("data/reports/distinct_public_pit_information_feasibility_v1.json")
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    assert audit(_protocol()) == expected
