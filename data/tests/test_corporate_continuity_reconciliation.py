import unittest

from herd.corporate_continuity_reconciliation import (
    CorporateContinuityError,
    verify_and_reconcile,
)


class CorporateContinuityReconciliationTest(unittest.TestCase):
    def setUp(self):
        self.reconciliation = [
            {
                "candidate_effective_date": "2019-11-05",
                "action": "REMOVE",
                "ticker": "OLD",
                "status": "NO_OFFICIAL_DOCUMENT_MATCH",
            },
            {
                "candidate_effective_date": "2019-11-05",
                "action": "ADD",
                "ticker": "NEW",
                "status": "NO_OFFICIAL_DOCUMENT_MATCH",
            },
            {
                "candidate_effective_date": "2017-04-04",
                "action": "ADD",
                "ticker": "NEXT",
                "status": "NO_OFFICIAL_DOCUMENT_MATCH",
            },
        ]
        self.sec_url = "https://www.sec.gov/Archives/example"
        self.sp_url = "https://press.spglobal.com/example"
        self.sec = {
            self.sec_url: (
                b"Old Company changed its name. ticker symbol NEW November 5 2019",
                "a" * 64,
            )
        }
        self.sp = {
            self.sp_url: (
                b"Prior Corp. will replace Other in the S&P 500 Post-merger",
                "b" * 64,
            )
        }

    def test_reconciles_same_cik_rename_and_consumes_optional_remove(self):
        claims = [{
            "candidate_effective_date": "2019-11-05",
            "action": "ADD",
            "ticker": "NEW",
            "continuity_type": "SAME_CIK_RENAME",
            "old_ticker": "OLD",
            "effective_date": "2019-11-05",
            "cik": "123",
            "sp_source_url": "",
            "filing_url": self.sec_url,
            "required_sp_terms": "",
            "required_sec_terms": "changed its name||ticker symbol NEW",
        }]

        rows, events, audit = verify_and_reconcile(
            self.reconciliation, claims, self.sp, self.sec
        )

        self.assertEqual(1, len(events))
        self.assertEqual("SAME_CIK_RENAME", events[0]["event_type"])
        self.assertEqual(2, audit["reclassified_candidate_rows"])
        self.assertEqual(
            {"VERIFIED_CORPORATE_CONTINUITY_COMPONENT"},
            {row["status"] for row in rows if row["ticker"] in {"OLD", "NEW"}},
        )
        self.assertFalse(audit["survivorship_safe"])

    def test_requires_both_official_sources_for_successor_membership(self):
        claims = [{
            "candidate_effective_date": "2017-04-04",
            "action": "ADD",
            "ticker": "NEXT",
            "continuity_type": "SUCCESSOR_MEMBERSHIP",
            "old_ticker": "PRIOR",
            "effective_date": "2017-04-04",
            "cik": "456",
            "sp_source_url": self.sp_url,
            "filing_url": self.sec_url,
            "required_sp_terms": "will replace Other||in the S&P 500||Post-merger",
            "required_sec_terms": "ticker symbol NEW",
        }]

        rows, events, audit = verify_and_reconcile(
            self.reconciliation, claims, self.sp, self.sec
        )

        self.assertEqual("SUCCESSOR_MEMBERSHIP", events[0]["event_type"])
        self.assertEqual("ADD", events[0]["action"])
        self.assertEqual(1, audit["reclassified_candidate_rows"])
        target = next(row for row in rows if row["ticker"] == "NEXT")
        self.assertEqual(
            "VERIFIED_CORPORATE_CONTINUITY_COMPONENT", target["status"]
        )

    def test_same_cik_membership_continuity_requires_sp_and_sec(self):
        claims = [{
            "candidate_effective_date": "2019-11-05",
            "action": "ADD",
            "ticker": "NEW",
            "continuity_type": "SAME_CIK_MEMBERSHIP_CONTINUITY",
            "old_ticker": "OLD",
            "effective_date": "2019-11-05",
            "cik": "123",
            "sp_source_url": self.sp_url,
            "filing_url": self.sec_url,
            "required_sp_terms": "Prior Corp.||in the S&P 500||Post-merger",
            "required_sec_terms": "changed its name||ticker symbol NEW",
        }]
        _, events, audit = verify_and_reconcile(
            self.reconciliation, claims, self.sp, self.sec
        )
        self.assertEqual("RENAME", events[0]["action"])
        self.assertEqual(2, audit["reclassified_candidate_rows"])

    def test_consumes_multiple_share_classes(self):
        reconciliation = [
            {
                "candidate_effective_date": "2022-04-11",
                "action": action,
                "ticker": ticker,
                "status": "NO_OFFICIAL_DOCUMENT_MATCH",
            }
            for action, ticker in (
                ("REMOVE", "DISCA"),
                ("REMOVE", "DISCK"),
                ("ADD", "WBD"),
            )
        ]
        claims = [{
            "candidate_effective_date": "2022-04-11",
            "action": "ADD",
            "ticker": "WBD",
            "continuity_type": "SAME_CIK_MEMBERSHIP_CONTINUITY",
            "old_ticker": "DISCA",
            "old_tickers": "DISCA|DISCK",
            "effective_date": "2022-04-11",
            "cik": "1437107",
            "sp_source_url": self.sp_url,
            "filing_url": self.sec_url,
            "required_sp_terms": "in the S&P 500||Post-merger",
            "required_sec_terms": "ticker symbol NEW",
        }]
        _, events, audit = verify_and_reconcile(
            reconciliation, claims, self.sp, self.sec
        )
        self.assertEqual("DISCA|DISCK", events[0]["old_ticker"])
        self.assertEqual(3, audit["reclassified_candidate_rows"])

    def test_fails_closed_when_required_term_is_absent(self):
        claims = [{
            "candidate_effective_date": "2019-11-05",
            "action": "ADD",
            "ticker": "NEW",
            "continuity_type": "SAME_CIK_RENAME",
            "old_ticker": "OLD",
            "effective_date": "2019-11-05",
            "cik": "123",
            "sp_source_url": "",
            "filing_url": self.sec_url,
            "required_sp_terms": "",
            "required_sec_terms": "not present",
        }]

        with self.assertRaises(CorporateContinuityError):
            verify_and_reconcile(
                self.reconciliation, claims, self.sp, self.sec
            )


if __name__ == "__main__":
    unittest.main()
