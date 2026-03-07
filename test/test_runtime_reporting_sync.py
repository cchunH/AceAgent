import json
import os
import tempfile
import unittest

from guiagent_v2.blueprint_hub import BlueprintRepository
from guiagent_v2.runtime.blueprint_sync import upsert_blueprint_from_observation
from guiagent_v2.runtime.reporting import write_runtime_summary


class TestRuntimeReportingAndSync(unittest.TestCase):
    def test_upsert_blueprint_from_observation(self):
        with tempfile.TemporaryDirectory() as td:
            repo = BlueprintRepository(os.path.join(td, "blueprints.json"))
            updated = upsert_blueprint_from_observation(
                repo=repo,
                intent_key="global:TAP:SEARCH_BAR",
                screen_width=1080,
                screen_height=2340,
                perception_infos_pre=[
                    {"text": "Search", "coordinates": (520, 110)},
                    {"text": "Home", "coordinates": (100, 2250)},
                ],
                perception_infos_post=[
                    {"text": "Search Results", "coordinates": (320, 200)},
                ],
                action_outcome="A",
                post_check_result={"passed": True, "reason_code": "STATE_TRANSITION_OK"},
            )
            self.assertIn("anchors", updated)
            self.assertTrue(updated["post_expectations"])
            found = repo.get_blueprint("global:TAP:SEARCH_BAR", "global:DEFAULT")
            self.assertIsNotNone(found)

    def test_write_runtime_summary(self):
        with tempfile.TemporaryDirectory() as td:
            event_path = os.path.join(td, "events.jsonl")
            with open(event_path, "w", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "run_id": "r1",
                            "task_id": "t1",
                            "step_id": 1,
                            "chain_mode": "legacy",
                            "event_type": "step_end",
                            "status": "SUCCESS",
                            "intent_key": "global:TAP:SEARCH_BAR",
                            "latency_ms": 100,
                        }
                    )
                    + "\n"
                )
                f.write(
                    json.dumps(
                        {
                            "run_id": "r1",
                            "task_id": "t1",
                            "step_id": 999999,
                            "chain_mode": "legacy",
                            "event_type": "task_end",
                            "status": "SUCCESS",
                            "intent_key": "global:TASK:END",
                        }
                    )
                    + "\n"
                )
            repo = BlueprintRepository(os.path.join(td, "blueprints.json"))
            out = write_runtime_summary(td, event_path, repo)
            self.assertTrue(os.path.exists(out["summary_path"]))
            self.assertIn("metrics", out["summary"])


if __name__ == "__main__":
    unittest.main()

