import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.timing_evidence_oos import (
    ETF_TICKERS,
    _forward_trough_return,
    _holm_adjust,
    build_scores,
)


class TimingEvidenceOosTest(unittest.TestCase):
    def test_scores_keep_only_equities_and_month_end(self):
        dates = pd.bdate_range("2018-01-01", periods=800)
        tickers = ["AAA", "BBB", *sorted(ETF_TICKERS)]
        closes = pd.DataFrame(
            {
                ticker: 100 + np.arange(len(dates)) * (index + 1) / 100
                + np.sin(np.arange(len(dates)) / (10 + index))
                for index, ticker in enumerate(tickers)
            },
            index=dates,
        )
        volumes = pd.DataFrame(
            {
                ticker: 1_000_000 + np.arange(len(dates)) * (index + 1)
                for index, ticker in enumerate(tickers)
            },
            index=dates,
        )
        scores = build_scores(closes, volumes)

        self.assertEqual(set(scores), {
            "PRICE_EXTENSION",
            "TREND_MATURITY",
            "RELATIVE_OVERHEAT",
            "PARTICIPATION",
            "MARKET_RISK",
        })
        for frame in scores.values():
            self.assertEqual(list(frame.columns), ["AAA", "BBB"])
            self.assertTrue(all(frame.index.is_month_end))

    def test_holm_adjustment_is_monotonic_in_sorted_p_values(self):
        rows = [
            {"raw_p_value": 0.04},
            {"raw_p_value": 0.01},
            {"raw_p_value": 0.03},
        ]
        _holm_adjust(rows)
        ordered = sorted(rows, key=lambda row: row["raw_p_value"])
        self.assertEqual(
            [row["holm_p_value"] for row in ordered],
            sorted(row["holm_p_value"] for row in ordered),
        )
        self.assertAlmostEqual(ordered[0]["holm_p_value"], 0.03)

    def test_future_price_change_does_not_change_prior_scores(self):
        dates = pd.bdate_range("2018-01-01", periods=900)
        tickers = ["AAA", "BBB", *sorted(ETF_TICKERS)]
        closes = pd.DataFrame(
            {
                ticker: 100 + np.arange(len(dates)) * (index + 1) / 100
                + np.sin(np.arange(len(dates)) / (9 + index))
                for index, ticker in enumerate(tickers)
            },
            index=dates,
        )
        volumes = pd.DataFrame(1_000_000, index=dates, columns=tickers)
        original = build_scores(closes, volumes)
        changed = closes.copy()
        boundary = dates[-40]
        changed.loc[boundary:, "AAA"] *= 10
        recalculated = build_scores(changed, volumes)

        for family in original:
            pd.testing.assert_frame_equal(
                original[family].loc[:boundary].iloc[:-1],
                recalculated[family].loc[:boundary].iloc[:-1],
            )

    def test_forward_trough_uses_daily_path_after_signal(self):
        dates = pd.to_datetime([
            "2020-01-31", "2020-02-03", "2020-02-14", "2020-02-28"
        ])
        daily = pd.DataFrame({"AAA": [100, 98, 70, 90]}, index=dates)
        result = _forward_trough_return(
            daily, pd.DatetimeIndex([dates[0]]), 1
        )
        self.assertAlmostEqual(result.loc[dates[0], "AAA"], -0.3)
