import unittest

from guiagent_v2.intent_contract import map_legacy_action_to_request
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


if __name__ == "__main__":
    unittest.main()

