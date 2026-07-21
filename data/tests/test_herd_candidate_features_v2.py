import numpy as np
import pandas as pd

from herd.herd_candidate_features_v2 import _daily_features, _trend_quality


def test_trend_quality_rewards_smooth_positive_trend():
    smooth = pd.Series(np.exp(np.linspace(1, 2, 26)))
    noisy = smooth * np.where(np.arange(26) % 2, 1.2, .8)
    assert _trend_quality(smooth) > _trend_quality(noisy)


def test_declining_trend_quality_is_zero():
    decline = pd.Series(np.exp(np.linspace(2, 1, 26)))
    assert _trend_quality(decline) == 0.0


def test_daily_features_do_not_look_ahead():
    dates = pd.bdate_range("2020-01-01", periods=320)

    def frame(scale: float) -> pd.DataFrame:
        close = np.linspace(100, 180, len(dates)) * scale
        return pd.DataFrame({"Date": dates, "Adj Close": close, "Volume": 1_000_000})

    stock, sector, spy = frame(1.0), frame(.8), frame(1.2)
    baseline = _daily_features(stock, sector, spy)
    stock.loc[stock.index[-20:], "Adj Close"] *= 10
    changed = _daily_features(stock, sector, spy)

    cutoff = dates[-21]
    pd.testing.assert_frame_equal(baseline.loc[:cutoff], changed.loc[:cutoff])
