import unittest

from guiagent_v2.runtime.replay_quality import score_replay_sample


class TestReplayQuality(unittest.TestCase):
    def test_score_replay_sample_accepts_stable_case(self):
        result = score_replay_sample(
            perception_infos_pre=[
                {"text": "Search", "coordinates": (520, 110)},
                {"text": "Home", "coordinates": (100, 2200)},
            ],
            perception_infos_post=[
                {"text": "Search", "coordinates": (520, 110)},
                {"text": "Result", "coordinates": (300, 300)},
            ],
            screen_width=1080,
            screen_height=2340,
            action_outcome="A",
            post_check_result={"passed": True, "reason_code": "STATE_TRANSITION_OK"},
            min_score=0.4,
        )
        self.assertTrue(result["accepted"])
        self.assertGreater(result["score"], 0.4)

    def test_score_replay_sample_rejects_unstable_case(self):
        result = score_replay_sample(
            perception_infos_pre=[{"text": "Loading", "coordinates": (10, 10)}],
            perception_infos_post=[{"text": "Ad", "coordinates": (1000, 2300)}],
            screen_width=1080,
            screen_height=2340,
            action_outcome="C",
            post_check_result={"passed": False, "reason_code": "ASSERTION_MISMATCH"},
            min_score=0.7,
        )
        self.assertFalse(result["accepted"])
        self.assertLess(result["score"], 0.7)


if __name__ == "__main__":
    unittest.main()

