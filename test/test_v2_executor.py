import unittest

from guiagent_v2.runtime.context_compaction import ContextCompactor
from guiagent_v2.runtime.default_hooks import post_state_check_hook, semantic_pre_assertion_hook
from guiagent_v2.runtime.guard_policy import GuardPolicy
from guiagent_v2.runtime.hooks import HookManager
from guiagent_v2.runtime.loop_detector import LoopDetector
from guiagent_v2.runtime.v2_executor import infer_probe_action, run_probe_step
from guiagent_v2.runtime.web_skill_router import WebSkillRouter


class _FakeWebSkill:
    def __init__(self, success=True, error=None, success_sequence=None, error_sequence=None):
        self.success = success
        self.error = error
        self.success_sequence = list(success_sequence) if success_sequence is not None else None
        self.error_sequence = list(error_sequence) if error_sequence is not None else None
        self.calls = []

    def invoke(self, task, session=None, constraints=None):
        self.calls.append(
            {
                "task": task,
                "session": session,
                "constraints": constraints,
            }
        )
        idx = len(self.calls) - 1
        success = self.success
        error = self.error
        if self.success_sequence is not None and idx < len(self.success_sequence):
            success = bool(self.success_sequence[idx])
        if self.error_sequence is not None and idx < len(self.error_sequence):
            error = self.error_sequence[idx]
        return {
            "success": success,
            "result": {"task": task},
            "trace": [],
            "error": error,
            "raw": {},
        }


class _ConfirmGuardPolicy:
    def decide(self, intent_key, action, context):  # noqa: ANN001
        del intent_key, action, context
        return {
            "decision": "confirm",
            "reason": "HIGH_RISK_INTENT",
            "category": "risk_control",
            "policy_source": "ut",
            "policy_version": "v1",
        }


class _FailingMobileExecutor:
    def execute_action(self, action, context=None):  # noqa: ANN001
        del action, context
        return {
            "success": False,
            "execution_mode": "device",
            "device_executed": False,
            "error": "DEVICE_EXEC_ERROR_UT",
            "action_name": "Wait",
            "latency_ms": 0,
        }


def _build_hooks():
    hooks = HookManager()
    hooks.register_pre_assertion_hook(semantic_pre_assertion_hook)
    hooks.register_post_check_hook(post_state_check_hook)
    return hooks


def _build_low_core_hooks():
    hooks = HookManager()

    def _pre(req, ctx):  # noqa: ANN001
        del req, ctx
        return {
            "passed": True,
            "reason_code": "OK",
            "core_anchor_confidence": 0.2,
            "aux_anchor_confidence": 0.9,
            "geometry_confidence": 0.8,
        }

    def _post(req, ctx):  # noqa: ANN001
        del req, ctx
        return {"passed": True, "reason_code": "STATE_TRANSITION_OK"}

    hooks.register_pre_assertion_hook(_pre)
    hooks.register_post_check_hook(_post)
    return hooks


