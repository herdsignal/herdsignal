import unittest

import numpy as np
import pandas as pd

from indicators.wilder_rsi import wilder_rsi


class WilderRsiContractTest(unittest.TestCase):
    def test_mixed_prices_match_frozen_operational_values(self) -> None:
        close = pd.Series([
            44, 44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42,
            45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03,
            46.41, 46.22,
        ], dtype=float)
        expected = np.array([
            np.nan, 100.0, 94.6466809421842, 94.7197400487409,
            83.65434497069518, 86.00237756797345, 87.3602598733411,
            88.03523897435832, 88.79870763035734, 89.72540100775568,
            90.22315340664342, 86.64452465338826, 87.05205377647087,
            79.24025410373326, 82.01317112962604, 82.01317112962604,
            77.02653371799495, 77.18658618450142, 79.16649508766967,
            75.63209469550246,
        ])

        actual = wilder_rsi(close, 14)

        self.assertIsNotNone(actual)
        np.testing.assert_allclose(actual.to_numpy(), expected, rtol=0, atol=1e-12,
                                   equal_nan=True)
        self.assertEqual(actual.name, "RSI_14")

    def test_monotonic_and_flat_edge_cases_remain_compatible(self) -> None:
        rising = wilder_rsi(pd.Series(range(1, 21), dtype=float), 14)
        falling = wilder_rsi(pd.Series(range(20, 0, -1), dtype=float), 14)
        flat = wilder_rsi(pd.Series([10.0] * 20), 14)

        self.assertTrue((rising.iloc[1:] == 100.0).all())
        self.assertTrue((falling.iloc[1:] == 0.0).all())
        self.assertTrue(flat.isna().all())

    def test_short_input_and_invalid_period_fail_as_contract_requires(self) -> None:
        self.assertIsNone(wilder_rsi(pd.Series(range(14), dtype=float), 14))
        with self.assertRaisesRegex(ValueError, "period must be positive"):
            wilder_rsi(pd.Series(range(20), dtype=float), 0)
