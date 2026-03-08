import unittest

from guiagent_v2.state_engine import (
    build_blueprint_match_index,
    build_static_skeleton,
    denoise_perception_frames,
    match_blueprint_fast,
    match_static_skeleton,
)


class TestSceneDenoiseAndMatch(unittest.TestCase):
    def test_denoise_perception_frames_extracts_stable_infos(self):
        frames = [
            [
                {"text": "Search", "coordinates": (520, 110)},
                {"text": "Toast123", "coordinates": (600, 600)},
            ],
            [
                {"text": "Search", "coordinates": (518, 112)},
            ],
        ]
        result = denoise_perception_frames(frames, (1080, 2340), min_presence_ratio=0.6)
        stable_texts = {str(item.get("text", "")).strip() for item in result["stable_infos"]}
        self.assertIn("Search", stable_texts)

    def test_static_skeleton_match(self):
        skeleton_a = build_static_skeleton(
            frames=[[{"text": "Search", "coordinates": (520, 110)}]],
            screen_size=(1080, 2340),
        )
        skeleton_b = build_static_skeleton(
            frames=[[{"text": "Search", "coordinates": (522, 108)}]],
            screen_size=(1080, 2340),
        )
        match = match_static_skeleton(skeleton_b, skeleton_a)
        self.assertGreater(match.confidence, 0.5)

    def test_fast_blueprint_match(self):
        skeleton = build_static_skeleton(
            frames=[[{"text": "Search", "coordinates": (520, 110)}]],
            screen_size=(1080, 2340),
        ).to_dict()
        index = build_blueprint_match_index(
            [
                {
                    "intent_key": "global:TAP:SEARCH_BAR",
                    "app_state": "global:DEFAULT",
                    "static_skeleton": skeleton,
                }
            ]
        )
        matched = match_blueprint_fast(
            observed_skeleton=skeleton,
            index=index,
            app_state="global:DEFAULT",
            top_k=1,
        )
        self.assertTrue(matched)
        self.assertEqual(matched[0]["intent_key"], "global:TAP:SEARCH_BAR")
        self.assertGreaterEqual(matched[0]["score"], 0.8)

    def test_fast_blueprint_match_uses_dynamic_slots_to_reduce_noise_recall(self):
        observed = {
            "signature": "obs-1",
            "nodes": [
                {
                    "type": "TEXT",
                    "text": "Search",
                    "zone": "top",
                    "norm_bbox": {"x": 0.5, "y": 0.08, "w": 0.0, "h": 0.0},
                },
                {
                    "type": "TEXT",
                    "text": "Toast",
                    "zone": "middle",
                    "norm_bbox": {"x": 0.5, "y": 0.45, "w": 0.0, "h": 0.0},
                },
            ],
            "dynamic_slots": [
                {
                    "key": "middle:toast",
                    "zone": "middle",
                    "text": "Toast",
                    "norm_pos": {"x": 0.5, "y": 0.45},
                }
            ],
        }
        index = build_blueprint_match_index(
            [
                {
                    "intent_key": "global:TAP:SEARCH_DYNAMIC_TOAST",
                    "app_state": "global:DEFAULT",
                    "static_skeleton": {
                        "signature": "bp-a",
                        "nodes": [
                            {
                                "type": "TEXT",
                                "text": "Search",
                                "zone": "top",
                                "norm_bbox": {"x": 0.5, "y": 0.08, "w": 0.0, "h": 0.0},
                            }
                        ],
                        "dynamic_slots": [
                            {
                                "key": "middle:toast",
                                "zone": "middle",
                                "text": "Toast",
                            }
                        ],
                    },
                },
                {
                    "intent_key": "global:TAP:SEARCH_STATIC_TOAST",
                    "app_state": "global:DEFAULT",
                    "static_skeleton": {
                        "signature": "bp-b",
                        "nodes": [
                            {
                                "type": "TEXT",
                                "text": "Search",
                                "zone": "top",
                                "norm_bbox": {"x": 0.5, "y": 0.08, "w": 0.0, "h": 0.0},
                            },
                            {
                                "type": "TEXT",
                                "text": "Toast",
                                "zone": "middle",
                                "norm_bbox": {"x": 0.5, "y": 0.45, "w": 0.0, "h": 0.0},
                            },
                        ],
                        "dynamic_slots": [],
                    },
                },
            ]
        )
        matched = match_blueprint_fast(
            observed_skeleton=observed,
            index=index,
            app_state="global:DEFAULT",
            top_k=2,
        )
        self.assertTrue(matched)
        self.assertEqual(matched[0]["intent_key"], "global:TAP:SEARCH_DYNAMIC_TOAST")
        static_toast = [item for item in matched if item.get("intent_key") == "global:TAP:SEARCH_STATIC_TOAST"]
        self.assertTrue(static_toast)
        self.assertGreater(static_toast[0]["dynamic_noise_penalty"], 0.0)

    def test_denoise_clusters_jittered_positions(self):
        frames = [
            [{"text": "Search", "coordinates": (520, 110)}],
            [{"text": "Search", "coordinates": (525, 114)}],
            [{"text": "Search", "coordinates": (518, 109)}],
        ]
        result = denoise_perception_frames(frames, (1080, 2340), min_presence_ratio=0.66)
        stable = result["stable_infos"]
        self.assertTrue(stable)
        self.assertEqual(stable[0]["text"], "Search")
        x, y = stable[0]["coordinates"]
        self.assertGreaterEqual(x, 518)
        self.assertLessEqual(x, 525)
        self.assertGreaterEqual(y, 109)
        self.assertLessEqual(y, 114)

    def test_denoise_counts_presence_once_per_frame(self):
        frames = [
            [
                {"text": "Search", "coordinates": (520, 110)},
                {"text": "Search", "coordinates": (521, 111)},
            ],
            [
                {"text": "Search", "coordinates": (520, 110)},
            ],
        ]
        result = denoise_perception_frames(frames, (1080, 2340), min_presence_ratio=0.9)
        stable_texts = {str(item.get("text", "")).strip() for item in result["stable_infos"]}
        self.assertIn("Search", stable_texts)

    def test_static_skeleton_contains_dynamic_slots(self):
        skeleton = build_static_skeleton(
            frames=[
                [{"text": "Search", "coordinates": (520, 110)}, {"text": "Toast", "coordinates": (500, 900)}],
                [{"text": "Search", "coordinates": (521, 111)}],
            ],
            screen_size=(1080, 2340),
            min_presence_ratio=0.6,
        )
        data = skeleton.to_dict()
        self.assertIn("dynamic_slots", data)
        self.assertTrue(isinstance(data["dynamic_slots"], list))


if __name__ == "__main__":
    unittest.main()
