import json
import tempfile
import unittest

from guiagent_v2.runtime.policy_loader import PolicyLoader


class TestPolicyLoader(unittest.TestCase):
    def test_default_policy_without_path(self):
        loader = PolicyLoader(policy_path=None)
        policy = loader.load()
        self.assertIn("high_risk_tokens", policy)
        self.assertEqual(policy["version"], "v1")

    def test_load_and_force_reload(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".json", encoding="utf-8") as f:
            json.dump({"version": "a1", "deny_intent_prefixes": ["global:BLOCK:"]}, f, ensure_ascii=False)
            f.flush()

            loader = PolicyLoader(policy_path=f.name, reload_interval_sec=60.0)
            p1 = loader.load()
            self.assertEqual(p1["version"], "a1")
            self.assertEqual(p1["deny_intent_prefixes"], ["global:BLOCK:"])

            f.seek(0)
            f.truncate()
            json.dump({"version": "a2", "confirm_intent_prefixes": ["global:CONFIRM:"]}, f, ensure_ascii=False)
            f.flush()

            p2 = loader.load(force=True)
            self.assertEqual(p2["version"], "a2")
            self.assertEqual(p2["confirm_intent_prefixes"], ["global:CONFIRM:"])


if __name__ == "__main__":
    unittest.main()
