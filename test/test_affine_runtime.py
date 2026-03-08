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

    def test_tap_projection_with_affine_norm(self):
        req = map_legacy_action_to_request({"name": "Tap", "arguments": {"x": 100, "y": 200}})
        projected = project_action(
            req,
            topology_result={
                "reference_screen": {"width": 1000, "height": 2000},
                "target_screen": {"width": 500, "height": 1000},
                "affine_norm": {"a": 1.0, "b": 0.0, "tx": 0.1, "c": 0.0, "d": 1.0, "ty": 0.2},
                "confidence": 0.91,
            },
        )
        # normalized(100,200)->(0.1,0.1), plus (0.1,0.2) => (0.2,0.3) on 500x1000
        self.assertEqual(projected["arguments"]["x"], 100)
        self.assertEqual(projected["arguments"]["y"], 300)
        self.assertEqual(projected.get("projection", {}).get("mode"), "affine_norm")


if __name__ == "__main__":
    unittest.main()
