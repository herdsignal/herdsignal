import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.timing_hypothesis_registry import (
    TimingHypothesisRegistryError,
    load_registry,
    validate_registry,
)


class TimingHypothesisRegistryTest(unittest.TestCase):
    def setUp(self):
        self.registry, self.audit = load_registry()

    def test_registry_locks_all_hypotheses_and_families(self):
        self.assertEqual(self.audit["hypothesis_count"], 7)
        self.assertEqual(self.audit["family_count"], 6)
        self.assertEqual(self.audit["state_count"], 5)
        self.assertEqual(len(self.audit["sha256"]), 64)

    def test_rush_cannot_be_automatic_sell(self):
        changed = copy.deepcopy(self.registry)
        changed["action_contract"]["rush_alone_can_sell"] = True

        with self.assertRaises(TimingHypothesisRegistryError):
            validate_registry(changed)

    def test_flee_cannot_bypass_business_guard(self):
        changed = copy.deepcopy(self.registry)
        changed["action_contract"][
            "business_guard_can_block_add_buy"
        ] = False

        with self.assertRaises(TimingHypothesisRegistryError):
            validate_registry(changed)

    def test_state_bands_must_be_contiguous(self):
        changed = copy.deepcopy(self.registry)
        changed["state_bands"][1]["minimum"] = 17

        with self.assertRaises(TimingHypothesisRegistryError):
            validate_registry(changed)


if __name__ == "__main__":
    unittest.main()
