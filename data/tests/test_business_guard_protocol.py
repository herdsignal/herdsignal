import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.business_guard_protocol import (
    BusinessGuardProtocolError,
    load_protocol,
    validate_protocol,
)


class BusinessGuardProtocolTest(unittest.TestCase):
    def test_repository_protocol_is_valid(self):
        _, audit = load_protocol()
        self.assertEqual(audit["status"], "LOCKED_BEFORE_OOS_RESULTS")
        self.assertEqual(audit["feature_count"], 4)

    def test_acceptance_time_cannot_be_replaced_by_period_end(self):
        protocol, _ = load_protocol()
        changed = copy.deepcopy(protocol)
        changed["data_contract"]["availability_time"] = "PERIOD_END"
        with self.assertRaises(BusinessGuardProtocolError):
            validate_protocol(changed)

    def test_unknown_cannot_be_labeled_deteriorated_for_research(self):
        protocol, _ = load_protocol()
        changed = copy.deepcopy(protocol)
        changed["guard_rule"]["research_unknown_policy"] = "TREAT_AS_VETO"
        with self.assertRaises(BusinessGuardProtocolError):
            validate_protocol(changed)

    def test_guard_cannot_create_a_sell_signal(self):
        protocol, _ = load_protocol()
        changed = copy.deepcopy(protocol)
        changed["forbidden"].remove("BUSINESS_GUARD_CREATES_SELL_SIGNAL")
        with self.assertRaises(BusinessGuardProtocolError):
            validate_protocol(changed)


if __name__ == "__main__":
    unittest.main()
