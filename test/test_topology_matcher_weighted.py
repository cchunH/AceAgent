import unittest

from guiagent_v2.state_engine.topology_matcher import match_topology


class TestTopologyMatcherWeighted(unittest.TestCase):
    def test_core_anchor_weight_penalizes_miss(self):
        expected = [
            {
                "id": "e-core",
                "text": "Search",
                "role": "CORE",
                "zone": "top",
                "norm_bbox": {"x": 0.5, "y": 0.08, "w": 0.0, "h": 0.0},
            },
            {
                "id": "e-aux",
                "text": "Home",
                "role": "AUXILIARY",
                "zone": "bottom",
                "norm_bbox": {"x": 0.1, "y": 0.95, "w": 0.0, "h": 0.0},
            },
        ]
        observed = [
            {
                "id": "o-aux",
                "text": "Home",
                "role": "AUXILIARY",
                "zone": "bottom",
                "norm_bbox": {"x": 0.1, "y": 0.95, "w": 0.0, "h": 0.0},
            }
        ]
        result = match_topology(observed, expected)
        self.assertLess(result.confidence, 0.6)
        self.assertEqual(result.reason_code, "TOPOLOGY_MISMATCH")
        self.assertLess(result.core_confidence, result.aux_confidence)

    def test_core_anchor_match_can_pass_with_aux_missing(self):
        expected = [
            {
                "id": "e-core",
                "text": "Search",
                "role": "CORE",
                "zone": "top",
                "norm_bbox": {"x": 0.5, "y": 0.08, "w": 0.0, "h": 0.0},
            },
            {
                "id": "e-aux",
                "text": "Home",
                "role": "AUXILIARY",
                "zone": "bottom",
                "norm_bbox": {"x": 0.1, "y": 0.95, "w": 0.0, "h": 0.0},
            },
        ]
        observed = [
            {
                "id": "o-core",
                "text": "Search",
                "role": "CORE",
                "zone": "top",
                "norm_bbox": {"x": 0.51, "y": 0.08, "w": 0.0, "h": 0.0},
            }
        ]
        result = match_topology(observed, expected)
        self.assertGreaterEqual(result.confidence, 0.6)
        self.assertEqual(result.reason_code, "TOPOLOGY_MATCH_OK")
        self.assertGreaterEqual(result.core_confidence, result.aux_confidence)

    def test_identical_sets_high_confidence(self):
        expected = [
            {
                "id": "a1",
                "text": "Search",
                "role": "CORE",
                "zone": "top",
                "norm_bbox": {"x": 0.5, "y": 0.08, "w": 0.0, "h": 0.0},
            },
            {
                "id": "a2",
                "text": "Home",
                "role": "AUXILIARY",
                "zone": "bottom",
                "norm_bbox": {"x": 0.1, "y": 0.95, "w": 0.0, "h": 0.0},
            },
        ]
        observed = [
            {
                "id": "b1",
                "text": "Search",
                "role": "CORE",
                "zone": "top",
                "norm_bbox": {"x": 0.5, "y": 0.08, "w": 0.0, "h": 0.0},
            },
            {
                "id": "b2",
                "text": "Home",
                "role": "AUXILIARY",
                "zone": "bottom",
                "norm_bbox": {"x": 0.1, "y": 0.95, "w": 0.0, "h": 0.0},
            },
        ]
        result = match_topology(observed, expected)
        self.assertGreaterEqual(result.confidence, 0.95)
        self.assertEqual(result.reason_code, "TOPOLOGY_MATCH_OK")
        self.assertIn(result.transform_mode, {"scale_translate", "affine6"})
        self.assertGreaterEqual(result.transform_pair_count, 2)

    def test_topology_estimates_affine_translation(self):
        expected = [
            {
                "id": "e1",
                "text": "A",
                "role": "CORE",
                "zone": "top",
                "norm_bbox": {"x": 0.1, "y": 0.1, "w": 0.0, "h": 0.0},
            },
            {
                "id": "e2",
                "text": "B",
                "role": "CORE",
                "zone": "middle",
                "norm_bbox": {"x": 0.6, "y": 0.5, "w": 0.0, "h": 0.0},
            },
            {
                "id": "e3",
                "text": "C",
                "role": "AUXILIARY",
                "zone": "bottom",
                "norm_bbox": {"x": 0.2, "y": 0.8, "w": 0.0, "h": 0.0},
            },
        ]
        observed = [
            {
                "id": "o1",
                "text": "A",
                "role": "CORE",
                "zone": "top",
                "norm_bbox": {"x": 0.2, "y": 0.2, "w": 0.0, "h": 0.0},
            },
            {
                "id": "o2",
                "text": "B",
                "role": "CORE",
                "zone": "middle",
                "norm_bbox": {"x": 0.7, "y": 0.6, "w": 0.0, "h": 0.0},
            },
            {
                "id": "o3",
                "text": "C",
                "role": "AUXILIARY",
                "zone": "bottom",
                "norm_bbox": {"x": 0.3, "y": 0.9, "w": 0.0, "h": 0.0},
            },
        ]
        result = match_topology(observed, expected)
        self.assertGreaterEqual(result.confidence, 0.6)
        self.assertEqual(result.transform_mode, "affine6")
        self.assertGreaterEqual(result.transform_pair_count, 3)
        self.assertAlmostEqual(float(result.affine_norm.get("tx", 0.0)), 0.1, delta=0.05)
        self.assertAlmostEqual(float(result.affine_norm.get("ty", 0.0)), 0.1, delta=0.05)


if __name__ == "__main__":
    unittest.main()
