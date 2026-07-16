import unittest

from herd.validation_policy import ValidationPolicy


class ValidationPolicyTest(unittest.TestCase):
    def test_fixed_policy_does_not_apply_train_selection(self):
        policy = ValidationPolicy()
        self.assertEqual(policy.applied_parameters(1.2, 30), (1.0, 20))
        self.assertFalse(policy.metadata()["automatic_selection_applied"])

    def test_train_selected_policy_is_explicit_research_mode(self):
        policy = ValidationPolicy(mode="train-selected")
        self.assertEqual(policy.applied_parameters(1.2, 30), (1.2, 30))
        self.assertTrue(policy.metadata()["automatic_selection_applied"])


if __name__ == "__main__":
    unittest.main()
