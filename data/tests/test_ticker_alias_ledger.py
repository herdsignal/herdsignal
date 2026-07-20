import unittest

from herd.corporate_continuity_reconciliation import CorporateContinuityError
from herd.ticker_alias_ledger import reconcile_ticker_aliases


class TickerAliasLedgerTest(unittest.TestCase):
    def setUp(self):
        self.reconciliation = [{
            "candidate_effective_date": "2017-08-29",
            "action": "ADD",
            "ticker": "IQV",
            "status": "UNMATCHED_REQUIRES_TICKER_ALIAS",
        }]
        self.claims = [{
            "candidate_effective_date": "2017-08-29",
            "action": "ADD",
            "ticker": "IQV",
            "entity_id": "IQVIA",
            "resolution_mode": "BACKFILLED_ADMISSION_THEN_RENAME",
            "announcement_date": "2017-08-24",
            "index_effective_date": "2017-08-29",
            "sp_source_url": "https://press.spglobal.com/q",
            "required_sp_terms": "Quintiles||ticker Q",
        }]
        self.aliases = [
            {
                "entity_id": "IQVIA",
                "cik": "1478242",
                "ticker": "Q",
                "valid_from": "2013-05-09",
                "valid_to": "2017-11-14",
                "predecessor_ticker": "",
                "announcement_date": "",
                "corporate_effective_date": "",
                "trading_start_date": "2013-05-09",
                "sec_source_url": "https://www.sec.gov/q",
                "required_sec_terms": "name change||IQV",
                "verification_status": "VERIFIED",
            },
            {
                "entity_id": "IQVIA",
                "cik": "1478242",
                "ticker": "IQV",
                "valid_from": "2017-11-15",
                "valid_to": "",
                "predecessor_ticker": "Q",
                "announcement_date": "2017-11-06",
                "corporate_effective_date": "2017-11-06",
                "trading_start_date": "2017-11-15",
                "sec_source_url": "https://www.sec.gov/q",
                "required_sec_terms": "name change||IQV",
                "verification_status": "VERIFIED",
            },
        ]
        self.sp = {
            "https://press.spglobal.com/q": (
                b"Quintiles will join with ticker Q", "a" * 64
            )
        }
        self.sec = {
            "https://www.sec.gov/q": (
                b"name change and shares trade as IQV", "b" * 64
            )
        }

    def test_builds_admission_then_rename_from_time_bounded_aliases(self):
        updated, events, audit = reconcile_ticker_aliases(
            self.reconciliation,
            self.claims,
            self.aliases,
            self.sp,
            self.sec,
        )
        self.assertEqual(
            "VERIFIED_CORPORATE_CONTINUITY_COMPONENT",
            updated[0]["status"],
        )
        self.assertEqual(
            [
                ("2017-08-29", "ADD", "Q"),
                ("2017-11-15", "RENAME", "IQV"),
            ],
            [
                (row["index_effective_date"], row["action"], row["ticker"])
                for row in events
            ],
        )
        self.assertEqual(2, audit["generated_events"])

    def test_rejects_overlapping_alias_intervals(self):
        aliases = [dict(row) for row in self.aliases]
        aliases[0]["valid_to"] = "2017-11-15"
        with self.assertRaises(CorporateContinuityError):
            reconcile_ticker_aliases(
                self.reconciliation,
                self.claims,
                aliases,
                self.sp,
                self.sec,
            )

    def test_rejects_cross_cik_alias_chain(self):
        aliases = [dict(row) for row in self.aliases]
        aliases[1]["cik"] = "999"
        with self.assertRaises(CorporateContinuityError):
            reconcile_ticker_aliases(
                self.reconciliation,
                self.claims,
                aliases,
                self.sp,
                self.sec,
            )


if __name__ == "__main__":
    unittest.main()
