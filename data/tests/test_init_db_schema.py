import unittest

from init_db import InvestorProfile, SchedulerRun


class InitDbSchemaTest(unittest.TestCase):
    def test_investor_profile_schema_loads(self) -> None:
        self.assertEqual(InvestorProfile.__tablename__, "investor_profiles")
        self.assertIn("time_horizon_years", InvestorProfile.__table__.columns)

    def test_scheduler_run_schema_tracks_execution_result(self) -> None:
        self.assertEqual(SchedulerRun.__tablename__, "scheduler_runs")
        self.assertIn("status", SchedulerRun.__table__.columns)
        self.assertIn("failed_tickers", SchedulerRun.__table__.columns)
