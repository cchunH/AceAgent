import json
import os
import tempfile
import unittest

from guiagent_v2.blueprint_hub import BlueprintRepository
from guiagent_v2.runtime.blueprint_sync import (
    upsert_blueprint_from_observation,
    upsert_blueprint_from_observation_with_gate,
)
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
            self.assertIn("static_skeleton", updated)
            self.assertTrue(updated["static_skeleton"].get("signature"))
            self.assertTrue(updated["post_expectations"])
            self.assertIn("denoise_stable_ratio", updated.get("metadata", {}))
            found = repo.get_blueprint("global:TAP:SEARCH_BAR", "global:DEFAULT")
            self.assertIsNotNone(found)

    def test_upsert_blueprint_uses_delta_patch_for_existing(self):
        with tempfile.TemporaryDirectory() as td:
            repo = BlueprintRepository(os.path.join(td, "blueprints.json"))
            first = upsert_blueprint_from_observation(
                repo=repo,
                intent_key="global:TAP:SEARCH_BAR",
                screen_width=1080,
                screen_height=2340,
                perception_infos_pre=[
                    {"text": "Search", "coordinates": (520, 110)},
                    {"text": "Home", "coordinates": (100, 2250)},
                ],
                perception_infos_post=[
                    {"text": "Search", "coordinates": (520, 110)},
                    {"text": "Results", "coordinates": (320, 200)},
                ],
                action_outcome="A",
                post_check_result={"passed": True, "reason_code": "STATE_TRANSITION_OK"},
            )
            version1 = first.get("version")
            anchors1 = list(first.get("anchors", []))
            skeleton1 = dict(first.get("static_skeleton", {}))

            second = upsert_blueprint_from_observation(
                repo=repo,
                intent_key="global:TAP:SEARCH_BAR",
                screen_width=1080,
                screen_height=2340,
                perception_infos_pre=[
                    {"text": "Random Ad", "coordinates": (900, 300)},
                    {"text": "Popup", "coordinates": (540, 1200)},
                ],
                perception_infos_post=[
                    {"text": "Spinner", "coordinates": (520, 1100)},
                    {"text": "Loading", "coordinates": (500, 1120)},
                ],
                action_outcome="C",
                post_check_result={"passed": False, "reason_code": "ASSERTION_MISMATCH"},
            )
            self.assertEqual(second.get("version"), version1)
            self.assertEqual(second.get("anchors", []), anchors1)
            self.assertEqual(second.get("static_skeleton", {}), skeleton1)
            metadata2 = dict(second.get("metadata", {}))
            self.assertEqual(metadata2.get("last_patch_mode"), "delta")
            self.assertIn("anchors", list(metadata2.get("last_patch_suppressed_fields", [])))

    def test_upsert_blueprint_gate_blocks_structural_update(self):
        with tempfile.TemporaryDirectory() as td:
            repo = BlueprintRepository(os.path.join(td, "blueprints.json"))
            first = upsert_blueprint_from_observation(
                repo=repo,
                intent_key="global:TAP:SEARCH_BAR",
                screen_width=1080,
                screen_height=2340,
                perception_infos_pre=[
                    {"text": "Search", "coordinates": (520, 110)},
                    {"text": "Home", "coordinates": (100, 2250)},
                ],
                perception_infos_post=[
                    {"text": "Search", "coordinates": (520, 110)},
                    {"text": "Results", "coordinates": (320, 200)},
                ],
                action_outcome="A",
                post_check_result={"passed": True, "reason_code": "STATE_TRANSITION_OK"},
            )
            anchors_before = list(first.get("anchors", []))
            skeleton_before = dict(first.get("static_skeleton", {}))
            result = upsert_blueprint_from_observation_with_gate(
                repo=repo,
                intent_key="global:TAP:SEARCH_BAR",
                screen_width=1080,
                screen_height=2340,
                perception_infos_pre=[
                    {"text": "Transient", "coordinates": (100, 100)},
                ],
                perception_infos_post=[
                    {"text": "Noise", "coordinates": (900, 2200)},
                ],
                action_outcome="A",
                post_check_result={"passed": True, "reason_code": "STATE_TRANSITION_OK"},
                replay_gate_min_score=0.95,
            )
            updated = dict(result.get("blueprint", {}))
            sync = dict(result.get("sync", {}))
            self.assertFalse(sync.get("replay_gate_passed"))
            self.assertIn("metadata_only", str(sync.get("sync_mode", "")))
            self.assertEqual(updated.get("anchors", []), anchors_before)
            self.assertEqual(updated.get("static_skeleton", {}), skeleton_before)
            self.assertIn("replay_gate_reason", dict(updated.get("metadata", {})))
            self.assertTrue("anchors" in list(sync.get("suppressed_fields", [])) or "anchors" in list(dict(updated.get("metadata", {})).get("last_patch_suppressed_fields", [])))

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
            self.assertIn("anchor_strategy", out["summary"])
            self.assertIn("topology_projection", out["summary"])
            self.assertIn("screenshot_trace", out["summary"])
            self.assertIn("blueprint_sync", out["summary"])
            self.assertIn("flow_audit", out["summary"])
            self.assertIn("blueprint_vector_backend", out["summary"])


if __name__ == "__main__":
    unittest.main()
