from datetime import datetime, timezone

import pytest

from herd.expectation_business_features_v1 import dilution_as_of, load_protocol


def test_dilution_uses_only_facts_visible_as_of_boundary():
    facts = [
        {"value": 100, "period_end": datetime(2022, 12, 31).date(), "accepted_at": datetime(2023, 2, 1, tzinfo=timezone.utc), "priority": 0, "concept": "shares"},
        {"value": 110, "period_end": datetime(2023, 12, 31).date(), "accepted_at": datetime(2024, 2, 1, tzinfo=timezone.utc), "priority": 0, "concept": "shares"},
        {"value": 220, "period_end": datetime(2024, 12, 31).date(), "accepted_at": datetime(2025, 2, 1, tzinfo=timezone.utc), "priority": 0, "concept": "shares"},
    ]
    assert dilution_as_of(facts, datetime(2024, 3, 1, tzinfo=timezone.utc)) == pytest.approx(0.10)


def test_protocol_forbids_zero_fill_and_sell_authority():
    forbidden = load_protocol()["forbidden"]
    assert "FILL_MISSING_DILUTION_WITH_ZERO" in forbidden
    assert "CREATE_SELL_SIGNAL" in forbidden


def test_unreconciled_corporate_action_is_not_called_dilution():
    facts = [
        {"value": 100, "period_end": datetime(2022, 12, 31).date(), "accepted_at": datetime(2023, 2, 1, tzinfo=timezone.utc), "priority": 0, "concept": "shares"},
        {"value": 300, "period_end": datetime(2023, 12, 31).date(), "accepted_at": datetime(2024, 2, 1, tzinfo=timezone.utc), "priority": 0, "concept": "shares"},
    ]
    assert dilution_as_of(facts, datetime(2024, 3, 1, tzinfo=timezone.utc)) is None
