import pandas as pd

from herd.herd_candidate_features_v2 import _daily_features
from herd.independent_rush_evidence_v1 import evaluate, load_protocol


def test_protocol_locks_four_single_hypotheses_and_blocks_combination():
    protocol = load_protocol()
    assert len(protocol["hypotheses"]) == 4
    assert "COMBINE_FAILED_HYPOTHESES" in protocol["forbidden"]
    assert protocol["sec_pit_business_state"]["missing_is_fail_closed"] is True


def test_evaluation_does_not_count_temporary_pullback_as_primary_success():
    protocol = load_protocol()
    rows = []
    for date, label, value in (
        ("2017-01-01", "LARGE_PULLBACK", 1.0),
        ("2017-02-01", "CONTINUATION", 0.0),
        ("2017-03-01", "TEMPORARY_PULLBACK", 100.0),
    ):
        rows.append({
            "last_observed_session": pd.Timestamp(date), "path_label": label,
            "SECTOR_RS_DAMAGE_DELTA_4W": value,
            "TREND_QUALITY_DELTA_4W": -value,
            "PARTICIPATION_WEAKENING_DELTA_4W": value,
            "MARKET_STRESS_DELTA_4W": value,
        })
    result = evaluate(pd.DataFrame(rows), protocol)
    assert set(result["treatment_events"]) == {1}
    assert set(result["control_events"]) == {1}
    assert not result["admitted"].any()


def test_daily_feature_alignment_sorts_union_of_mismatched_calendars():
    def frame(dates):
        return pd.DataFrame({
            "Date": pd.to_datetime(dates), "Adj Close": [100.0 + i for i in range(len(dates))],
            "Volume": [1000.0] * len(dates),
        })
    stock = frame(["2020-01-02", "2020-01-06"])
    sector = frame(["2020-01-03", "2020-01-06"])
    spy = frame(["2020-01-02", "2020-01-03", "2020-01-06"])
    result = _daily_features(stock, sector, spy)
    assert result.index.is_monotonic_increasing
