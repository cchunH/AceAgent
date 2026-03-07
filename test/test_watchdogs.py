import unittest

from guiagent_v2.runtime.watchdogs import WatchdogManager, build_default_watchdog_manager


class _BadWatchdog:
    name = "bad_watchdog"

    def on_event(self, event):
        raise RuntimeError("boom")


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
        manager = WatchdogManager(plugins=[_BadWatchdog()])
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


if __name__ == "__main__":
    unittest.main()
