import unittest

from herd.constituent_event_contract import (
    ConstituentEventContractError,
    build_official_event,
    classify_effective_timing,
    membership_session_date,
    xnys_membership_session_date,
)


class ConstituentEventContractTest(unittest.TestCase):
    def test_prior_open_weekend_date_maps_to_next_trading_session(self):
        self.assertEqual(
            "2024-03-18",
            membership_session_date(
                "2024-03-16",
                "PRIOR_TO_OPEN",
                ["2024-03-15", "2024-03-18", "2024-03-19"],
            ),
        )

    def test_after_close_maps_to_following_trading_session(self):
        self.assertEqual(
            "2024-03-19",
            membership_session_date(
                "2024-03-18",
                "AFTER_CLOSE",
                ["2024-03-18", "2024-03-19"],
            ),
        )

    def test_classifies_prior_to_market_open_variant(self):
        self.assertEqual(
            "PRIOR_TO_OPEN",
            classify_effective_timing(
                "effective prior to the market open on Tuesday, November 13"
            ),
        )

    def test_xnys_after_close_skips_labor_day(self):
        self.assertEqual(
            "2016-09-06",
            xnys_membership_session_date("2016-09-02", "AFTER_CLOSE"),
        )

    def test_unspecified_timing_fails_closed(self):
        self.assertIsNone(
            membership_session_date(
                "2024-03-18", "UNSPECIFIED", ["2024-03-18"]
            )
        )

    def test_rejects_context_with_conflicting_timing(self):
        with self.assertRaises(ConstituentEventContractError):
            classify_effective_timing(
                "prior to the open on Monday and after the close on Monday"
            )

    def test_builds_only_official_hash_pinned_event(self):
        event = build_official_event(
            announcement_date="2024-03-10",
            stated_effective_date="2024-03-18",
            timing_context="effective prior to the open on March 18, 2024",
            action="add",
            ticker="aaa",
            source_url="https://press.spglobal.com/example",
            source_sha256="a" * 64,
            evidence_type="OFFICIAL_PROSE",
            trading_sessions=["2024-03-18"],
        )
        self.assertEqual("PRIOR_TO_OPEN", event["effective_timing"])
        self.assertEqual("2024-03-18", event["membership_session_date"])
        self.assertEqual("AAA", event["ticker"])

    def test_rejects_non_spglobal_source(self):
        with self.assertRaises(ConstituentEventContractError):
            build_official_event(
                announcement_date="2024-03-10",
                stated_effective_date="2024-03-18",
                timing_context="prior to the open",
                action="ADD",
                ticker="AAA",
                source_url="https://example.com/reconstruction",
                source_sha256="a" * 64,
                evidence_type="OFFICIAL_PROSE",
                trading_sessions=["2024-03-18"],
            )


if __name__ == "__main__":
    unittest.main()
