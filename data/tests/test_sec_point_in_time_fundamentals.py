import unittest
from datetime import datetime, timezone

from herd.sec_point_in_time_fundamentals import (
    SecFundamentalsError,
    build_acceptance_index,
    facts_as_of,
    normalize_companyfacts,
)


def companyfacts_payload():
    return {
        "cik": 1,
        "entityName": "Example",
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": {
                    "label": "Net Income",
                    "units": {
                        "USD": [
                            {
                                "start": "2023-01-01", "end": "2023-12-31",
                                "val": 100, "accn": "old", "form": "10-K",
                                "filed": "2024-02-01", "fy": 2023, "fp": "FY",
                            },
                            {
                                "start": "2023-01-01", "end": "2023-12-31",
                                "val": 90, "accn": "amended", "form": "10-K/A",
                                "filed": "2024-03-01", "fy": 2023, "fp": "FY",
                            },
                            {
                                "start": "2024-01-01", "end": "2024-03-31",
                                "val": 30, "accn": "missing", "form": "10-Q",
                                "filed": "2024-05-01", "fy": 2024, "fp": "Q1",
                            },
                        ]
                    },
                }
            }
        },
    }


class SecPointInTimeFundamentalsTest(unittest.TestCase):
    def test_preserves_restatement_versions_and_uses_acceptance_time(self):
        acceptance = build_acceptance_index([{
            "filings": {"recent": {
                "accessionNumber": ["old", "amended"],
                "acceptanceDateTime": [
                    "2024-02-01T21:00:00Z", "2024-03-01T21:00:00Z"
                ],
            }}
        }])
        rows, audit = normalize_companyfacts(companyfacts_payload(), acceptance)
        self.assertEqual(2, len(rows))
        self.assertEqual(1, audit["missing_acceptances"])
        self.assertFalse(audit["point_in_time_ready"])
        before_amendment = facts_as_of(
            rows, datetime(2024, 2, 15, tzinfo=timezone.utc),
            concept="NetIncomeLoss",
        )
        self.assertEqual(["old"], [row["accession_number"] for row in before_amendment])
        after_amendment = facts_as_of(
            rows, datetime(2024, 3, 2, tzinfo=timezone.utc),
            concept="NetIncomeLoss",
        )
        self.assertEqual(["old", "amended"], [row["accession_number"] for row in after_amendment])

    def test_non_strict_mode_marks_missing_acceptance_as_unavailable(self):
        rows, audit = normalize_companyfacts(
            companyfacts_payload(), {}, strict_acceptance=False
        )
        self.assertFalse(audit["point_in_time_ready"])
        self.assertTrue(all(row["availability"] == "MISSING_ACCEPTANCE_TIME" for row in rows))
        self.assertEqual([], facts_as_of(rows, datetime.now(timezone.utc)))

    def test_rejects_naive_as_of_timestamp(self):
        with self.assertRaises(SecFundamentalsError):
            facts_as_of([], datetime(2024, 1, 1))


if __name__ == "__main__":
    unittest.main()
