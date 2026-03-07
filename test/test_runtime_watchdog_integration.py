import json
import os
import tempfile
import unittest

from guiagent_v2.runtime.event_bus import JSONLEventBus
from guiagent_v2.runtime.orchestrator_v2 import _emit_and_track
from guiagent_v2.runtime.watchdogs import build_default_watchdog_manager


class TestRuntimeWatchdogIntegration(unittest.TestCase):
    def test_emit_and_track_emits_watchdog_alert(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "events.jsonl")
            bus = JSONLEventBus(p, default_chain_mode="guiagent_v2")
            manager = build_default_watchdog_manager()
            _emit_and_track(
                bus,
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
                },
                watchdog_manager=manager,
            )
            with open(p, "r", encoding="utf-8") as f:
                rows = [json.loads(line) for line in f if line.strip()]
            self.assertGreaterEqual(len(rows), 2)
            event_types = [row.get("event_type") for row in rows]
            self.assertIn("guard_decision", event_types)
            self.assertIn("watchdog_alert", event_types)


if __name__ == "__main__":
    unittest.main()
