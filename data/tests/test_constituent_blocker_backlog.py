import unittest

from herd.constituent_blocker_backlog import (
    BlockerBacklogError,
    build_blocker_backlog,
)


class ConstituentBlockerBacklogTest(unittest.TestCase):
    def test_routes_semantics_pair_and_isolated_event_without_promotion(self):
        ledger = [
            {
                "candidate_effective_date": "2020-01-02",
                "action": "REMOVE",
                "ticker": "OLD",
                "event_status": "REQUIRES_REVIEW",
            },
            {
                "candidate_effective_date": "2020-01-03",
                "action": "ADD",
                "ticker": "NEW",
                "event_status": "UNRESOLVED",
            },
            {
                "candidate_effective_date": "2020-02-01",
                "action": "ADD",
                "ticker": "SOLO",
                "event_status": "UNRESOLVED",
            },
        ]
        residual = [
            {
                "candidate_effective_date": "2020-01-02",
                "action": "REMOVE",
                "ticker": "OLD",
                "residual_category":
                    "ACTUAL_MEMBERSHIP_CHANGE_REQUIRES_OFFICIAL_SEMANTICS",
            },
            {
                "candidate_effective_date": "2020-01-03",
                "action": "ADD",
                "ticker": "NEW",
                "residual_category": "OFFICIAL_DOCUMENT_MISSING",
            },
            {
                "candidate_effective_date": "2020-02-01",
                "action": "ADD",
                "ticker": "SOLO",
                "residual_category": "OFFICIAL_DOCUMENT_MISSING",
            },
        ]
        rows, audit = build_blocker_backlog(
            ledger,
            residual,
            identity_evidence=[{
                "old_candidate_date": "2020-01-02",
                "new_candidate_date": "2020-01-03",
                "old_ticker": "OLD",
                "new_ticker": "NEW",
                "identity_status": "SEC_IDENTITY_AND_EFFECTIVE_DATE_VERIFIED",
            }],
        )
        by_ticker = {row["ticker"]: row for row in rows}
        self.assertEqual(
            "OFFICIAL_MEMBERSHIP_SEMANTICS_REVIEW",
            by_ticker["OLD"]["workstream"],
        )
        self.assertEqual(
            "CORPORATE_ACTION_CONTINUITY_REVIEW",
            by_ticker["NEW"]["workstream"],
        )
        self.assertEqual(
            "OFFICIAL_DOCUMENT_DISCOVERY",
            by_ticker["SOLO"]["workstream"],
        )
        self.assertTrue(all(row["promotion_allowed"] == "false" for row in rows))
        self.assertEqual(3, audit["classified_blockers"])

    def test_does_not_treat_date_proximity_as_company_continuity(self):
        ledger = [
            {
                "candidate_effective_date": "2020-01-02",
                "action": "REMOVE",
                "ticker": "UNRELATED",
                "event_status": "UNRESOLVED",
            },
            {
                "candidate_effective_date": "2020-01-03",
                "action": "ADD",
                "ticker": "OTHER",
                "event_status": "UNRESOLVED",
            },
        ]
        residual = [{
            "candidate_effective_date": row["candidate_effective_date"],
            "action": row["action"],
            "ticker": row["ticker"],
            "residual_category": "OFFICIAL_DOCUMENT_MISSING",
        } for row in ledger]
        rows, _ = build_blocker_backlog(ledger, residual)
        self.assertEqual(
            {"PROXIMITY_PAIR_TRIAGE"},
            {row["workstream"] for row in rows},
        )

    def test_fails_when_blocker_has_no_residual_classification(self):
        with self.assertRaises(BlockerBacklogError):
            build_blocker_backlog(
                [{
                    "candidate_effective_date": "2020-01-02",
                    "action": "ADD",
                    "ticker": "MISS",
                    "event_status": "UNRESOLVED",
                }],
                [],
            )


if __name__ == "__main__":
    unittest.main()
