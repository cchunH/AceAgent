import unittest

from guiagent_v2.runtime.loop_detector import LoopDetector


class TestLoopDetector(unittest.TestCase):
    def test_repeated_action_triggers_warning(self):
        detector = LoopDetector(repeat_threshold=3, stagnation_threshold=10)
        action = {"name": "Tap", "arguments": {"x": 1, "y": 2}}

        detector.observe(action, page_fingerprint="page-a")
        detector.observe(action, page_fingerprint="page-b")
        state = detector.observe(action, page_fingerprint="page-c")

        self.assertTrue(state["should_warn"])
        self.assertGreaterEqual(state["repeated_action_count"], 3)

    def test_stagnation_triggers_warning(self):
        detector = LoopDetector(repeat_threshold=10, stagnation_threshold=3)
        action1 = {"name": "Tap", "arguments": {"x": 1, "y": 2}}
        action2 = {"name": "Swipe", "arguments": {"x1": 1, "y1": 1, "x2": 1, "y2": 2}}

        detector.observe(action1, page_fingerprint="same")
        detector.observe(action2, page_fingerprint="same")
        state = detector.observe(action1, page_fingerprint="same")

        self.assertTrue(state["should_warn"])
        self.assertGreaterEqual(state["stagnation_steps"], 3)


if __name__ == "__main__":
    unittest.main()
