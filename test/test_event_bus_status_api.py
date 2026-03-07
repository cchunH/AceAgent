import json
import os
import tempfile
import unittest

from guiagent_v2.runtime.event_bus import JSONLEventBus
from guiagent_v2.runtime.status_api import TaskStatusStore


class TestEventBusAndStatusAPI(unittest.TestCase):
    def test_jsonl_event_bus_and_status_store(self):
        with tempfile.TemporaryDirectory() as td:
            event_path = os.path.join(td, "events.jsonl")
            bus = JSONLEventBus(event_path, default_chain_mode="guiagent_v2_shadow")
            store = TaskStatusStore()

            e1 = bus.emit(
                {
                    "run_id": "run-1",
                    "task_id": "task-1",
                    "step_id": 1,
                    "event_type": "step_start",
                    "status": "RUNNING",
                    "intent_key": "global:TAP:SEARCH_BAR",
                }
            )
            e2 = bus.emit(
                {
                    "run_id": "run-1",
                    "task_id": "task-1",
                    "step_id": 1,
                    "event_type": "step_end",
                    "status": "SUCCESS",
                    "intent_key": "global:TAP:SEARCH_BAR",
                    "latency_ms": 123,
                }
            )
            store.update(e1)
            store.update(e2)

            status = store.get_task_status("run-1", "task-1")
            self.assertIsNotNone(status)
            self.assertEqual(status["status"], "SUCCESS")
            self.assertEqual(status["event_count"], 2)

            timeline = store.get_task_timeline("run-1", "task-1")
            self.assertEqual(len(timeline), 2)

            with open(event_path, "r", encoding="utf-8") as f:
                lines = [json.loads(line) for line in f]
            self.assertEqual(len(lines), 2)
            for line in lines:
                self.assertIn("run_id", line)
                self.assertIn("task_id", line)
                self.assertIn("step_id", line)
                self.assertIn("chain_mode", line)
                self.assertIn("event_type", line)
                self.assertIn("status", line)
                self.assertIn("intent_key", line)


if __name__ == "__main__":
    unittest.main()

