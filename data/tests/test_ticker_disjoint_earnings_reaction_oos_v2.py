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


def test_published_v2_failure_remains_fail_closed():
    report = json.loads((ROOT / "data/reports/ticker_disjoint_earnings_reaction_oos_v2.json").read_text())
    gate = json.loads((ROOT / "data/reports/ticker_disjoint_earnings_reaction_oos_v2_gate.json").read_text())

    assert report["status"] == "INDEPENDENT_HISTORICAL_OOS_FAILED"
    assert report["passed"] is False
    assert report["combined_with_v1_for_gate"] is False
    assert report["thresholds_retuned"] is False
    assert report["median_terminal_wealth_delta"] < 0
    assert gate["prospective_confirmation_allowed"] is False
    assert gate["operational_action_ratio"] == 0.0
