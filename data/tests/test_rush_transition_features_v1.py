import pandas as pd

from herd.rush_transition_features_v1 import build_transition_panel, load_contract


def test_transition_uses_four_completed_week_difference():
    dates = pd.date_range("2020-01-03", periods=6, freq="W-FRI")
    weekly = pd.DataFrame({"ticker":"A", "signal_date":dates})
    for index, source in enumerate({
        "STOCK_SECTOR_RS_13W", "STOCK_SECTOR_RS_DAMAGE", "STOCK_SPY_RS_13W",
        "HIGH_52W_FAILURE", "SIGNED_VOLUME_PARTICIPATION", "MARKET_STRESS_REGIME",
        "TREND_26W_QUALITY", "TREND_13W_DECELERATION"
    }):
        weekly[source] = pd.Series(range(6), dtype=float) + index
    paths = pd.DataFrame({"ticker":["A"], "signal_date":[dates[4]], "path_label":["CONTINUATION"]})

    result = build_transition_panel(paths, weekly, load_contract())

    assert result["SECTOR_RS_DELTA_4W"].iloc[0] == 4.0
    assert result["TREND_QUALITY_DELTA_4W"].iloc[0] == 4.0
