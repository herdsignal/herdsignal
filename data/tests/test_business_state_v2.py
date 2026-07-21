from datetime import datetime, timezone

from herd.business_guard_protocol import load_protocol as load_v1_protocol
from herd.business_state_v2 import classify_v2, entity_type, load_protocol


def test_unsupported_entity_types_fail_closed():
    protocol, _ = load_protocol()
    v1, _ = load_v1_protocol()
    for ticker, expected in (("JPM", "BANK"), ("AMT", "REIT")):
        result = classify_v2([], datetime.now(timezone.utc), ticker, protocol, v1)
        assert entity_type(ticker, protocol) == expected
        assert result["guard_state"] == "UNKNOWN"


def test_business_state_cannot_change_herd_or_sell():
    protocol, audit = load_protocol()
    assert audit["locked"] is True
    assert "BUSINESS_STATE_CHANGES_HERD" in protocol["forbidden"]
    assert "BUSINESS_STATE_CREATES_SELL" in protocol["forbidden"]
