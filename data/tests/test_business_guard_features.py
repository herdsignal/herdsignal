import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.business_guard_features import classify_as_of
from herd.business_guard_protocol import load_protocol


def fact(group, end, value, accepted, *, days=90):
    end_date = datetime.fromisoformat(end).date()
    return {
        "group": group,
        "concept": group,
        "concept_priority": 0,
        "period_start": end_date.fromordinal(end_date.toordinal() - days),
        "period_end": end_date,
        "duration_days": days,
        "accepted_at": datetime.fromisoformat(accepted).replace(
            tzinfo=timezone.utc
        ),
        "accession_number": accepted,
        "value": value,
    }


class BusinessGuardFeaturesTest(unittest.TestCase):
    def setUp(self):
        self.protocol, _ = load_protocol()

    def complete_facts(self):
        rows = []
        for end, accepted, revenue, earnings in (
            ("2023-03-31", "2023-05-01T12:00:00", 100, 10),
            ("2024-03-31", "2024-05-01T12:00:00", 85, -5),
        ):
            rows.extend([
                fact("revenue", end, revenue, accepted),
                fact("earnings", end, earnings, accepted),
            ])
        for end, accepted, cash in (
            ("2022-12-31", "2023-02-01T12:00:00", 20),
            ("2023-12-31", "2024-02-01T12:00:00", -1),
        ):
            rows.append(fact(
                "operating_cash_flow", end, cash, accepted, days=365
            ))
        for end, accepted, assets, liabilities in (
            ("2023-03-31", "2023-05-01T12:00:00", 100, 50),
            ("2024-03-31", "2024-05-01T12:00:00", 100, 70),
        ):
            rows.extend([
                fact("assets", end, assets, accepted, days=0),
                fact("liabilities", end, liabilities, accepted, days=0),
            ])
        return rows

    def test_multiple_deteriorations_create_veto(self):
        result = classify_as_of(
            self.complete_facts(),
            datetime(2024, 6, 1, tzinfo=timezone.utc),
            self.protocol,
        )
        self.assertEqual(result["guard_state"], "VETO")
        self.assertGreaterEqual(result["flag_count"], 2)
        self.assertEqual(result["operating_cash_flow_value"], -1)

    def test_future_filing_is_not_visible(self):
        result = classify_as_of(
            self.complete_facts(),
            datetime(2024, 4, 1, tzinfo=timezone.utc),
            self.protocol,
        )
        self.assertEqual(result["guard_state"], "UNKNOWN")

    def test_missing_comparable_facts_are_unknown(self):
        result = classify_as_of(
            self.complete_facts()[:2],
            datetime(2024, 6, 1, tzinfo=timezone.utc),
            self.protocol,
        )
        self.assertEqual(result["guard_state"], "UNKNOWN")

    def test_liabilities_can_be_derived_from_assets_and_equity(self):
        rows = self.complete_facts()
        rows = [row for row in rows if row["group"] != "liabilities"]
        for end, accepted, equity in (
            ("2023-03-31", "2023-05-01T12:00:00", 50),
            ("2024-03-31", "2024-05-01T12:00:00", 30),
        ):
            rows.append(fact("equity", end, equity, accepted, days=0))
        result = classify_as_of(
            rows,
            datetime(2024, 6, 1, tzinfo=timezone.utc),
            self.protocol,
        )
        self.assertEqual(result["guard_state"], "VETO")
        self.assertAlmostEqual(result["liabilities_to_assets"], 0.7)


if __name__ == "__main__":
    unittest.main()
