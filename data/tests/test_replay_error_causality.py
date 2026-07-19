import unittest

from herd.replay_error_causality import trace_replay_errors


class ReplayErrorCausalityTest(unittest.TestCase):
    def test_links_remove_error_to_prior_blocked_add(self):
        audit = {"error_rows": [{
            "effective_date": "2022-01-03",
            "error": "REMOVE_ABSENT_TICKER",
            "ticker": "AAA",
        }]}
        ledger = [{
            "event_type": "MEMBERSHIP_CHANGE",
            "candidate_effective_date": "2020-01-02",
            "action": "ADD",
            "ticker": "AAA",
            "event_status": "UNRESOLVED",
            "candidate_reconciliation_status": "NO_OFFICIAL_DOCUMENT_MATCH",
        }]

        rows, result = trace_replay_errors(audit, ledger)

        self.assertTrue(rows[0]["prior_blocker_found"])
        self.assertEqual(
            "DOWNSTREAM_ERROR_FROM_UNRESOLVED_INTRODUCTION", rows[0]["diagnosis"]
        )
        self.assertFalse(rows[0]["auto_fix_allowed"])
        self.assertEqual(1, result["explained_by_prior_blocker"])

    def test_leaves_unexplained_error_for_baseline_review(self):
        rows, result = trace_replay_errors({"error_rows": [{
            "effective_date": "2022-01-03",
            "error": "REMOVE_ABSENT_TICKER",
            "ticker": "AAA",
        }]}, [])

        self.assertFalse(rows[0]["prior_blocker_found"])
        self.assertEqual(1, result["baseline_or_history_review_required"])


if __name__ == "__main__":
    unittest.main()
