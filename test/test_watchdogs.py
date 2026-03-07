import unittest

from guiagent_v2.runtime.watchdogs import WatchdogManager, build_default_watchdog_manager
from guiagent_v2.runtime.watchdogs.security_watchdog import SecurityWatchdog


class _BadWatchdog:
    name = "bad_watchdog"

    def on_event(self, event):
        raise RuntimeError("boom")


class _PolicyLoader:
    def __init__(self, policy):
        self._policy = dict(policy)

    def load(self, force=False):
        del force
        return dict(self._policy)

    def source(self):
        return "test-policy"


class TestWatchdogs(unittest.TestCase):
    def test_security_watchdog_alert_on_guard_deny(self):
        manager = build_default_watchdog_manager()
        alerts = manager.process(
            {
                "run_id": "r1",
                "task_id": "t1",
                "step_id": 1,
                "chain_mode": "guiagent_v2",
                "event_type": "guard_decision",
                "status": "HANDOVER",
                "intent_key": "global:TAP:SUBMIT",
                "policy_decision": "deny",
                "policy_reason": "ACTION_DENIED_BY_POLICY",
            }
        )
        self.assertTrue(any(item["watchdog_name"] == "security_watchdog" for item in alerts))
        self.assertTrue(all(item["event_type"] == "watchdog_alert" for item in alerts))

    def test_crash_watchdog_alert_on_task_failed(self):
        manager = build_default_watchdog_manager()
        alerts = manager.process(
            {
                "run_id": "r2",
                "task_id": "t2",
                "step_id": 999999,
                "chain_mode": "legacy",
                "event_type": "task_end",
                "status": "FAILED",
                "intent_key": "global:TASK:END",
                "reason_code": "UNKNOWN_ERROR",
            }
        )
        self.assertTrue(any(item["watchdog_name"] == "crash_watchdog" for item in alerts))

    def test_watchdog_alert_event_not_reentered(self):
        manager = build_default_watchdog_manager()
        alerts = manager.process(
            {
                "run_id": "r3",
                "task_id": "t3",
                "step_id": 1,
                "chain_mode": "guiagent_v2",
                "event_type": "watchdog_alert",
                "status": "FAILED",
                "intent_key": "global:TAP:SEARCH",
                "watchdog_name": "x",
            }
        )
        self.assertEqual(alerts, [])

    def test_watchdog_plugin_error_is_wrapped_as_alert(self):
        manager = WatchdogManager(
            plugins=[_BadWatchdog()],
            policy_loader=_PolicyLoader(
                {
                    "version": "v1",
                    "enabled_watchdogs": ["bad_watchdog"],
                    "min_severity": "LOW",
                    "dedup_window_sec": 0.0,
                    "max_alerts_per_key": 3,
                    "throttle_window_sec": 60.0,
                    "dedup_key_fields": ["watchdog_name", "task_id", "reason_code"],
                }
            ),
        )
        alerts = manager.process(
            {
                "run_id": "r4",
                "task_id": "t4",
                "step_id": 1,
                "chain_mode": "guiagent_v2",
                "event_type": "step_start",
                "status": "RUNNING",
                "intent_key": "global:TAP:SEARCH",
            }
        )
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["reason_code"], "WATCHDOG_PLUGIN_ERROR")
        self.assertEqual(alerts[0]["watchdog_name"], "bad_watchdog")

    def test_policy_can_disable_specific_watchdog(self):
        manager = WatchdogManager(
            plugins=[
                _BadWatchdog(),
            ],
            policy_loader=_PolicyLoader(
                {
                    "version": "v1",
                    "enabled_watchdogs": ["security_watchdog"],
                    "min_severity": "LOW",
                    "dedup_window_sec": 0.0,
                    "max_alerts_per_key": 3,
                    "throttle_window_sec": 60.0,
                    "dedup_key_fields": ["watchdog_name", "task_id", "reason_code"],
                }
            ),
        )
        alerts = manager.process(
            {
                "run_id": "r5",
                "task_id": "t5",
                "step_id": 1,
                "chain_mode": "guiagent_v2",
                "event_type": "step_start",
                "status": "RUNNING",
                "intent_key": "global:TAP:SEARCH",
            }
        )
        self.assertEqual(alerts, [])

    def test_dedup_window_suppresses_duplicate_alert(self):
        manager = build_default_watchdog_manager()
        event = {
            "run_id": "r6",
            "task_id": "t6",
            "step_id": 1,
            "chain_mode": "guiagent_v2",
            "event_type": "guard_decision",
            "status": "HANDOVER",
            "intent_key": "global:TAP:SUBMIT",
            "policy_decision": "deny",
            "policy_reason": "ACTION_DENIED_BY_POLICY",
        }
        first = manager.process(event)
        second = manager.process(event)
        self.assertGreaterEqual(len(first), 1)
        self.assertEqual(second, [])

    def test_throttle_window_limits_alert_rate(self):
        manager = WatchdogManager(
            plugins=[SecurityWatchdog()],
            policy_loader=_PolicyLoader(
                {
                    "version": "v1",
                    "enabled_watchdogs": ["security_watchdog"],
                    "min_severity": "LOW",
                    "dedup_window_sec": 0.0,
                    "max_alerts_per_key": 1,
                    "throttle_window_sec": 60.0,
                    "dedup_key_fields": ["watchdog_name", "task_id", "reason_code"],
                }
            ),
        )
        event = {
            "run_id": "r7",
            "task_id": "t7",
            "step_id": 1,
            "chain_mode": "guiagent_v2",
            "event_type": "guard_decision",
            "status": "HANDOVER",
            "intent_key": "global:TAP:SUBMIT",
            "policy_decision": "deny",
            "policy_reason": "ACTION_DENIED_BY_POLICY",
        }
        first = manager.process(event)
        second = manager.process(event)
        self.assertGreaterEqual(len(first), 1)
        self.assertEqual(second, [])

    def test_escalation_rules_raise_alert_severity(self):
        manager = WatchdogManager(
            plugins=[SecurityWatchdog()],
            policy_loader=_PolicyLoader(
                {
                    "version": "v1",
                    "enabled_watchdogs": ["security_watchdog"],
                    "min_severity": "LOW",
                    "dedup_window_sec": 0.0,
                    "max_alerts_per_key": 10,
                    "throttle_window_sec": 60.0,
                    "dedup_key_fields": ["watchdog_name", "task_id", "reason_code"],
                    "escalation_rules": [
                        {
                            "name": "deny-to-critical",
                            "watchdog_name": "security_watchdog",
                            "policy_decision": "deny",
                            "threshold": 2,
                            "window_sec": 60.0,
                            "target_severity": "CRITICAL",
                        }
                    ],
                }
            ),
        )
        event = {
            "run_id": "r8",
            "task_id": "t8",
            "step_id": 1,
            "chain_mode": "guiagent_v2",
            "event_type": "guard_decision",
            "status": "HANDOVER",
            "intent_key": "global:TAP:SUBMIT",
            "policy_decision": "deny",
            "policy_reason": "ACTION_DENIED_BY_POLICY",
        }
        first = manager.process(event)
        second = manager.process(event)
        self.assertEqual(first[0]["watchdog_severity"], "HIGH")
        self.assertFalse(first[0].get("watchdog_escalated", False))
        self.assertEqual(second[0]["watchdog_severity"], "CRITICAL")
        self.assertTrue(second[0].get("watchdog_escalated", False))
        self.assertEqual(second[0].get("watchdog_escalation_rule"), "deny-to-critical")

    def test_escalation_rule_not_matched_keeps_original_severity(self):
        manager = WatchdogManager(
            plugins=[SecurityWatchdog()],
            policy_loader=_PolicyLoader(
                {
                    "version": "v1",
                    "enabled_watchdogs": ["security_watchdog"],
                    "min_severity": "LOW",
                    "dedup_window_sec": 0.0,
                    "max_alerts_per_key": 10,
                    "throttle_window_sec": 60.0,
                    "dedup_key_fields": ["watchdog_name", "task_id", "reason_code"],
                    "escalation_rules": [
                        {
                            "name": "deny-to-critical",
                            "watchdog_name": "security_watchdog",
                            "policy_decision": "deny",
                            "threshold": 1,
                            "window_sec": 60.0,
                            "target_severity": "CRITICAL",
                        }
                    ],
                }
            ),
        )
        confirm_event = {
            "run_id": "r9",
            "task_id": "t9",
            "step_id": 1,
            "chain_mode": "guiagent_v2",
            "event_type": "guard_decision",
            "status": "RUNNING",
            "intent_key": "global:TAP:SUBMIT",
            "policy_decision": "confirm",
            "policy_reason": "NEEDS_CONFIRM",
        }
        alerts = manager.process(confirm_event)
        self.assertEqual(alerts[0]["watchdog_severity"], "MEDIUM")
        self.assertFalse(alerts[0].get("watchdog_escalated", False))

    def test_cross_task_aggregation_emits_aggregate_alert(self):
        manager = WatchdogManager(
            plugins=[SecurityWatchdog()],
            policy_loader=_PolicyLoader(
                {
                    "version": "v1",
                    "enabled_watchdogs": ["security_watchdog"],
                    "min_severity": "LOW",
                    "dedup_window_sec": 0.0,
                    "max_alerts_per_key": 10,
                    "throttle_window_sec": 60.0,
                    "dedup_key_fields": ["watchdog_name", "task_id", "reason_code"],
                    "escalation_rules": [],
                    "cross_task_aggregation": {
                        "enabled": True,
                        "window_sec": 120.0,
                        "min_distinct_tasks": 2,
                        "emit_throttle_sec": 0.0,
                        "severity": "CRITICAL",
                        "group_by_fields": ["watchdog_name", "reason_code", "alert_category"],
                    },
                }
            ),
        )
        event1 = {
            "run_id": "r10",
            "task_id": "t10",
            "step_id": 1,
            "chain_mode": "guiagent_v2",
            "event_type": "guard_decision",
            "status": "HANDOVER",
            "intent_key": "global:TAP:SUBMIT",
            "policy_decision": "deny",
            "policy_reason": "ACTION_DENIED_BY_POLICY",
        }
        event2 = {
            "run_id": "r11",
            "task_id": "t11",
            "step_id": 1,
            "chain_mode": "guiagent_v2",
            "event_type": "guard_decision",
            "status": "HANDOVER",
            "intent_key": "global:TAP:SUBMIT",
            "policy_decision": "deny",
            "policy_reason": "ACTION_DENIED_BY_POLICY",
        }
        first = manager.process(event1)
        second = manager.process(event2)
        self.assertTrue(any(item.get("watchdog_name") == "security_watchdog" for item in first))
        aggregate = [item for item in second if item.get("watchdog_name") == "aggregate_watchdog"]
        self.assertEqual(len(aggregate), 1)
        self.assertEqual(aggregate[0].get("watchdog_severity"), "CRITICAL")
        self.assertEqual(aggregate[0].get("aggregated_distinct_tasks"), 2)
        self.assertEqual(aggregate[0].get("reason_code"), "CROSS_TASK_ALERT_SPIKE")


if __name__ == "__main__":
    unittest.main()
