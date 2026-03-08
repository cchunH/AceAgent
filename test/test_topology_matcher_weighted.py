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


if __name__ == "__main__":
    unittest.main()
