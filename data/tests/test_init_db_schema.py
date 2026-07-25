import unittest

from init_db import HerdObservation, InvestorProfile, SchedulerRun


class InitDbSchemaTest(unittest.TestCase):
    def test_investor_profile_schema_loads(self) -> None:
        self.assertEqual(InvestorProfile.__tablename__, "investor_profiles")
        self.assertIn("time_horizon_years", InvestorProfile.__table__.columns)

    def test_scheduler_run_schema_tracks_execution_result(self) -> None:
        self.assertEqual(SchedulerRun.__tablename__, "scheduler_runs")
        self.assertIn("status", SchedulerRun.__table__.columns)
        self.assertIn("failed_tickers", SchedulerRun.__table__.columns)
        self.assertIn("skipped_tickers", SchedulerRun.__table__.columns)

    def test_observation_schema_is_versioned_and_state_only(self) -> None:
        self.assertEqual(HerdObservation.__tablename__, "herd_observations")
        columns = HerdObservation.__table__.columns
        self.assertIn("state_model_version", columns)
        self.assertIn("source_scope", columns)
        self.assertIn("operational_action_ratio", columns)
