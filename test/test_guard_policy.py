import json
import tempfile
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

    def test_policy_file_confirm_prefix(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".json", encoding="utf-8") as f:
            json.dump(
                {
                    "version": "v-test",
                    "high_risk_tokens": [],
                    "confirm_intent_prefixes": ["global:WAIT:"],
                },
                f,
                ensure_ascii=False,
            )
            f.flush()
            policy = GuardPolicy.from_policy_file(f.name, reload_interval_sec=0.0)
            result = policy.decide(
                "global:WAIT:TASK",
                {"name": "Wait", "arguments": {}},
                {"channel": "mobile_native"},
            )
            self.assertEqual(result["decision"], "confirm")
            self.assertEqual(result["reason"], "INTENT_PREFIX_CONFIRM")
            self.assertEqual(result["policy_version"], "v-test")

    def test_policy_file_reload_to_deny_prefix(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".json", encoding="utf-8") as f:
            json.dump({"version": "v1", "deny_intent_prefixes": []}, f, ensure_ascii=False)
            f.flush()
            policy = GuardPolicy.from_policy_file(f.name, reload_interval_sec=0.0)
            allow = policy.decide(
                "global:CUSTOM:ACTION",
                {"name": "Custom", "arguments": {}},
                {"channel": "mobile_native"},
            )
            self.assertEqual(allow["decision"], "allow")

            f.seek(0)
            f.truncate()
            json.dump({"version": "v2", "deny_intent_prefixes": ["global:CUSTOM:"]}, f, ensure_ascii=False)
            f.flush()
            policy.reload_policy()

            deny = policy.decide(
                "global:CUSTOM:ACTION",
                {"name": "Custom", "arguments": {}},
                {"channel": "mobile_native"},
            )
            self.assertEqual(deny["decision"], "deny")
            self.assertEqual(deny["reason"], "INTENT_PREFIX_DENIED")
            self.assertEqual(deny["policy_version"], "v2")

    def test_policy_file_web_domain_allowlist_blocks_unknown_domain(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".json", encoding="utf-8") as f:
            json.dump(
                {
                    "version": "v-domain",
                    "web_domain_allowlist": ["example.com", "*.trusted.site"],
                },
                f,
                ensure_ascii=False,
            )
            f.flush()
            policy = GuardPolicy.from_policy_file(f.name, reload_interval_sec=0.0)
            denied = policy.decide(
                "web:OPEN:URL",
                {"name": "web_open", "arguments": {"url": "https://evil.site/page"}},
                {"channel": "web_skill", "web_task": {"url": "https://evil.site/page"}},
            )
            self.assertEqual(denied["decision"], "deny")
            self.assertEqual(denied["reason"], "WEB_DOMAIN_NOT_ALLOWED")

            allowed = policy.decide(
                "web:OPEN:URL",
                {"name": "web_open", "arguments": {"url": "https://sub.trusted.site/path"}},
                {"channel": "web_skill", "web_task": {"url": "https://sub.trusted.site/path"}},
            )
            self.assertEqual(allowed["decision"], "allow")

    def test_policy_file_web_domain_denylist_blocks_matched_domain(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".json", encoding="utf-8") as f:
            json.dump(
                {
                    "version": "v-domain-deny",
                    "web_domain_denylist": ["*.blocked.site"],
                },
                f,
                ensure_ascii=False,
            )
            f.flush()
            policy = GuardPolicy.from_policy_file(f.name, reload_interval_sec=0.0)
            denied = policy.decide(
                "web:OPEN:URL",
                {"name": "web_open", "arguments": {"url": "https://foo.blocked.site/home"}},
                {"channel": "web_skill", "web_task": {"url": "https://foo.blocked.site/home"}},
            )
            self.assertEqual(denied["decision"], "deny")
            self.assertEqual(denied["reason"], "WEB_DOMAIN_DENIED")


if __name__ == "__main__":
    unittest.main()
