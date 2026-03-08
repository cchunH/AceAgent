import json
import os
import tempfile
import unittest

from guiagent_v2.runtime.metrics import (
    compute_metrics_from_events,
    compute_metrics_from_jsonl,
    compute_timeseries_from_events,
)
from guiagent_v2.runtime.orchestrator_v2 import (
    _build_hook_manager,
    _emit_events_from_legacy_steps,
    _translate_legacy_step_to_events,
)
from guiagent_v2.runtime.context_compaction import ContextCompactor
from guiagent_v2.runtime.event_bus import JSONLEventBus
from guiagent_v2.runtime.loop_detector import LoopDetector
from guiagent_v2.runtime.web_skill_router import WebSkillRouter


class TestRuntimeMetricsAndTranslation(unittest.TestCase):
    def test_translate_action_emits_route_event(self):
        step = {
            "step": 2,
            "operation": "action",
            "action_object": {"name": "Web_Open", "arguments": {"url": "https://example.com"}},
        }
        context_index = {
            "action_by_step": {},
            "perception_by_step": {},
            "route_by_step": {},
            "screen_size": {"width": 1080, "height": 2340},
        }
        events = _translate_legacy_step_to_events(
            step,
            context_index=context_index,
            hooks=_build_hook_manager(),
            blueprint_repo=None,
            router=WebSkillRouter(),
        )
        self.assertEqual(events[0]["event_type"], "skill_route")
        self.assertEqual(events[0]["channel"], "web_skill")
        self.assertEqual(events[1]["event_type"], "action_exec")
        self.assertEqual(events[1]["channel"], "web_skill")

    def test_translate_action_reflection_failure(self):
        step = {
            "step": 3,
            "operation": "action_reflection",
            "outcome": "B",
            "error_description": "TARGET_NOT_FOUND",
            "action_object": {"name": "Tap", "arguments": {"x": 1, "y": 2}},
            "duration": 0.2,
        }
        context_index = {
            "action_by_step": {
                3: {
                    "action_object": {"name": "Tap", "arguments": {"x": 1, "y": 2}},
                }
            },
            "perception_by_step": {
                3: [{"text": "Home", "coordinates": (1, 1)}],
                4: [{"text": "Error", "coordinates": (1, 1)}],
            },
            "route_by_step": {
                3: {
                    "channel": "web_skill",
                    "route_reason": "web_intent_prefix",
                    "skill_name": "AgentBrowserSkill",
                }
            },
        }
        events = _translate_legacy_step_to_events(
            step,
            context_index=context_index,
            hooks=_build_hook_manager(),
            blueprint_repo=None,
        )
        event_types = [e["event_type"] for e in events]
        self.assertIn("assertion", event_types)
        self.assertIn("post_check", event_types)
        self.assertIn("skill_fallback", event_types)
        self.assertIn("handover", event_types)
        self.assertIn("step_end", event_types)

    def test_translate_action_emits_loop_warning_when_repeated(self):
        step = {
            "step": 2,
            "operation": "action",
            "action_object": {"name": "Tap", "arguments": {"x": 1, "y": 2}},
        }
        context_index = {
            "action_by_step": {},
            "perception_by_step": {
                2: [{"text": "Home", "coordinates": (1, 1)}],
            },
            "route_by_step": {},
            "screen_size": {"width": 1080, "height": 2340},
        }
        detector = LoopDetector(repeat_threshold=2, stagnation_threshold=99)
        detector.observe({"name": "Tap", "arguments": {"x": 1, "y": 2}}, page_fingerprint="same-page")

        events = _translate_legacy_step_to_events(
            step,
            context_index=context_index,
            hooks=_build_hook_manager(),
            blueprint_repo=None,
            router=WebSkillRouter(),
            loop_detector=detector,
        )
        self.assertEqual(events[0]["event_type"], "loop_warning")
        self.assertIn("loop_score", events[0])

    def test_emit_legacy_steps_emits_context_compaction(self):
        with tempfile.TemporaryDirectory() as td:
            steps_path = os.path.join(td, "steps.json")
            steps = [
                {"step": i, "operation": "noop"} for i in range(1, 12)
            ]
            with open(steps_path, "w", encoding="utf-8") as f:
                json.dump(steps, f, ensure_ascii=False)

            event_path = os.path.join(td, "events.jsonl")
            bus = JSONLEventBus(event_path, default_chain_mode="legacy")
            _emit_events_from_legacy_steps(
                bus=bus,
                run_id="run-ut",
                task_id="task-ut",
                chain_mode="legacy",
                log_dir=td,
                router=WebSkillRouter(),
                loop_detector=LoopDetector(),
                context_compactor=ContextCompactor(max_events=4, keep_recent=2),
            )

            with open(event_path, "r", encoding="utf-8") as f:
                rows = [json.loads(line) for line in f if line.strip()]
            event_types = [row.get("event_type") for row in rows]
            self.assertIn("context_compaction", event_types)

    def test_compute_metrics_from_jsonl(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "events.jsonl")
            rows = [
                {
                    "run_id": "r1",
                    "task_id": "t1",
                    "step_id": 1,
                    "chain_mode": "legacy",
                    "event_type": "assertion",
                    "status": "SUCCESS",
                    "intent_key": "global:TAP:SEARCH",
                    "assertion_result": {"passed": True, "reason_code": "OK"},
                },
                {
                    "run_id": "r1",
                    "task_id": "t1",
                    "step_id": 1,
                    "chain_mode": "legacy",
                    "event_type": "step_end",
                    "status": "SUCCESS",
                    "intent_key": "global:TAP:SEARCH",
                    "latency_ms": 100,
                },
                {
                    "run_id": "r1",
                    "task_id": "t1",
                    "step_id": 2,
                    "chain_mode": "legacy",
                    "event_type": "handover",
                    "status": "HANDOVER",
                    "intent_key": "global:TAP:SUBMIT",
                },
                {
                    "run_id": "r1",
                    "task_id": "t1",
                    "step_id": 2,
                    "chain_mode": "legacy",
                    "event_type": "step_end",
                    "status": "HANDOVER",
                    "intent_key": "global:TAP:SUBMIT",
                    "latency_ms": 200,
                },
                {
                    "run_id": "r1",
                    "task_id": "t1",
                    "step_id": 2,
                    "chain_mode": "guiagent_v2",
                    "event_type": "web_plan",
                    "status": "SUCCESS",
                    "intent_key": "web:OPEN:URL",
                },
                {
                    "run_id": "r1",
                    "task_id": "t1",
                    "step_id": 2,
                    "chain_mode": "guiagent_v2",
                    "event_type": "web_replan",
                    "status": "RUNNING",
                    "intent_key": "web:OPEN:URL",
                },
                {
                    "run_id": "r1",
                    "task_id": "t1",
                    "step_id": 2,
                    "chain_mode": "guiagent_v2",
                    "event_type": "web_step_end",
                    "status": "SUCCESS",
                    "intent_key": "web:OPEN:URL",
                    "latency_ms": 80,
                },
                {
                    "run_id": "r1",
                    "task_id": "t1",
                    "step_id": 2,
                    "chain_mode": "guiagent_v2",
                    "event_type": "fallback_action_selected",
                    "status": "SUCCESS",
                    "intent_key": "web:OPEN:URL",
                },
                {
                    "run_id": "r1",
                    "task_id": "t1",
                    "step_id": 999999,
                    "chain_mode": "legacy",
                    "event_type": "task_end",
                    "status": "SUCCESS",
                    "intent_key": "global:TASK:END",
                },
            ]
            with open(p, "w", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

            metrics = compute_metrics_from_jsonl(p)
            self.assertAlmostEqual(metrics["task_success_rate"], 1.0)
            self.assertAlmostEqual(metrics["s2_takeover_rate"], 0.5)
            self.assertEqual(metrics["step_latency_p50_ms"], 150.0)
            self.assertEqual(metrics["web_plan_count"], 1)
            self.assertEqual(metrics["web_replan_count"], 1)
            self.assertEqual(metrics["fallback_action_selected_count"], 1)
            self.assertAlmostEqual(metrics["web_step_success_rate"], 1.0)
            self.assertIn("denoise_stable_ratio_avg", metrics)
            self.assertIn("core_anchor_confidence_avg", metrics)
            self.assertIn("aux_anchor_confidence_avg", metrics)
            self.assertIn("geometry_confidence_avg", metrics)
            self.assertIn("fast_match_hit_rate", metrics)
            self.assertIn("anchor_gate_allow_rate", metrics)
            self.assertIn("anchor_gate_retry_rate", metrics)
            self.assertIn("anchor_micro_retry_recovered_rate", metrics)

    def test_compute_metrics_from_events(self):
        rows = [
            {
                "run_id": "r2",
                "task_id": "t2",
                "step_id": 1,
                "chain_mode": "guiagent_v2",
                "event_type": "web_plan",
                "status": "SUCCESS",
                "intent_key": "web:OPEN:URL",
            },
            {
                "run_id": "r2",
                "task_id": "t2",
                "step_id": 1,
                "chain_mode": "guiagent_v2",
                "event_type": "pending_confirm",
                "status": "BLOCKED",
                "intent_key": "global:PAY:ORDER",
                "confirm_id": "r2:t2:1",
                "policy_decision": "confirm",
            },
            {
                "run_id": "r2",
                "task_id": "t2",
                "step_id": 1,
                "chain_mode": "guiagent_v2",
                "event_type": "confirm_approved",
                "status": "SUCCESS",
                "intent_key": "global:PAY:ORDER",
                "confirm_id": "r2:t2:1",
            },
            {
                "run_id": "r2",
                "task_id": "t2",
                "step_id": 1,
                "chain_mode": "guiagent_v2",
                "event_type": "task_end",
                "status": "FAILED",
                "intent_key": "global:TASK:END",
            },
        ]
        metrics = compute_metrics_from_events(rows)
        self.assertEqual(metrics["web_plan_count"], 1)
        self.assertAlmostEqual(metrics["task_success_rate"], 0.0)
        self.assertEqual(metrics["pending_confirm_count"], 1)
        self.assertEqual(metrics["confirm_approved_count"], 1)
        self.assertIn("skeleton_confidence_p50", metrics)

    def test_compute_metrics_anchor_strategy(self):
        rows = [
            {
                "run_id": "r-anchor",
                "task_id": "t-anchor",
                "step_id": 1,
                "chain_mode": "guiagent_v2",
                "event_type": "anchor_gate",
                "status": "HANDOVER",
                "intent_key": "global:TAP:SEARCH",
                "anchor_gate_decision": "retry",
            },
            {
                "run_id": "r-anchor",
                "task_id": "t-anchor",
                "step_id": 1,
                "chain_mode": "guiagent_v2",
                "event_type": "anchor_micro_retry",
                "status": "RUNNING",
                "intent_key": "global:TAP:SEARCH",
                "anchor_retry_attempt": 1,
            },
            {
                "run_id": "r-anchor",
                "task_id": "t-anchor",
                "step_id": 1,
                "chain_mode": "guiagent_v2",
                "event_type": "anchor_micro_retry",
                "status": "SUCCESS",
                "intent_key": "global:TAP:SEARCH",
                "anchor_retry_attempt": 1,
                "anchor_retry_applied": True,
            },
            {
                "run_id": "r-anchor",
                "task_id": "t-anchor",
                "step_id": 2,
                "chain_mode": "guiagent_v2",
                "event_type": "anchor_gate",
                "status": "HANDOVER",
                "intent_key": "global:TAP:PAY",
                "anchor_gate_decision": "deny",
            },
        ]
        metrics = compute_metrics_from_events(rows)
        self.assertEqual(metrics["counts"]["anchor_gate"], 2)
        self.assertEqual(metrics["counts"]["anchor_gate_retry"], 1)
        self.assertEqual(metrics["counts"]["anchor_gate_deny"], 1)
        self.assertEqual(metrics["counts"]["anchor_micro_retry_result"], 1)
        self.assertEqual(metrics["counts"]["anchor_micro_retry_applied"], 1)
        self.assertAlmostEqual(metrics["anchor_gate_retry_rate"], 0.5)
        self.assertAlmostEqual(metrics["anchor_gate_deny_rate"], 0.5)
        self.assertAlmostEqual(metrics["anchor_micro_retry_applied_rate"], 1.0)
        self.assertAlmostEqual(metrics["anchor_micro_retry_recovered_rate"], 1.0)

    def test_compute_metrics_fast_match_source_breakdown(self):
        rows = [
            {
                "run_id": "r-fast",
                "task_id": "t-fast",
                "step_id": 1,
                "chain_mode": "guiagent_v2",
                "event_type": "assertion",
                "status": "SUCCESS",
                "intent_key": "global:TAP:SEARCH",
                "fast_match_hint": {
                    "matched_intent_key": "global:TAP:SEARCH",
                    "match_source": "vector",
                    "vector_score": 0.82,
                    "signature_hit": False,
                },
            },
            {
                "run_id": "r-fast",
                "task_id": "t-fast",
                "step_id": 2,
                "chain_mode": "guiagent_v2",
                "event_type": "assertion",
                "status": "SUCCESS",
                "intent_key": "global:TAP:SEARCH",
                "fast_match_hint": {
                    "matched_intent_key": "global:TAP:SEARCH",
                    "match_source": "fused",
                    "fused_score": 0.73,
                    "signature_hit": True,
                },
            },
            {
                "run_id": "r-fast",
                "task_id": "t-fast",
                "step_id": 999999,
                "chain_mode": "guiagent_v2",
                "event_type": "task_end",
                "status": "SUCCESS",
                "intent_key": "global:TASK:END",
            },
        ]
        metrics = compute_metrics_from_events(rows)
        self.assertAlmostEqual(metrics["fast_match_hit_rate"], 1.0)
        self.assertAlmostEqual(metrics["fast_match_signature_hit_rate"], 0.5)
        self.assertAlmostEqual(metrics["fast_match_source_vector_rate"], 0.5)
        self.assertAlmostEqual(metrics["fast_match_source_fused_rate"], 0.5)
        self.assertEqual(metrics["counts"]["fast_match_source_vector"], 1)
        self.assertEqual(metrics["counts"]["fast_match_source_fused"], 1)

    def test_compute_timeseries_from_events(self):
        rows = [
            {
                "run_id": "r3",
                "task_id": "t3",
                "event_type": "web_plan",
                "status": "SUCCESS",
                "intent_key": "web:OPEN:URL",
                "ts": "2026-03-08T12:00:01Z",
            },
            {
                "run_id": "r3",
                "task_id": "t3",
                "event_type": "task_end",
                "status": "SUCCESS",
                "intent_key": "global:TASK:END",
                "ts": "2026-03-08T12:00:35Z",
            },
            {
                "run_id": "r3",
                "task_id": "t4",
                "event_type": "task_end",
                "status": "FAILED",
                "intent_key": "global:TASK:END",
                "ts": "2026-03-08T12:01:05Z",
            },
        ]
        payload = compute_timeseries_from_events(rows, bucket_sec=60, max_buckets=10)
        self.assertEqual(payload["bucket_sec"], 60)
        self.assertEqual(len(payload["series"]), 2)
        self.assertEqual(payload["series"][0]["event_count"], 2)
        self.assertEqual(payload["series"][1]["event_count"], 1)
        self.assertAlmostEqual(payload["series"][0]["metrics"]["task_success_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