def _build_post_snapshot_hooks():
    hooks = HookManager()

    def _pre(req, ctx):  # noqa: ANN001
        del req, ctx
        return {"passed": True, "reason_code": "OK"}

    def _post(req, ctx):  # noqa: ANN001
        del req
        infos = list(ctx.get("perception_infos_post", []))
        texts = [str(item.get("text", "")) for item in infos if isinstance(item, dict)]
        passed = any("post-marker" in text for text in texts)
        return {
            "passed": passed,
            "reason_code": "STATE_TRANSITION_OK" if passed else "POST_SNAPSHOT_MISSING",
        }

    hooks.register_pre_assertion_hook(_pre)
    hooks.register_post_check_hook(_post)
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
            session_id="sess-mobile",
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
        self.assertIn("executor_state", event_types)
        self.assertNotIn("adapter_call", event_types)
        self.assertEqual(len(web_skill.calls), 0)

    def test_run_probe_web_success(self):
        events = []
        web_skill = _FakeWebSkill(success=True)

        result = run_probe_step(
            instruction="open https://example.com",
            run_id="r2",
            task_id="t2",
            session_id="sess-web",
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
        self.assertIn("web_plan", event_types)
        self.assertIn("web_step_start", event_types)
        self.assertIn("web_step_end", event_types)
        self.assertIn("adapter_call", event_types)
        self.assertNotIn("skill_fallback", event_types)
        self.assertGreaterEqual(len(web_skill.calls), 2)
        adapter_events = [item for item in events if item.get("event_type") == "adapter_call"]
        self.assertTrue(adapter_events)
        self.assertTrue(all(str(item.get("web_trace_id", "")).strip() for item in adapter_events))
        self.assertTrue(all(str(item.get("web_plan_id", "")).strip() for item in adapter_events))

    def test_run_probe_web_failed_then_fallback(self):
        events = []
        web_skill = _FakeWebSkill(
            success=True,
            success_sequence=[True, False],
            error_sequence=[None, "CLI_NOT_FOUND"],
        )

        result = run_probe_step(
            instruction="open https://example.com",
            run_id="r3",
            task_id="t3",
            session_id="sess-web-fallback",
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
        self.assertIn("web_step_end", event_types)
        self.assertIn("fallback_action_selected", event_types)
        self.assertIn("web_replan_skipped", event_types)
        self.assertNotIn("web_replan", event_types)
        self.assertEqual(len(web_skill.calls), 2)
        skipped_events = [item for item in events if item.get("event_type") == "web_replan_skipped"]
        self.assertEqual(skipped_events[-1].get("web_replan_strategy"), "backend_unavailable")
        fallback_events = [item for item in events if item.get("event_type") == "fallback_action_selected"]
        self.assertEqual(fallback_events[-1].get("fallback_action", {}).get("name"), "Back")

    def test_run_probe_web_replan_then_recover(self):
        events = []
        web_skill = _FakeWebSkill(
            success=True,
            success_sequence=[False, True, True],
            error_sequence=["CLI_TIMEOUT", None, None],
        )

        result = run_probe_step(
            instruction="open https://example.com",
            run_id="r3r",
            task_id="t3r",
            session_id="sess-web-replan",
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
        self.assertIn("web_replan", event_types)
        self.assertNotIn("skill_fallback", event_types)

    def test_run_probe_web_supports_multiple_replans(self):
        events = []
        web_skill = _FakeWebSkill(
            success=True,
            success_sequence=[False, False, True, True, True],
            error_sequence=["CLI_TIMEOUT", "SELECTOR_NOT_FOUND", None, None, None],
        )

        result = run_probe_step(
            instruction="open https://example.com",
            run_id="r3m",
            task_id="t3m",
            session_id="sess-web-replan-multi",
            step_id=1,
            chain_mode="guiagent_v2",
            emit_event=events.append,
            hooks=_build_hooks(),
            router=WebSkillRouter(),
            guard_policy=GuardPolicy(),
            web_skill=web_skill,
            web_max_steps=5,
            web_replan_max_attempts=2,
        )

        self.assertEqual(result.status, "SUCCESS")
        replan_events = [e for e in events if e.get("event_type") == "web_replan"]
        self.assertGreaterEqual(len(replan_events), 2)
        self.assertEqual(replan_events[0].get("web_replan_strategy"), "timeout_wait_then_snapshot")
        self.assertEqual(replan_events[1].get("web_replan_strategy"), "selector_refresh_snapshot")

    def test_run_probe_emits_loop_warning_when_repeated(self):
        events = []
        web_skill = _FakeWebSkill(success=True)
        detector = LoopDetector(repeat_threshold=2, stagnation_threshold=99)
        fp = detector.build_page_fingerprint([{"text": "__probe_pre__", "coordinates": (1, 1)}])
        detector.observe({"name": "Wait", "arguments": {}}, page_fingerprint=fp)

        run_probe_step(
            instruction="在手机里等待一下",
            run_id="r4",
            task_id="t4",
            session_id="sess-loop",
            step_id=1,
            chain_mode="guiagent_v2_shadow",
            emit_event=events.append,
            hooks=_build_hooks(),
            router=WebSkillRouter(),
            guard_policy=GuardPolicy(),
            web_skill=web_skill,
            loop_detector=detector,
        )
        event_types = [e["event_type"] for e in events]
        self.assertIn("loop_warning", event_types)

    def test_run_probe_emits_context_compaction(self):
        events = []
        web_skill = _FakeWebSkill(success=True)

        run_probe_step(
            instruction="open https://example.com",
            run_id="r5",
            task_id="t5",
            session_id="sess-compact",
            step_id=1,
            chain_mode="guiagent_v2",
            emit_event=events.append,
            hooks=_build_hooks(),
            router=WebSkillRouter(),
            guard_policy=GuardPolicy(),
            web_skill=web_skill,
            context_compactor=ContextCompactor(max_events=3, keep_recent=1),
        )
        event_types = [e["event_type"] for e in events]
        self.assertIn("context_compaction", event_types)

    def test_run_probe_propagates_runtime_session_id(self):
        events = []
        web_skill = _FakeWebSkill(success=True)

        run_probe_step(
            instruction="open https://example.com",
            run_id="r6",
            task_id="t6",
            session_id="sess-route-1",
            step_id=1,
            chain_mode="guiagent_v2",
            emit_event=events.append,
            hooks=_build_hooks(),
            router=WebSkillRouter(),
            guard_policy=GuardPolicy(),
            web_skill=web_skill,
        )

        self.assertTrue(events)
        self.assertTrue(all(e.get("session_id") == "sess-route-1" for e in events))
        self.assertEqual(web_skill.calls[0]["session"]["session_id"], "sess-route-1")

    def test_run_probe_confirm_approved_then_continue(self):
        events = []
        web_skill = _FakeWebSkill(success=True)
        pending = []

        def _register(payload):
            pending.append(dict(payload))
            return payload

        def _wait(confirm_id, timeout_sec, poll_interval):
            del timeout_sec, poll_interval
            return {
                "confirm_id": confirm_id,
                "decision": "approve",
                "actor": "ops",
                "source": "control-panel",
            }

        result = run_probe_step(
            instruction="在手机里等待一下",
            run_id="r-confirm-ok",
            task_id="t-confirm-ok",
            session_id="sess-confirm-ok",
            step_id=2,
            chain_mode="guiagent_v2",
            emit_event=events.append,
            hooks=_build_hooks(),
            router=WebSkillRouter(),
            guard_policy=_ConfirmGuardPolicy(),
            web_skill=web_skill,
            confirm_wait_timeout=5.0,
            register_confirmation=_register,
            wait_confirmation=_wait,
        )

        self.assertEqual(result.status, "SUCCESS")
        self.assertTrue(pending)
        event_types = [e["event_type"] for e in events]
        self.assertIn("pending_confirm", event_types)
        self.assertIn("confirm_approved", event_types)
        self.assertNotIn("handover", event_types)

    def test_run_probe_confirm_rejected_handover(self):
        events = []
        web_skill = _FakeWebSkill(success=True)

        result = run_probe_step(
            instruction="在手机里等待一下",
            run_id="r-confirm-no",
            task_id="t-confirm-no",
            session_id="sess-confirm-no",
            step_id=3,
            chain_mode="guiagent_v2",
            emit_event=events.append,
            hooks=_build_hooks(),
            router=WebSkillRouter(),
            guard_policy=_ConfirmGuardPolicy(),
            web_skill=web_skill,
            confirm_wait_timeout=5.0,
            register_confirmation=lambda payload: payload,
            wait_confirmation=lambda confirm_id, timeout_sec, poll_interval: {
                "confirm_id": confirm_id,
                "decision": "reject",
                "actor": "ops",
            },
        )

        self.assertEqual(result.status, "HANDOVER")
        event_types = [e["event_type"] for e in events]
        self.assertIn("pending_confirm", event_types)
        self.assertIn("confirm_rejected", event_types)
        self.assertIn("handover", event_types)

    def test_run_probe_blocks_when_core_anchor_confidence_low(self):
        events = []
        web_skill = _FakeWebSkill(success=True)

        result = run_probe_step(
            instruction="在手机里等待一下",
            run_id="r-core-low",
            task_id="t-core-low",
            session_id="sess-core-low",
            step_id=4,
            chain_mode="guiagent_v2",
            emit_event=events.append,
            hooks=_build_low_core_hooks(),
            router=WebSkillRouter(),
            guard_policy=GuardPolicy(),
            web_skill=web_skill,
        )

        self.assertEqual(result.status, "HANDOVER")
        event_types = [e["event_type"] for e in events]
        self.assertIn("anchor_gate", event_types)
        handovers = [e for e in events if e.get("event_type") == "handover"]
        self.assertTrue(handovers)
        self.assertEqual(handovers[-1].get("reason_code"), "CORE_ANCHOR_CONFIDENCE_LOW")

    def test_run_probe_handover_when_mobile_device_exec_fails(self):
        events = []
        web_skill = _FakeWebSkill(success=True)

        result = run_probe_step(
            instruction="在手机里等待一下",
            run_id="r-mobile-fail",
            task_id="t-mobile-fail",
            session_id="sess-mobile-fail",
            step_id=5,
            chain_mode="guiagent_v2",
            emit_event=events.append,
            hooks=_build_hooks(),
            router=WebSkillRouter(),
            guard_policy=GuardPolicy(),
            web_skill=web_skill,
            mobile_executor=_FailingMobileExecutor(),
        )

        self.assertEqual(result.status, "HANDOVER")
        handovers = [e for e in events if e.get("event_type") == "handover"]
        self.assertTrue(handovers)
        self.assertEqual(handovers[-1].get("reason_code"), "DEVICE_EXEC_ERROR_UT")

    def test_run_probe_uses_perception_provider_for_pre_post_snapshot(self):
        events = []
        web_skill = _FakeWebSkill(success=True)
        calls = {"count": 0}

        def _perception_provider():
            calls["count"] += 1
            if calls["count"] == 1:
                return {
                    "perception_infos": [{"text": "pre-marker", "coordinates": [1, 1]}],
                    "screen_width": 720,
                    "screen_height": 1280,
                    "keyboard": False,
                }
            return {
                "perception_infos": [{"text": "post-marker", "coordinates": [2, 2]}],
                "screen_width": 720,
                "screen_height": 1280,
                "keyboard": False,
            }

        result = run_probe_step(
            instruction="在手机里等待一下",
            run_id="r-perception",
            task_id="t-perception",
            session_id="sess-perception",
            step_id=6,
            chain_mode="guiagent_v2",
            emit_event=events.append,
            hooks=_build_post_snapshot_hooks(),
            router=WebSkillRouter(),
            guard_policy=GuardPolicy(),
            web_skill=web_skill,
            perception_provider=_perception_provider,
        )

        self.assertEqual(result.status, "SUCCESS")
        self.assertGreaterEqual(calls["count"], 2)


if __name__ == "__main__":
    unittest.main()
