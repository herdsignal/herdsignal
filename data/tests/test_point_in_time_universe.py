import tempfile
import unittest
from datetime import date
from pathlib import Path

from herd.point_in_time_universe import audit_survivorship_coverage, constituents_at, load_universe_history


class PointInTimeUniverseTest(unittest.TestCase):
    def test_selects_constituents_at_historical_date(self):
        records = [
            {"ticker": "OLD", "start_date": date(2010, 1, 1), "end_date": date(2020, 1, 1)},
            {"ticker": "NEW", "start_date": date(2020, 1, 2), "end_date": None},
        ]
        self.assertEqual(constituents_at(records, date(2019, 1, 1)), ["OLD"])
        self.assertEqual(constituents_at(records, date(2021, 1, 1)), ["NEW"])

    def test_audit_requires_non_survivor_records(self):
        record = {"ticker": "OLD", "start_date": date(2010, 1, 1), "end_date": date(2020, 1, 1),
                  "sector": "Tech", "exit_reason": "delisted", "source": "index_provider"}
        audit = audit_survivorship_coverage(
            [record], ["NEW"], minimum_non_survivors=1, minimum_historical_coverage=1.0,
        )
        self.assertTrue(audit["point_in_time_ready"])
        self.assertEqual(audit["non_survivor_tickers"], 1)

    def test_audit_does_not_claim_readiness_from_token_sample(self):
        record = {"ticker": "OLD", "start_date": date(2010, 1, 1), "end_date": date(2020, 1, 1),
                  "sector": "Tech", "exit_reason": "delisted", "source": "index_provider"}
        audit = audit_survivorship_coverage([record], ["NEW"])
        self.assertFalse(audit["point_in_time_ready"])
        self.assertEqual(audit["status"], "SURVIVORSHIP_BIAS_REMAINS")

    def test_loader_rejects_invalid_exit_reason(self):
        content = "ticker,start_date,end_date,sector,exit_reason,source\nOLD,2010-01-01,2020-01-01,Tech,unknown,test\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.csv"
            path.write_text(content, encoding="utf-8")
            with self.assertRaises(ValueError): load_universe_history(path)


if __name__ == "__main__": unittest.main()
