import pandas as pd

from herd.profit_take_oos_v2 import extract_episode_events, evaluate_events
from herd.profit_take_measurements_v2 import load_registry


def test_episode_extractor_counts_one_event_until_reset():
    index = pd.date_range("2020-01-31", periods=8, freq="ME")
    values = pd.Series([0.5, 0.81, 0.95, 0.88, 0.69, 0.75, 0.91, 0.92], index=index)
    events = extract_episode_events(values, threshold=0.8, reset=0.7)
    assert list(events) == [index[1], index[6]]


def test_empty_evidence_never_authorizes_profit_take():
    registry, _ = load_registry()
    columns = [
        "hypothesis_id", "threshold", "group", "horizon_days", "ticker",
        "fold_id", "forward_excess_return", "forward_trough_return",
        "forward_upside_return",
    ]
    table, summary = evaluate_events(pd.DataFrame(columns=columns), registry)
    assert table.empty
    assert summary["profit_take_authorized"] is False
    assert summary["operational_action_ratio"] == 0.0
