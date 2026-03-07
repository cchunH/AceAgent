import unittest

from guiagent_v2.runtime.context_compaction import ContextCompactor


class TestContextCompaction(unittest.TestCase):
    def test_no_compaction_when_under_threshold(self):
        compactor = ContextCompactor(max_events=5, keep_recent=2)
        events = [{"event_type": "step_start"}, {"event_type": "skill_route"}]
        result = compactor.compact(events)

        self.assertFalse(result["applied"])
        self.assertEqual(result["before_count"], 2)
        self.assertEqual(result["after_count"], 2)

    def test_compaction_applied(self):
        compactor = ContextCompactor(max_events=5, keep_recent=2)
        events = [
            {"event_type": "step_start"},
            {"event_type": "skill_route"},
            {"event_type": "guard_decision"},
            {"event_type": "action_exec"},
            {"event_type": "post_check"},
            {"event_type": "step_end"},
        ]
        result = compactor.compact(events)

        self.assertTrue(result["applied"])
        self.assertEqual(result["before_count"], 6)
        self.assertEqual(result["after_count"], 3)
        self.assertEqual(result["truncated_count"], 3)
        self.assertIn("event_type_counts", result["summary"])


if __name__ == "__main__":
    unittest.main()
