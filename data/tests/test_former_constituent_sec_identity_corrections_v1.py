from pathlib import Path

import pandas as pd

from herd.former_constituent_sec_identity_corrections_v1 import (
    discover_disagreements,
    load_protocol,
)


def test_discovers_the_two_company_name_cik_mismatches():
    protocol = load_protocol(require_mapping=True)
    rows = discover_disagreements(protocol)

    assert rows["ticker"].tolist() == ["WHR", "ZION"]
    assert rows.set_index("ticker").loc["WHR", "current_sec_cik"] == "0000106640"
    assert rows.set_index("ticker").loc["ZION", "current_sec_cik"] == "0000109380"


def test_protocol_does_not_authorize_outcome_or_action():
    protocol = load_protocol()

    assert protocol["future_price_outcomes_read"] is False
    assert protocol["future_earnings_outcomes_read"] is False
    assert protocol["operational_action_ratio"] == 0.0
