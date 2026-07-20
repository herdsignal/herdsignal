import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.timing_hypothesis_registry import TimingHypothesisRegistryError
from herd.timing_oos_protocol import load_protocol, validate_protocol


class TimingOosProtocolTest(unittest.TestCase):
    def test_protocol_is_locked(self):
        _, audit = load_protocol()
        self.assertEqual(audit["test_count"], 6)

    def test_participation_cannot_set_action_direction(self):
        protocol, _ = load_protocol()
        changed = copy.deepcopy(protocol)
        for item in changed["tests"]:
            if item["family"] == "PARTICIPATION":
                item["action_test"] = "STANDALONE_BUY_SELL"
        with self.assertRaises(TimingHypothesisRegistryError):
            validate_protocol(changed)

    def test_low_exposure_rule_is_rejected(self):
        protocol, _ = load_protocol()
        changed = copy.deepcopy(protocol)
        changed["common_execution"]["minimum_exposure"] = 0.5
        with self.assertRaises(TimingHypothesisRegistryError):
            validate_protocol(changed)

