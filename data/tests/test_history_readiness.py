import unittest

import pandas as pd

from herd.history_readiness import is_history_ready


def _price_frame(periods: int) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=periods)
    return pd.DataFrame({"Date": dates, "Close": range(1, periods + 1)})


class HistoryReadinessTest(unittest.TestCase):
    def test_history_is_not_ready_before_28_months(self) -> None:
        self.assertFalse(is_history_ready(_price_frame(500)))

    def test_history_is_ready_after_all_indicator_minimums(self) -> None:
        self.assertTrue(is_history_ready(_price_frame(620)))

    def test_history_without_date_is_not_ready(self) -> None:
        self.assertFalse(is_history_ready(pd.DataFrame({"Close": [1, 2, 3]})))
