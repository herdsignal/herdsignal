import json
from pathlib import Path

import pandas as pd

from herd.ticker_disjoint_earnings_reaction_oos_v2 import load_contract


ROOT = Path(__file__).resolve().parents[2]


def test_v2_reuses_the_exact_v1_formula_without_combining_samples():
    contract = load_contract()
    v1 = json.loads((ROOT / "data/herd/ticker_disjoint_earnings_reaction_oos_v1.json").read_text())

    for field in ("event_binding", "economic_policy", "outcome_label", "gate"):
        assert contract[field] == v1[field]
    assert contract["sample_policy"]["combine_with_v1_for_gate"] is False
    assert contract["sample_policy"]["threshold_retuning"] is False
    assert contract["operational_action_ratio"] == 0.0


def test_v2_universe_is_ticker_disjoint_from_v1():
    current = set(pd.read_csv(ROOT / "data/reports/ticker_disjoint_earnings_oos_expansion_v2.csv")["ticker"])
    v1 = set(pd.read_csv(ROOT / "data/reports/ticker_disjoint_earnings_oos_universe_v1.csv")["ticker"])

    assert len(current) == 21
    assert current.isdisjoint(v1)
