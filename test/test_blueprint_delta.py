import unittest

from guiagent_v2.runtime.blueprint_delta import bump_blueprint_version, plan_blueprint_delta


class TestBlueprintDelta(unittest.TestCase):
    def test_bump_blueprint_version(self):
        self.assertEqual(bump_blueprint_version("v0.1.0"), "v0.1.1")
        self.assertEqual(bump_blueprint_version("1.2.3"), "v1.2.4")
        self.assertEqual(bump_blueprint_version("bad"), "v0.1.0")

    def test_plan_delta_structural_update(self):
        existing = {
            "intent_key": "global:TAP:SEARCH_BAR",
            "app_state": "global:DEFAULT",
            "version": "v0.1.0",
            "reference_screen": {"width": 1080, "height": 2340},
            "anchors": [
                {
                    "text": "Search",
                    "zone": "top",
                    "norm_bbox": {"x": 0.5, "y": 0.08, "w": 0.0, "h": 0.0},
                }
            ],
            "static_skeleton": {"signature": "old-sig", "nodes": []},
            "post_expectations": ["Results"],
            "metadata": {"x": 1},
        }
        observed_anchors = [
            {
                "text": "Search Input",
                "zone": "top",
                "norm_bbox": {"x": 0.52, "y": 0.08, "w": 0.0, "h": 0.0},
            }
        ]
        observed_skeleton = {"signature": "new-sig", "nodes": []}
        plan = plan_blueprint_delta(
            existing=existing,
            observed_anchors=observed_anchors,
            observed_skeleton=observed_skeleton,
            discovered_expectations=["More Results"],
            reference_screen={"width": 1080, "height": 2340},
            metadata_update={"denoise_stable_ratio": 0.7},
            allow_structural_update=True,
        )
        self.assertIn("anchors", plan.delta)
        self.assertIn("static_skeleton", plan.delta)
        self.assertTrue(plan.structural_changed)
        self.assertEqual(plan.next_version, "v0.1.1")
        self.assertEqual(plan.rollback_to, "v0.1.0")

    def test_plan_delta_suppress_structural_update(self):
        existing = {
            "intent_key": "global:TAP:SEARCH_BAR",
            "app_state": "global:DEFAULT",
            "version": "v0.1.0",
            "reference_screen": {"width": 1080, "height": 2340},
            "anchors": [
                {
                    "text": "Search",
                    "zone": "top",
                    "norm_bbox": {"x": 0.5, "y": 0.08, "w": 0.0, "h": 0.0},
                }
            ],
            "static_skeleton": {"signature": "old-sig", "nodes": []},
            "post_expectations": ["Results"],
            "metadata": {"x": 1},
        }
        observed_anchors = [
            {
                "text": "Settings",
                "zone": "middle",
                "norm_bbox": {"x": 0.2, "y": 0.4, "w": 0.0, "h": 0.0},
            }
        ]
        observed_skeleton = {"signature": "new-sig", "nodes": []}
        plan = plan_blueprint_delta(
            existing=existing,
            observed_anchors=observed_anchors,
            observed_skeleton=observed_skeleton,
            discovered_expectations=[],
            reference_screen={"width": 1080, "height": 2340},
            metadata_update={"denoise_stable_ratio": 0.1},
            allow_structural_update=False,
        )
        self.assertNotIn("anchors", plan.delta)
        self.assertNotIn("static_skeleton", plan.delta)
        self.assertIn("anchors", plan.suppressed_fields)
        self.assertIn("static_skeleton", plan.suppressed_fields)
        self.assertFalse(plan.structural_changed)
        self.assertEqual(plan.next_version, "v0.1.0")
        self.assertIsNone(plan.rollback_to)


if __name__ == "__main__":
    unittest.main()

