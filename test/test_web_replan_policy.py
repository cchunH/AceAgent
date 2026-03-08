import unittest

from guiagent_v2.runtime.web_replan_policy import WebReplanPolicy, normalize_reason_key


class TestWebReplanPolicy(unittest.TestCase):
    def test_reason_normalization(self):
        self.assertEqual(normalize_reason_key("CLI_NOT_FOUND"), "backend_unavailable")
        self.assertEqual(normalize_reason_key("selector_not_found"), "selector_missing")
        self.assertEqual(normalize_reason_key("CLI_TIMEOUT"), "timeout")
        self.assertEqual(normalize_reason_key("unauthorized"), "auth_blocked")

    def test_backend_unavailable_disables_replan(self):
        policy = WebReplanPolicy(base_max_attempts=3)
        decision = policy.decide("CLI_NOT_FOUND", attempted=0)
        self.assertFalse(decision.allow)
        self.assertEqual(decision.allowed_attempts, 0)
        self.assertEqual(decision.reason_key, "backend_unavailable")

    def test_failure_bias_reduces_attempt_budget(self):
        policy = WebReplanPolicy(base_max_attempts=3)
        policy.record_failure("CLI_TIMEOUT")
        policy.record_failure("CLI_TIMEOUT")
        decision = policy.decide("CLI_TIMEOUT", attempted=1)
        self.assertLessEqual(decision.allowed_attempts, 1)
        self.assertFalse(decision.allow)

    def test_recovery_bias_can_increase_budget(self):
        policy = WebReplanPolicy(base_max_attempts=2)
        policy.record_recovery("selector_not_found")
        policy.record_recovery("selector_not_found")
        decision = policy.decide("selector_not_found", attempted=1)
        self.assertTrue(decision.allow)
        self.assertGreaterEqual(decision.allowed_attempts, 2)


if __name__ == "__main__":
    unittest.main()

