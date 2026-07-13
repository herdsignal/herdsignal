import unittest

import pandas as pd

from herd.earnings_point_in_time import build_eps_multiplier_series, validate_earnings_record


class EarningsPointInTimeTest(unittest.TestCase):
    def test_rejects_period_only_record(self):
        valid, reason = validate_earnings_record({"period": "2024-03-31", "actual": 2, "estimate": 1})
        self.assertFalse(valid)
        self.assertEqual(reason, "missing_required_field")

    def test_applies_surprise_only_after_announcement(self):
        records = [
            {"announcement_date": "2024-04-20", "actual": 2, "estimate": 1, "date_source": "company_ir"},
            {"announcement_date": "2024-07-20", "actual": 2, "estimate": 1, "date_source": "company_ir"},
        ]
        index = pd.to_datetime(["2024-04-19", "2024-07-19", "2024-07-21"])
        series, audit = build_eps_multiplier_series(records, index)
        self.assertEqual(series.iloc[0], 1.0)
        self.assertEqual(series.iloc[1], 1.0)
        self.assertLess(series.iloc[2], 1.0)
        self.assertEqual(audit["status"], "ACTIVE")

    def test_excludes_untrusted_date_source(self):
        record = {"announcement_date": "2024-04-20", "actual": 2, "estimate": 1, "date_source": "estimated_lag"}
        series, audit = build_eps_multiplier_series([record], pd.to_datetime(["2024-05-01"]))
        self.assertEqual(series.iloc[0], 1.0)
        self.assertEqual(audit["status"], "EXCLUDED_NO_TRUSTED_ANNOUNCEMENT_DATES")


if __name__ == "__main__": unittest.main()
