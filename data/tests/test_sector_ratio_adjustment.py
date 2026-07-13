import unittest

import pandas as pd

from herd.sector_ratio_adjustment import apply_sector_ratio, build_sector_ratio_factor


class SectorRatioAdjustmentTest(unittest.TestCase):
    def test_non_target_sector_is_neutral(self):
        index = pd.date_range("2020-01-01", periods=300, freq="B")
        prices = pd.Series(range(100, 400), index=index, dtype=float)
        factor = build_sector_ratio_factor(prices, prices, prices, "technology")
        self.assertTrue((factor == 1.0).all())

    def test_factor_is_strictly_bounded(self):
        index = pd.date_range("2020-01-01", periods=300, freq="B")
        stock = pd.Series([300 - i * 0.8 for i in range(300)], index=index)
        sector = pd.Series([300 - i * 0.4 for i in range(300)], index=index)
        market = pd.Series([100 + i * 0.2 for i in range(300)], index=index)
        factor = build_sector_ratio_factor(stock, sector, market, "energy")
        self.assertGreaterEqual(factor.min(), 0.9)
        self.assertLessEqual(factor.max(), 1.1)

    def test_adjustment_scales_common_ratio(self):
        action, ratio = apply_sector_ratio("SELL", 0.2, pd.Series({"sector_ratio_factor": 1.1}))
        self.assertEqual(action, "SELL")
        self.assertEqual(ratio, 0.22)


if __name__ == "__main__": unittest.main()
