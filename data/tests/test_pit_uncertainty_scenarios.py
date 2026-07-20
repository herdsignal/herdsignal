import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.pit_uncertainty_scenarios import (
    PitUncertaintyScenarioError,
    _validate_assumptions,
)


class PitUncertaintyScenarioTest(unittest.TestCase):
    def test_assumptions_must_cover_blockers_exactly(self):
        blockers = [{
            "candidate_effective_date": "2020-01-02",
            "ticker": "NEW",
        }]
        assumptions = [{
            "candidate_effective_date": "2020-01-02",
            "ticker": "NEW",
            "old_ticker": "OLD",
            "assumed_index_effective_date": "2020-01-02",
            "baseline_policy": "USE_FROZEN_BASELINE",
            "review_status": "RESEARCH_SCENARIO_ONLY",
            "promotion_allowed": "false",
        }]
        rows = _validate_assumptions(blockers, assumptions)
        self.assertIn(("2020-01-02", "NEW"), rows)

    def test_rejects_promotable_assumption(self):
        blockers = [{
            "candidate_effective_date": "2020-01-02",
            "ticker": "NEW",
        }]
        assumptions = [{
            "candidate_effective_date": "2020-01-02",
            "ticker": "NEW",
            "old_ticker": "OLD",
            "assumed_index_effective_date": "2020-01-02",
            "baseline_policy": "USE_FROZEN_BASELINE",
            "review_status": "RESEARCH_SCENARIO_ONLY",
            "promotion_allowed": "true",
        }]
        with self.assertRaises(PitUncertaintyScenarioError):
            _validate_assumptions(blockers, assumptions)


if __name__ == "__main__":
    unittest.main()
