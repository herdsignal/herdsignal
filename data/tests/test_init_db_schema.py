import unittest

from init_db import InvestorProfile


class InitDbSchemaTest(unittest.TestCase):
    def test_investor_profile_schema_loads(self) -> None:
        self.assertEqual(InvestorProfile.__tablename__, "investor_profiles")
        self.assertIn("time_horizon_years", InvestorProfile.__table__.columns)
