import json
import os
import tempfile
import unittest

from guiagent_v2.runtime.event_bus import JSONLEventBus
from guiagent_v2.runtime.event_schema import normalize_event, validate_event


class TestEventSchema(unittest.TestCase):
    def test_normalize_and_validate_ok(self):
        event = normalize_event(
            {
                "run_id": "r1",
                "task_id": "t1",
                "step_id": "2",
                "chain_mode": "guiagent_v2",
                "event_type": "skill_route",
                "status": "success",
                "intent_key": "web:OPEN:URL",
                "channel": "web_skill",
                "route_reason": "web_intent_prefix",
            },
            default_chain_mode="legacy",
        )
        self.assertEqual(event["step_id"], 2)
        self.assertEqual(event["status"], "SUCCESS")
        valid, detail = validate_event(event)
        self.assertTrue(valid)
        self.assertEqual(detail["code"], "OK")

    def test_validate_guard_decision_requires_policy_decision(self):
        event = normalize_event(
            {
                "run_id": "r2",
                "task_id": "t2",
                "step_id": 1,
                "chain_mode": "guiagent_v2",
                "event_type": "guard_decision",
                "status": "SUCCESS",
                "intent_key": "global:TAP:SEARCH",
            },
            default_chain_mode="legacy",
        )
        valid, detail = validate_event(event)
        self.assertFalse(valid)
        self.assertEqual(detail["code"], "EVENT_SCHEMA_INVALID")
        self.assertTrue(any("policy_decision" in item for item in detail["errors"]))

    def test_event_bus_marks_invalid_schema(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "events.jsonl")
            bus = JSONLEventBus(p, default_chain_mode="guiagent_v2")
            emitted = bus.emit(
                {
                    "run_id": "r3",
                    "task_id": "t3",
                    "step_id": 1,
                    "event_type": "guard_decision",
                    "status": "SUCCESS",
                    "intent_key": "global:TAP:SEARCH",
                }
            )
            self.assertFalse(emitted["schema_valid"])
            self.assertIn("schema_error", emitted)
            with open(p, "r", encoding="utf-8") as f:
                row = json.loads(f.readline())
            self.assertEqual(row["event_schema_version"], "v1")
            self.assertFalse(row["schema_valid"])


if __name__ == "__main__":
    unittest.main()
