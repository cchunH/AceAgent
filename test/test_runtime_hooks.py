import unittest

from guiagent_v2.intent_contract import map_legacy_action_to_request
from guiagent_v2.runtime.default_hooks import (
    post_state_check_hook,
    semantic_pre_assertion_hook,
)
from guiagent_v2.runtime.hooks import HookManager


class TestRuntimeHooks(unittest.TestCase):
    def test_hook_order(self):
        manager = HookManager()
        calls = []

        def pre_hook(req, ctx):
            calls.append(("pre", req.intent_key))
            return {"passed": True, "reason_code": "OK"}

        def post_hook(req, ctx):
            calls.append(("post", req.intent_key))
            return {"passed": True, "reason_code": "STATE_TRANSITION_OK"}

        manager.register_pre_assertion_hook(pre_hook)
        manager.register_post_check_hook(post_hook)

        req = map_legacy_action_to_request({"name": "Wait", "arguments": {}})
        pre_result = manager.run_pre_assertion(req, {})
        post_result = manager.run_post_check(req, {})

        self.assertTrue(pre_result["passed"])
        self.assertTrue(post_result["passed"])
        self.assertEqual(calls[0][0], "pre")
        self.assertEqual(calls[1][0], "post")

    def test_semantic_pre_assertion_hook(self):
        req = map_legacy_action_to_request(
            {"name": "Type", "arguments": {"text": "coffee"}},
            context={"expected_semantics": ["coffee"]},
        )
        context = {
            "perception_infos_pre": [
                {"text": "Search coffee", "coordinates": (120, 88)},
            ],
        }
        result = semantic_pre_assertion_hook(req, context)
        self.assertTrue(result["passed"])

    def test_post_state_check_hook(self):
        req = map_legacy_action_to_request({"name": "Tap", "arguments": {"x": 1, "y": 2}})
        context = {
            "perception_infos_pre": [
                {"text": "Home", "coordinates": (20, 20)},
            ],
            "perception_infos_post": [
                {"text": "Search Page", "coordinates": (20, 20)},
            ],
        }
        result = post_state_check_hook(req, context)
        self.assertTrue(result["passed"])


if __name__ == "__main__":
    unittest.main()
