import unittest

from guiagent_v2.intent_contract import map_legacy_action_to_request
from guiagent_v2.state_engine import build_static_skeleton, extract_anchors, match_topology
from guiagent_v2.action_engine import run_pre_assertion, run_post_check


class TestStateActionEngine(unittest.TestCase):
    def test_extract_anchors_and_match(self):
        infos = [
            {"text": "Back", "coordinates": (30, 40)},
            {"text": "Search", "coordinates": (520, 110)},
            {"text": "Home", "coordinates": (100, 2250)},
        ]
        anchors = extract_anchors(infos, (1080, 2340))
        self.assertGreaterEqual(len(anchors), 2)
        self.assertTrue(any(a.role == "CORE" for a in anchors))

        expected = [a.to_dict() for a in anchors[:2]]
        result = match_topology(anchors, expected)
        self.assertGreaterEqual(result.confidence, 0.5)

    def test_pre_assertion_structural_fail(self):
        req = map_legacy_action_to_request({"name": "Tap", "arguments": {"x": 1, "y": 1}})
        context = {
            "perception_infos_pre": [{"text": "Profile", "coordinates": (500, 100)}],
            "screen_width": 1080,
            "screen_height": 2340,
            "expected_anchors": [
                {
                    "id": "e1",
                    "text": "Search",
                    "norm_bbox": {"x": 0.1, "y": 0.1, "w": 0.0, "h": 0.0},
                }
            ],
        }
        result = run_pre_assertion(req, context)
        self.assertFalse(result["passed"])
        self.assertEqual(result["reason_code"], "STRUCTURAL_ASSERTION_FAILED")
        self.assertIn("core_anchor_confidence", result)
        self.assertIn("aux_anchor_confidence", result)
        self.assertIn("geometry_confidence", result)

    def test_post_check_no_change(self):
        req = map_legacy_action_to_request({"name": "Tap", "arguments": {"x": 1, "y": 1}})
        same = [{"text": "Search", "coordinates": (100, 100)}]
        context = {
            "perception_infos_pre": same,
            "perception_infos_post": same,
            "screen_width": 1080,
            "screen_height": 2340,
        }
        result = run_post_check(req, context)
        self.assertFalse(result["passed"])
        self.assertEqual(result["reason_code"], "NO_STATE_CHANGE")
        self.assertIn("core_anchor_confidence", result)
        self.assertIn("aux_anchor_confidence", result)
        self.assertIn("geometry_confidence", result)

    def test_pre_assertion_shadow_navigation_softens_skeleton(self):
        req = map_legacy_action_to_request({"name": "Back", "arguments": {}})
        expected = build_static_skeleton(
            frames=[[{"text": "Search", "coordinates": (520, 110)}]],
            screen_size=(1080, 2340),
            min_presence_ratio=1.0,
            max_nodes=8,
        ).to_dict()
        context = {
            "perception_infos_pre": [{"text": "Profile", "coordinates": (500, 100)}],
            "screen_width": 1080,
            "screen_height": 2340,
            "expected_skeleton": expected,
            "mobile_execution_mode": "shadow",
        }
        result = run_pre_assertion(req, context)
        self.assertTrue(result["passed"])
        self.assertIn("skeleton_confidence", result)

    def test_pre_assertion_device_navigation_keeps_skeleton_guard(self):
        req = map_legacy_action_to_request({"name": "Back", "arguments": {}})
        expected = build_static_skeleton(
            frames=[[{"text": "Search", "coordinates": (520, 110)}]],
            screen_size=(1080, 2340),
            min_presence_ratio=1.0,
            max_nodes=8,
        ).to_dict()
        context = {
            "perception_infos_pre": [{"text": "Profile", "coordinates": (500, 100)}],
            "screen_width": 1080,
            "screen_height": 2340,
            "expected_skeleton": expected,
            "mobile_execution_mode": "device",
        }
        result = run_pre_assertion(req, context)
        self.assertFalse(result["passed"])
        self.assertEqual(result["reason_code"], "SKELETON_ASSERTION_FAILED")


if __name__ == "__main__":
    unittest.main()
