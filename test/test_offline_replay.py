import json
import os
import tempfile
import unittest

from guiagent_v2.runtime.offline_replay import rebuild_blueprints_from_steps


class TestOfflineReplay(unittest.TestCase):
    def test_rebuild_blueprints_from_steps(self):
        with tempfile.TemporaryDirectory() as td:
            steps_path = os.path.join(td, "steps.json")
            blueprints_path = os.path.join(td, "blueprints.json")
            steps = [
                {
                    "step": 0,
                    "operation": "init",
                    "init_info_pool": {"width": 1080, "height": 2340},
                },
                {
                    "step": 1,
                    "operation": "perception",
                    "perception_infos": [{"text": "Search", "coordinates": (520, 110)}],
                },
                {
                    "step": 1,
                    "operation": "action",
                    "action_object": {"name": "Tap", "arguments": {"x": 520, "y": 110}},
                },
                {
                    "step": 2,
                    "operation": "perception",
                    "perception_infos": [{"text": "Results", "coordinates": (320, 180)}],
                },
                {
                    "step": 1,
                    "operation": "action_reflection",
                    "outcome": "A",
                },
            ]
            with open(steps_path, "w", encoding="utf-8") as f:
                json.dump(steps, f, ensure_ascii=False)

            result = rebuild_blueprints_from_steps(steps_path, blueprints_path)
            self.assertEqual(result["status"], "SUCCESS")
            self.assertGreaterEqual(result["rebuilt_count"], 1)
            self.assertTrue(os.path.exists(blueprints_path))


if __name__ == "__main__":
    unittest.main()
