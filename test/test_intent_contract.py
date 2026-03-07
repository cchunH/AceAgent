import unittest

from guiagent_v2.intent_contract import (
    build_intent_key,
    map_legacy_action_to_request,
    map_legacy_outcome_to_result,
)


class TestIntentContract(unittest.TestCase):
    def test_build_intent_key(self):
        self.assertEqual(
            build_intent_key("global", "TAP", "SEARCH_BAR"),
            "global:TAP:SEARCH_BAR",
        )

    def test_map_legacy_action_to_request(self):
        req = map_legacy_action_to_request(
            {"name": "Tap", "arguments": {"x": 100, "y": 200}},
            context={"object": "SEARCH_BAR"},
        )
        self.assertEqual(req.intent_key, "global:TAP:SEARCH_BAR")
        self.assertEqual(req.action["name"], "Tap")
        self.assertEqual(req.action["arguments"]["x"], 100)

    def test_map_legacy_outcome_to_result(self):
        res = map_legacy_outcome_to_result("req-1", "A", latency_ms=12)
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.recovery_level, "NONE")
        self.assertEqual(res.latency_ms, 12)


if __name__ == "__main__":
    unittest.main()

