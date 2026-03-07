import unittest

from guiagent_v2.action_engine.affine_runtime import project_action
from guiagent_v2.intent_contract import map_legacy_action_to_request


class TestAffineRuntime(unittest.TestCase):
    def test_tap_projection_with_screen_scaling(self):
        req = map_legacy_action_to_request({"name": "Tap", "arguments": {"x": 100, "y": 200}})
        projected = project_action(
            req,
            topology_result={
                "reference_screen": {"width": 1000, "height": 2000},
                "target_screen": {"width": 2000, "height": 4000},
                "confidence": 0.9,
            },
        )
        self.assertEqual(projected["arguments"]["x"], 200)
        self.assertEqual(projected["arguments"]["y"], 400)
        self.assertIn("projection", projected)

    def test_swipe_projection(self):
        req = map_legacy_action_to_request(
            {"name": "Swipe", "arguments": {"x1": 10, "y1": 20, "x2": 30, "y2": 40}}
        )
        projected = project_action(
            req,
            topology_result={"scale_x": 2.0, "scale_y": 0.5, "offset_x": 0, "offset_y": 0},
        )
        self.assertEqual(projected["arguments"]["x1"], 20)
        self.assertEqual(projected["arguments"]["y1"], 10)
        self.assertEqual(projected["arguments"]["x2"], 60)
        self.assertEqual(projected["arguments"]["y2"], 20)


if __name__ == "__main__":
    unittest.main()

