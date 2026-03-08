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


if __name__ == "__main__":
    unittest.main()
