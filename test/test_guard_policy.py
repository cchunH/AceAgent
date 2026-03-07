import unittest

from guiagent_v2.runtime.guard_policy import GuardPolicy


class TestGuardPolicy(unittest.TestCase):
    def test_allow_by_default(self):
        policy = GuardPolicy()
        result = policy.decide(
            "global:TAP:BTN",
            {"name": "Tap", "arguments": {"x": 1, "y": 2}},
            {"channel": "mobile_native"},
        )
        self.assertEqual(result["decision"], "allow")

    def test_deny_mobile_action_for_web_skill(self):
        policy = GuardPolicy()
        result = policy.decide(
            "global:TAP:BTN",
            {"name": "Tap", "arguments": {"x": 1, "y": 2}},
            {"channel": "web_skill"},
        )
        self.assertEqual(result["decision"], "deny")
        self.assertEqual(result["category"], "route_guard")

    def test_confirm_high_risk_intent(self):
        policy = GuardPolicy()
        result = policy.decide(
            "global:PAY:ORDER",
            {"name": "CustomAction", "arguments": {}},
            {"channel": "mobile_native"},
        )
        self.assertEqual(result["decision"], "confirm")
        self.assertEqual(result["category"], "risk_control")


if __name__ == "__main__":
    unittest.main()
