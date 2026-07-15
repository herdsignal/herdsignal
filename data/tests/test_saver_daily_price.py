import unittest

import pandas as pd

from herd.saver import _latest_valid_price


class LatestValidPriceTest(unittest.TestCase):
    def test_uses_previous_row_when_latest_ohlc_is_missing(self):
        prices = pd.DataFrame({
            "Date": ["2026-07-14", "2026-07-15"],
            "Open": [170.0, float("nan")],
            "High": [174.0, float("nan")],
            "Low": [169.0, float("nan")],
            "Close": [173.0, float("nan")],
            "Volume": [1_000, 0],
        })

        row, price_date = _latest_valid_price(prices)

        self.assertEqual(price_date.isoformat(), "2026-07-14")
        self.assertEqual(row["Close"], 173.0)

    def test_supports_date_index(self):
        prices = pd.DataFrame(
            {
                "Open": [10.0],
                "High": [11.0],
                "Low": [9.0],
                "Close": [10.5],
            },
            index=pd.to_datetime(["2026-07-14"]),
        )

        _, price_date = _latest_valid_price(prices)

        self.assertEqual(price_date.isoformat(), "2026-07-14")

    def test_rejects_data_without_valid_ohlc(self):
        prices = pd.DataFrame({
            "Date": ["2026-07-15"],
            "Open": [float("nan")],
            "High": [float("nan")],
            "Low": [float("nan")],
            "Close": [float("nan")],
        })

        with self.assertRaisesRegex(ValueError, "유효한 OHLC"):
            _latest_valid_price(prices)


if __name__ == "__main__":
    unittest.main()
