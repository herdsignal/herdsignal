import unittest
from contextlib import nullcontext
from unittest.mock import MagicMock, patch

import pandas as pd

from herd import saver
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

    def test_save_uses_source_price_session_instead_of_runtime_calendar_date(self):
        prices = pd.DataFrame({
            "Date": ["2026-07-14"],
            "Open": [170.0],
            "High": [174.0],
            "Low": [169.0],
            "Close": [173.0],
            "Volume": [1_000],
        })
        result = {
            "score": 62.0,
            "stage": "Herd Drift",
            "indicators": {
                "weekly_rsi": 50,
                "monthly_rsi": 50,
                "position_52w": 50,
                "ma200_deviation": 50,
                "volume_strength": 50,
                "ma200_weekly": 50,
            },
        }
        session = MagicMock()

        with (
            patch.object(saver, "_get_session_factory", return_value=lambda: nullcontext(session)),
            patch.object(saver, "_upsert_stock"),
            patch.object(saver, "_upsert_herd_score") as upsert_score,
            patch.object(saver, "_upsert_herd_indicators") as upsert_indicators,
            patch.object(saver, "_upsert_daily_price"),
        ):
            saved = saver.save_herd_result("NVDA", result, prices)

        self.assertTrue(saved)
        self.assertEqual(upsert_score.call_args.args[-1].isoformat(), "2026-07-14")
        self.assertEqual(upsert_indicators.call_args.args[-1].isoformat(), "2026-07-14")


if __name__ == "__main__":
    unittest.main()
