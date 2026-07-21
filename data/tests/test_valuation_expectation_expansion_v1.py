from datetime import datetime, timezone

import numpy as np
import pandas as pd

from herd.valuation_expectation_expansion_v1 import load_protocol, prior_window_percentile, shares_as_of


def test_percentile_never_reads_current_or_future_values():
    values = pd.Series([*range(36), 100, -100])
    result = prior_window_percentile(values)
    assert np.isnan(result.iloc[35])
    assert result.iloc[36] == 1.0
    assert result.iloc[37] == 0.0


def test_shares_exclude_fact_accepted_after_boundary():
    facts = [
        {"value": 100, "period_end": datetime(2023, 12, 31).date(), "accepted_at": datetime(2024, 2, 1, tzinfo=timezone.utc), "priority": 0},
        {"value": 200, "period_end": datetime(2024, 3, 31).date(), "accepted_at": datetime(2024, 5, 1, tzinfo=timezone.utc), "priority": 0},
    ]
    assert shares_as_of(facts, datetime(2024, 3, 1, tzinfo=timezone.utc)) == 100


def test_expensive_alone_cannot_create_sell():
    assert "EXPENSIVE_ALONE_CREATES_SELL" in load_protocol()["forbidden"]
