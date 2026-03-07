import json
import os
import tempfile
import unittest

from guiagent_v2.runtime.metrics import compute_metrics_from_jsonl
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


if __name__ == "__main__":
    unittest.main()
