import copy
import json

import pytest

from herd.survivorship_readiness_v2 import (
    PROTOCOL_PATH,
    SurvivorshipReadinessV2Error,
    validate_survivorship_readiness_v2,
)


def test_latest_public_universe_gaps_are_measured_and_fail_closed():
    audit = validate_survivorship_readiness_v2(json.loads(PROTOCOL_PATH.read_text()))
    assert audit["historical_tickers"] == 1128
    assert audit["official_events_verified"] == 336
    assert audit["official_events_unresolved"] == 16
    assert audit["replay_errors"] == 0
    assert audit["identity_tickers"] == 528
    assert audit["price_tickers"] == 481
    assert audit["price_snapshot_failure_count"] > 0
    assert audit["checks"]["price_snapshot_failures"] is False
    assert audit["survivorship_safe"] is False
    assert audit["promotion_allowed"] is False


def test_public_reconstruction_cannot_claim_survivorship_safe():
    protocol = json.loads(PROTOCOL_PATH.read_text())
    changed = copy.deepcopy(protocol)
    changed["decision"]["survivorship_safe"] = True
    with pytest.raises(SurvivorshipReadinessV2Error, match="promoted"):
        validate_survivorship_readiness_v2(changed)
