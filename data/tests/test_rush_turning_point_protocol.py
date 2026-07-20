import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.rush_turning_point_protocol import (
    RushTurningPointProtocolError,
    load_protocol,
    validate_protocol,
)


class RushTurningPointProtocolTest(unittest.TestCase):
    def test_repository_protocol_is_valid_and_locked(self):
        _, audit = load_protocol()
        self.assertEqual(audit["status"], "LOCKED_BEFORE_OOS_RESULTS")
        self.assertEqual(audit["state_count"], 4)

    def test_high_herd_alone_cannot_become_sell_signal(self):
        protocol, _ = load_protocol()
        changed = copy.deepcopy(protocol)
        changed["forbidden"].remove("HIGH_HERD_ALONE_AS_SELL_SIGNAL")
        with self.assertRaises(RushTurningPointProtocolError):
            validate_protocol(changed)

    def test_exhaustion_cannot_drop_participation_confirmation(self):
        protocol, _ = load_protocol()
        changed = copy.deepcopy(protocol)
        changed["state_rules"]["EXHAUSTED_RUSH"].remove(
            "PARTICIPATION_3M_CHANGE_LT_ZERO"
        )
        with self.assertRaises(RushTurningPointProtocolError):
            validate_protocol(changed)

    def test_reentry_cannot_precede_profit_take_validation(self):
        protocol, _ = load_protocol()
        changed = copy.deepcopy(protocol)
        changed["forbidden"].remove(
            "REENTRY_RULE_BEFORE_PROFIT_TAKE_GATE_PASS"
        )
        with self.assertRaises(RushTurningPointProtocolError):
            validate_protocol(changed)
