import os
import tempfile
import unittest

from guiagent_v2.blueprint_hub import BlueprintRepository
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


class _ScreenshotMobileExecutor:
    def execute_action(self, action, context=None):  # noqa: ANN001
        del action, context
        return {
            "success": True,
            "execution_mode": "device",
            "device_executed": True,
            "error": None,
            "action_name": "Wait",
            "latency_ms": 0,
            "screenshot_path": "/tmp/mobile-action.png",
            "screenshot_error": None,
            "context": {"screenshot_post": "/tmp/post-live.jpg"},
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

    def test_infer_probe_action_back(self):
        action, context = infer_probe_action("执行返回操作，然后等待")
        self.assertEqual(action["name"], "Back")
        self.assertFalse(context["is_web_subtask"])
        self.assertEqual(context["task_type"], "mobile")

    def test_infer_probe_action_home(self):
        action, context = infer_probe_action("回到桌面，然后等待")
        self.assertEqual(action["name"], "Home")
        self.assertFalse(context["is_web_subtask"])
        self.assertEqual(context["task_type"], "mobile")

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
        self.assertIn("adapter_call", event_types)
        self.assertEqual(len(web_skill.calls), 0)

    def test_run_probe_handover_when_page_hint_mismatch(self):
        events = []
        web_skill = _FakeWebSkill(success=True)

        result = run_probe_step(
            instruction="在手机里等待一下",
            run_id="r-page-mismatch",
            task_id="t-page-mismatch",
            session_id="sess-page-mismatch",
            step_id=1,
            chain_mode="guiagent_v2",
            emit_event=events.append,
            hooks=_build_hooks(),
            router=WebSkillRouter(),
            guard_policy=GuardPolicy(),
            web_skill=web_skill,
            page_hint="微信会话页",
        )

        self.assertEqual(result.status, "HANDOVER")
        gate_events = [e for e in events if e.get("event_type") == "page_hint_gate"]
        self.assertTrue(gate_events)
        self.assertEqual(gate_events[-1].get("status"), "HANDOVER")
        self.assertLess(float(gate_events[-1].get("fingerprint_match_score", 1.0)), 0.55)
        self.assertLess(float(gate_events[-1].get("page_fingerprint_score", 1.0)), 0.55)
        handovers = [e for e in events if e.get("event_type") == "handover"]
        self.assertTrue(handovers)
        self.assertEqual(handovers[-1].get("reason_code"), "PAGE_HINT_MISMATCH")

    def test_run_probe_allows_when_page_hint_matches(self):
        events = []
        web_skill = _FakeWebSkill(success=True)

        def _perception_provider():
            return {
                "perception_infos": [{"text": "微信会话", "coordinates": [100, 120]}],
                "screen_width": 1080,
                "screen_height": 2340,
                "keyboard": False,
            }

        result = run_probe_step(
            instruction="在手机里等待一下",
            run_id="r-page-match",
            task_id="t-page-match",
            session_id="sess-page-match",
            step_id=1,
            chain_mode="guiagent_v2",
            emit_event=events.append,
            hooks=_build_hooks(),
            router=WebSkillRouter(),
            guard_policy=GuardPolicy(),
            web_skill=web_skill,
            page_hint="微信会话",
            perception_provider=_perception_provider,
        )

        self.assertIn(result.status, {"SUCCESS", "HANDOVER"})
        gate_events = [e for e in events if e.get("event_type") == "page_hint_gate"]
        self.assertTrue(gate_events)
        self.assertEqual(gate_events[-1].get("status"), "SUCCESS")
        self.assertGreaterEqual(float(gate_events[-1].get("fingerprint_match_score", 0.0)), 0.55)
        self.assertGreaterEqual(float(gate_events[-1].get("page_fingerprint_score", 0.0)), 0.55)

    def test_run_probe_handover_when_page_fingerprint_id_mismatch(self):
        events = []
        web_skill = _FakeWebSkill(success=True)

        def _perception_provider():
            return {
                "perception_infos": [{"text": "微信会话", "coordinates": [100, 120]}],
                "screen_width": 1080,
                "screen_height": 2340,
                "keyboard": False,
            }

        result = run_probe_step(
            instruction="在手机里等待一下",
            run_id="r-pfid-mismatch",
            task_id="t-pfid-mismatch",
            session_id="sess-pfid-mismatch",
            step_id=2,
            chain_mode="guiagent_v2",
            emit_event=events.append,
            hooks=_build_hooks(),
            router=WebSkillRouter(),
            guard_policy=GuardPolicy(),
            web_skill=web_skill,
            page_hint="微信会话",
            page_fingerprint_id="pfid:force-mismatch",
            perception_provider=_perception_provider,
        )

        self.assertEqual(result.status, "HANDOVER")
        gate_events = [e for e in events if e.get("event_type") == "page_hint_gate"]
        self.assertTrue(gate_events)
        self.assertFalse(bool(gate_events[-1].get("fingerprint_id_matched", True)))
        handovers = [e for e in events if e.get("event_type") == "handover"]
        self.assertTrue(handovers)
        self.assertEqual(handovers[-1].get("reason_code"), "PAGE_FINGERPRINT_ID_MISMATCH")

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

    def test_run_probe_mobile_adapter_call_includes_screenshot(self):
        events = []
        web_skill = _FakeWebSkill(success=True)
        result = run_probe_step(
            instruction="在手机里等待一下",
            run_id="r-mobile-shot",
            task_id="t-mobile-shot",
            session_id="sess-mobile-shot",
            step_id=12,
            chain_mode="guiagent_v2",
            emit_event=events.append,
            hooks=_build_hooks(),
            router=WebSkillRouter(),
            guard_policy=GuardPolicy(),
            web_skill=web_skill,
            mobile_executor=_ScreenshotMobileExecutor(),
        )
        self.assertEqual(result.status, "SUCCESS")
        adapter_events = [e for e in events if e.get("event_type") == "adapter_call"]
        self.assertTrue(adapter_events)
        self.assertEqual(adapter_events[-1].get("adapter_backend"), "mobile-device")
        self.assertEqual(adapter_events[-1].get("screenshot_path"), "/tmp/mobile-action.png")
        step_end = [e for e in events if e.get("event_type") == "step_end"][-1]
        self.assertEqual(step_end.get("action_screenshot"), "/tmp/mobile-action.png")
        self.assertEqual(step_end.get("screenshot_post"), "/tmp/post-live.jpg")

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

    def test_run_probe_emits_snapshot_events_with_paths(self):
        events = []
        web_skill = _FakeWebSkill(success=True)
        calls = {"count": 0}

        def _perception_provider(**kwargs):  # noqa: ANN003
            calls["count"] += 1
            role = str(kwargs.get("snapshot_role", ""))
            return {
                "perception_infos": [{"text": f"{role}-marker", "coordinates": [1, 1]}],
                "screen_width": 720,
                "screen_height": 1280,
                "keyboard": False,
                "screenshot_path": f"/tmp/{role}-{calls['count']}.jpg",
                "snapshot_seq": calls["count"],
            }

        result = run_probe_step(
            instruction="在手机里等待一下",
            run_id="r-snap",
            task_id="t-snap",
            session_id="sess-snap",
            step_id=11,
            chain_mode="guiagent_v2",
            emit_event=events.append,
            hooks=_build_post_snapshot_hooks(),
            router=WebSkillRouter(),
            guard_policy=GuardPolicy(),
            web_skill=web_skill,
            perception_provider=_perception_provider,
        )

        self.assertEqual(result.status, "SUCCESS")
        snapshot_events = [e for e in events if e.get("event_type") == "snapshot_captured"]
        self.assertGreaterEqual(len(snapshot_events), 2)
        self.assertTrue(all(str(e.get("snapshot_path", "")).startswith("/tmp/") for e in snapshot_events))
        step_end = [e for e in events if e.get("event_type") == "step_end"][-1]
        self.assertTrue(str(step_end.get("screenshot_pre", "")).startswith("/tmp/pre"))
        self.assertTrue(str(step_end.get("screenshot_post", "")).startswith("/tmp/post"))

    def test_run_probe_syncs_blueprint_after_mobile_step(self):
        events = []
        web_skill = _FakeWebSkill(success=True)
        calls = {"count": 0}

        def _perception_provider():
            calls["count"] += 1
            if calls["count"] == 1:
                return {
                    "perception_infos": [{"text": "Home", "coordinates": [120, 80]}],
                    "screen_width": 1080,
                    "screen_height": 2340,
                }
            return {
                "perception_infos": [{"text": "Search", "coordinates": [520, 120]}],
                "screen_width": 1080,
                "screen_height": 2340,
            }

        with tempfile.TemporaryDirectory() as td:
            repo = BlueprintRepository(os.path.join(td, "blueprints.json"))
            result = run_probe_step(
                instruction="在手机里等待一下",
                run_id="r-blueprint",
                task_id="t-blueprint",
                session_id="sess-blueprint",
                step_id=7,
                chain_mode="guiagent_v2",
                emit_event=events.append,
                hooks=_build_hooks(),
                router=WebSkillRouter(),
                guard_policy=GuardPolicy(),
                web_skill=web_skill,
                perception_provider=_perception_provider,
                blueprint_repo=repo,
            )

            self.assertEqual(result.status, "SUCCESS")
            saved = repo.get_blueprint(result.intent_key, app_state="global:DEFAULT")
            self.assertIsNotNone(saved)
            self.assertTrue(saved.get("anchors"))

        blueprint_events = [e for e in events if e.get("event_type") == "blueprint_sync"]
        self.assertTrue(blueprint_events)
        self.assertEqual(blueprint_events[-1].get("status"), "SUCCESS")
        self.assertIn("replay_gate_passed", blueprint_events[-1])
        self.assertIn("replay_quality_score", blueprint_events[-1])
        self.assertTrue(str(blueprint_events[-1].get("blueprint_sync_mode", "")).strip())
        self.assertIn("replay_gate_enabled_cfg", blueprint_events[-1])
        self.assertIn("replay_gate_min_score_cfg", blueprint_events[-1])

    def test_run_probe_fast_match_uses_vector_fallback(self):
        events = []
        web_skill = _FakeWebSkill(success=True)

        def _perception_provider():
            return {
                "perception_infos": [{"text": "入口", "coordinates": [80, 80]}],
                "screen_width": 1080,
                "screen_height": 2340,
            }

        with tempfile.TemporaryDirectory() as td:
            repo = BlueprintRepository(os.path.join(td, "blueprints.json"))
            repo.save_blueprint(
                {
                    "intent_key": "global:CHECKOUT:CTA",
                    "app_state": "global:DEFAULT",
                    "version": "v0.1.0",
                    "reference_screen": {"width": 1080, "height": 2340},
                    "anchors": [{"text": "checkout", "coordinates": [600, 2000]}],
                    "post_expectations": [],
                    "metadata": {},
                }
            )
            result = run_probe_step(
                instruction="请等待并进入 checkout 页面",
                run_id="r-fastmatch",
                task_id="t-fastmatch",
                session_id="sess-fastmatch",
                step_id=8,
                chain_mode="guiagent_v2",
                emit_event=events.append,
                hooks=_build_hooks(),
                router=WebSkillRouter(),
                guard_policy=GuardPolicy(),
                web_skill=web_skill,
                perception_provider=_perception_provider,
                blueprint_repo=repo,
            )

        self.assertIn(result.status, {"SUCCESS", "HANDOVER"})
        assertion_events = [e for e in events if e.get("event_type") == "assertion"]
        self.assertTrue(assertion_events)
        hint = assertion_events[-1].get("fast_match_hint", {})
        self.assertEqual(hint.get("matched_intent_key"), "global:CHECKOUT:CTA")
        self.assertIn(hint.get("match_source"), {"vector", "fused"})

    def test_run_probe_emits_topology_projection_when_blueprint_exists(self):
        events = []
        web_skill = _FakeWebSkill(success=True)

        def _perception_provider():
            return {
                "perception_infos": [
                    {"text": "Search", "coordinates": [120, 80]},
                    {"text": "Home", "coordinates": [100, 2200]},
                ],
                "screen_width": 1080,
                "screen_height": 2340,
            }

        with tempfile.TemporaryDirectory() as td:
            repo = BlueprintRepository(os.path.join(td, "blueprints.json"))
            repo.save_blueprint(
                {
                    "intent_key": "global:WAIT:UNSPECIFIED_TARGET",
                    "app_state": "global:DEFAULT",
                    "version": "v0.1.0",
                    "reference_screen": {"width": 1080, "height": 2340},
                    "anchors": [
                        {
                            "id": "a1",
                            "text": "Search",
                            "role": "CORE",
                            "zone": "top",
                            "norm_bbox": {"x": 120 / 1080, "y": 80 / 2340, "w": 0.0, "h": 0.0},
                        },
                        {
                            "id": "a2",
                            "text": "Home",
                            "role": "CORE",
                            "zone": "bottom",
                            "norm_bbox": {"x": 100 / 1080, "y": 2200 / 2340, "w": 0.0, "h": 0.0},
                        },
                    ],
                    "post_expectations": [],
                    "metadata": {},
                }
            )
            run_probe_step(
                instruction="在手机里等待一下",
                run_id="r-topology",
                task_id="t-topology",
                session_id="sess-topology",
                step_id=9,
                chain_mode="guiagent_v2",
                emit_event=events.append,
                hooks=_build_hooks(),
                router=WebSkillRouter(),
                guard_policy=GuardPolicy(),
                web_skill=web_skill,
                perception_provider=_perception_provider,
                blueprint_repo=repo,
            )
        topology_events = [e for e in events if e.get("event_type") == "topology_projection"]
        self.assertTrue(topology_events)
        self.assertIn(topology_events[-1].get("transform_mode"), {"identity", "scale_translate", "affine6"})
        self.assertIn(topology_events[-1].get("projection_mode"), {"affine_norm", "scale"})
        self.assertTrue(str(topology_events[-1].get("projection_guard_reason", "")).strip())

    def test_run_probe_topology_projection_guard_blocks_bad_affine(self):
        events = []
        web_skill = _FakeWebSkill(success=True)

        def _perception_provider():
            return {
                "perception_infos": [
                    {"text": "Search", "coordinates": [80, 60]},
                    {"text": "Home", "coordinates": [900, 2200]},
                ],
                "screen_width": 1080,
                "screen_height": 2340,
            }

        with tempfile.TemporaryDirectory() as td:
            repo = BlueprintRepository(os.path.join(td, "blueprints.json"))
            repo.save_blueprint(
                {
                    "intent_key": "global:WAIT:UNSPECIFIED_TARGET",
                    "app_state": "global:DEFAULT",
                    "version": "v0.1.0",
                    "reference_screen": {"width": 1080, "height": 2340},
                    "anchors": [
                        {
                            "id": "a1",
                            "text": "Search",
                            "role": "CORE",
                            "zone": "top",
                            "norm_bbox": {"x": 0.9, "y": 0.9, "w": 0.0, "h": 0.0},
                        },
                        {
                            "id": "a2",
                            "text": "Home",
                            "role": "CORE",
                            "zone": "bottom",
                            "norm_bbox": {"x": 0.1, "y": 0.1, "w": 0.0, "h": 0.0},
                        },
                    ],
                    "post_expectations": [],
                    "metadata": {},
                }
            )
            run_probe_step(
                instruction="在手机里等待一下",
                run_id="r-topology-block",
                task_id="t-topology-block",
                session_id="sess-topology-block",
                step_id=10,
                chain_mode="guiagent_v2",
                emit_event=events.append,
                hooks=_build_hooks(),
                router=WebSkillRouter(),
                guard_policy=GuardPolicy(),
                web_skill=web_skill,
                perception_provider=_perception_provider,
                blueprint_repo=repo,
            )
        topology_events = [e for e in events if e.get("event_type") == "topology_projection"]
        self.assertTrue(topology_events)
        last = topology_events[-1]
        self.assertEqual(last.get("projection_mode"), "scale")
        self.assertIn(
            last.get("projection_guard_reason"),
            {"INSUFFICIENT_ANCHOR_PAIRS", "AFFINE_FIT_ERROR_HIGH", "CORE_CONFIDENCE_LOW", "NO_AFFINE_TRANSFORM"},
        )


if __name__ == "__main__":
    unittest.main()
