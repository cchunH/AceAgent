import unittest

from guiagent_v2.runtime.default_hooks import post_state_check_hook, semantic_pre_assertion_hook
from guiagent_v2.runtime.guard_policy import GuardPolicy
from guiagent_v2.runtime.hooks import HookManager
from guiagent_v2.runtime.v2_executor import infer_probe_action, run_probe_step
from guiagent_v2.runtime.web_skill_router import WebSkillRouter


class _FakeWebSkill:
    def __init__(self, success=True, error=None):
        self.success = success
        self.error = error
        self.calls = []

    def invoke(self, task, session=None, constraints=None):
        self.calls.append(
            {
                "task": task,
                "session": session,
                "constraints": constraints,
            }
        )
        return {
            "success": self.success,
            "result": {"task": task},
            "trace": [],
            "error": self.error,
            "raw": {},
        }


def _build_hooks():
    hooks = HookManager()
    hooks.register_pre_assertion_hook(semantic_pre_assertion_hook)
    hooks.register_post_check_hook(post_state_check_hook)
    return hooks


class TestV2Executor(unittest.TestCase):
    def test_infer_probe_action_url(self):
        action, context = infer_probe_action("请打开 https://example.com")
        self.assertEqual(action["name"], "web_open")
        self.assertTrue(context["is_web_subtask"])
        self.assertEqual(context["web_task"]["action"], "open")

    def test_run_probe_mobile_path(self):
        events = []
        web_skill = _FakeWebSkill(success=True)

        result = run_probe_step(
            instruction="在手机里等待一下",
            run_id="r1",
            task_id="t1",
            step_id=1,
            chain_mode="guiagent_v2_shadow",
            emit_event=events.append,
            hooks=_build_hooks(),
            router=WebSkillRouter(),
            guard_policy=GuardPolicy(),
            web_skill=web_skill,
        )

        self.assertEqual(result.channel, "mobile_native")
        self.assertEqual(result.status, "SUCCESS")
        event_types = [e["event_type"] for e in events]
        self.assertIn("guard_decision", event_types)
        self.assertNotIn("adapter_call", event_types)
        self.assertEqual(len(web_skill.calls), 0)

    def test_run_probe_web_success(self):
        events = []
        web_skill = _FakeWebSkill(success=True)

        result = run_probe_step(
            instruction="open https://example.com",
            run_id="r2",
            task_id="t2",
            step_id=1,
            chain_mode="guiagent_v2",
            emit_event=events.append,
            hooks=_build_hooks(),
            router=WebSkillRouter(),
            guard_policy=GuardPolicy(),
            web_skill=web_skill,
        )

        self.assertEqual(result.channel, "web_skill")
        self.assertEqual(result.status, "SUCCESS")
        event_types = [e["event_type"] for e in events]
        self.assertIn("adapter_call", event_types)
        self.assertNotIn("skill_fallback", event_types)

    def test_run_probe_web_failed_then_fallback(self):
        events = []
        web_skill = _FakeWebSkill(success=False, error="CLI_NOT_FOUND")

        result = run_probe_step(
            instruction="open https://example.com",
            run_id="r3",
            task_id="t3",
            step_id=1,
            chain_mode="guiagent_v2",
            emit_event=events.append,
            hooks=_build_hooks(),
            router=WebSkillRouter(),
            guard_policy=GuardPolicy(),
            web_skill=web_skill,
        )

        self.assertEqual(result.channel, "mobile_native")
        self.assertEqual(result.route_reason, "skill_fallback_to_mobile_native")
        event_types = [e["event_type"] for e in events]
        self.assertIn("adapter_call", event_types)
        self.assertIn("skill_fallback", event_types)
        self.assertIn("step_end", event_types)


if __name__ == "__main__":
    unittest.main()
