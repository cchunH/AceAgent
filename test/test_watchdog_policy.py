import json
import os
import tempfile
import unittest

from guiagent_v2.runtime.watchdog_policy import (
    WatchdogPolicyLoader,
    normalize_watchdog_policy,
)


class TestWatchdogPolicy(unittest.TestCase):
    def test_normalize_policy(self):
        policy = normalize_watchdog_policy(
            {
                "version": "v2",
                "enabled_watchdogs": [" security_watchdog ", "", "crash_watchdog"],
                "min_severity": "high",
                "dedup_window_sec": "10",
                "max_alerts_per_key": "2",
                "throttle_window_sec": "15",
                "dedup_key_fields": ["watchdog_name", "reason_code"],
            }
        )
        self.assertEqual(policy["version"], "v2")
        self.assertEqual(policy["enabled_watchdogs"], ["security_watchdog", "crash_watchdog"])
        self.assertEqual(policy["min_severity"], "HIGH")
        self.assertEqual(policy["dedup_window_sec"], 10.0)
        self.assertEqual(policy["max_alerts_per_key"], 2)
        self.assertEqual(policy["throttle_window_sec"], 15.0)
        self.assertEqual(policy["dedup_key_fields"], ["watchdog_name", "reason_code"])

    def test_loader_from_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "watchdog-policy.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "version": "v3",
                        "enabled_watchdogs": ["security_watchdog"],
                        "min_severity": "MEDIUM",
                        "dedup_window_sec": 5,
                        "max_alerts_per_key": 1,
                        "throttle_window_sec": 30,
                        "dedup_key_fields": ["watchdog_name", "task_id", "reason_code"],
                    },
                    f,
                )
            loader = WatchdogPolicyLoader(policy_path=path, reload_interval_sec=0.0)
            policy = loader.load(force=True)
            self.assertEqual(policy["version"], "v3")
            self.assertEqual(policy["enabled_watchdogs"], ["security_watchdog"])
            self.assertEqual(policy["max_alerts_per_key"], 1)
            self.assertEqual(loader.source(), path)


if __name__ == "__main__":
    unittest.main()
