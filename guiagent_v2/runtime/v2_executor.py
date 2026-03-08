from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from guiagent_v2.intent_contract import map_legacy_action_to_request
from .action_registry import ActionRegistry
from .agent_browser_skill import AgentBrowserSkill
from .context_compaction import ContextCompactor
from .guard_policy import GuardPolicy
from .hooks import HookManager
from .loop_detector import LoopDetector
from .pipeline import StepPipeline
from .executor_state_machine import ProbeState, ProbeStateMachine
from .web_skill_router import WebSkillRouter
from .web_planner import WebPlanStep, build_initial_web_plan, build_replan_after_failure
from .web_replan_policy import WebReplanPolicy


EventEmitter = Callable[[dict[str, Any]], None]
ConfirmationRegistrar = Callable[[dict[str, Any]], dict[str, Any] | None]
ConfirmationWaiter = Callable[[str, float, float], dict[str, Any] | None]
_URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_WEB_HINTS = (
    "http://",
    "https://",
    "网页",
    "website",
    "browser",
    "web",
    "h5",
)
_CORE_ANCHOR_MIN_CONFIDENCE = 0.45
_AUX_ANCHOR_RETRY_THRESHOLD = 0.35
_ANCHOR_MICRO_RETRY_MAX = 1


@dataclass
class V2ProbeResult:
    status: str
    intent_key: str
    channel: str
    route_reason: str


def _extract_first_url(text: str) -> str | None:
    match = _URL_PATTERN.search(text)
    if match is None:
        return None
    return match.group(0).strip()


def infer_probe_action(instruction: str) -> tuple[dict[str, Any], dict[str, Any]]:
    text = str(instruction or "").strip()
    lower = text.lower()
    url = _extract_first_url(text)

    if url:
        return (
            {"name": "web_open", "arguments": {"url": url}},
            {
                "task_type": "web",
                "is_web_subtask": True,
                "web_task": {"action": "open", "url": url},
            },
        )

    if any(hint in lower for hint in _WEB_HINTS):
        return (
            {"name": "web_snapshot", "arguments": {}},
            {
                "task_type": "web",
                "is_web_subtask": True,
                "web_task": {"action": "snapshot", "interactive": True},
            },
        )

    return (
        {"name": "Wait", "arguments": {}},
        {
            "task_type": "mobile",
            "is_web_subtask": False,
            "web_task": None,
        },
    )


def build_default_action_registry(
    pipeline: StepPipeline,
    web_skill: AgentBrowserSkill,
) -> ActionRegistry:
    registry = ActionRegistry()

    def mobile_native_shadow_handler(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        del context
        legacy_action = payload.get("legacy_action")
        step_context = payload.get("step_context")
        request, result = pipeline.run_shadow_step(legacy_action, context=step_context)
        return {
            "status": result.status,
            "request_id": request.get("request_id"),
            "intent_key": request.get("intent_key"),
            "assertion_result": result.assertion_result,
            "post_check": result.post_check,
            "recovery_level": result.recovery_level,
            "latency_ms": result.latency_ms,
        }

    def web_skill_agent_browser_handler(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        del context
        web_task = payload.get("web_task")
        session_id = str(payload.get("session_id", "default")).strip() or "default"
        if not isinstance(web_task, dict):
            web_task = {"action": "snapshot", "interactive": True}

        start = time.time()
        invoke_result = web_skill.invoke(
            task=web_task,
            session={"session_id": session_id},
            constraints={"ensure_session": False},
        )
        latency_ms = int(max(0.0, time.time() - start) * 1000)

        success = bool(invoke_result.get("success", False))
        reason = "WEB_SKILL_OK" if success else str(invoke_result.get("error") or "WEB_SKILL_EXEC_FAILED")
        return {
            "status": "SUCCESS" if success else "FAILED",
            "assertion_result": {
                "passed": success,
                "reason_code": reason,
            },
            "post_check": {
                "passed": success,
                "reason_code": reason,
            },
            "recovery_level": "NONE" if success else "L2",
            "latency_ms": latency_ms,
            "adapter_call": invoke_result,
            "session_id": session_id,
        }

    registry.register(
        "mobile_native_shadow",
        schema={
            "required": ["legacy_action", "step_context"],
            "field_types": {"legacy_action": "dict", "step_context": "dict"},
        },
        handler=mobile_native_shadow_handler,
    )
    registry.register(
        "web_skill_agent_browser",
        schema={
            "required": ["web_task", "session_id"],
            "field_types": {"web_task": "dict", "session_id": "str"},
        },
        handler=web_skill_agent_browser_handler,
    )
    return registry


def _normalize_step_status(status: str) -> str:
    status = str(status or "").upper()
    if status in {"SUCCESS", "FAILED", "HANDOVER", "BLOCKED"}:
        return status
    return "FAILED"


def _select_mobile_fallback_action(route_context: dict[str, Any], failed_reason: str) -> dict[str, Any]:
    del failed_reason
    web_task = route_context.get("web_task")
    if not isinstance(web_task, dict):
        return {"name": "Wait", "arguments": {}}

    base_action = str(web_task.get("action", "")).strip().lower()
    if base_action in {"open", "click", "type", "fill", "hover", "check", "uncheck"}:
        return {"name": "Back", "arguments": {}}
    return {"name": "Wait", "arguments": {}}


def _normalize_adapter_error(step_result: dict[str, Any]) -> str:
    adapter_call = step_result.get("adapter_call", {})
    error = None
    if isinstance(adapter_call, dict):
        error = adapter_call.get("error")
    if error:
        return str(error)
    return str(
        step_result.get("post_check", {}).get("reason_code")
        or step_result.get("assertion_result", {}).get("reason_code")
        or "WEB_SKILL_EXEC_FAILED"
    )


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _extract_anchor_confidence(exec_result: dict[str, Any]) -> tuple[float, float, float]:
    assertion_result = dict(exec_result.get("assertion_result", {}) or {})
    post_check = dict(exec_result.get("post_check", {}) or {})
    core = _as_float(
        assertion_result.get("core_anchor_confidence", post_check.get("core_anchor_confidence", 1.0)),
        1.0,
    )
    aux = _as_float(
        assertion_result.get("aux_anchor_confidence", post_check.get("aux_anchor_confidence", 1.0)),
        1.0,
    )
    geometry = _as_float(
        assertion_result.get("geometry_confidence", post_check.get("geometry_confidence", 1.0)),
        1.0,
    )
    return core, aux, geometry


def _choose_better_anchor_result(primary: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    p_pass = bool(dict(primary.get("assertion_result", {}) or {}).get("passed", False))
    c_pass = bool(dict(candidate.get("assertion_result", {}) or {}).get("passed", False))
    if c_pass and not p_pass:
        return candidate
    if p_pass and not c_pass:
        return primary
    p_core, p_aux, p_geom = _extract_anchor_confidence(primary)
    c_core, c_aux, c_geom = _extract_anchor_confidence(candidate)
    p_score = (p_core * 0.6) + (p_aux * 0.25) + (p_geom * 0.15)
    c_score = (c_core * 0.6) + (c_aux * 0.25) + (c_geom * 0.15)
    return candidate if c_score > p_score else primary


def run_probe_step(
    instruction: str,
    run_id: str,
    task_id: str,
    session_id: str | None,
    step_id: int,
    chain_mode: str,
    emit_event: EventEmitter,
    hooks: HookManager,
    router: WebSkillRouter,
    guard_policy: GuardPolicy,
    web_skill: AgentBrowserSkill,
    loop_detector: LoopDetector | None = None,
    context_compactor: ContextCompactor | None = None,
    screen_width: int = 1080,
    screen_height: int = 2340,
    web_max_steps: int = 3,
    web_replan_max_attempts: int = 1,
    confirm_wait_timeout: float = 0.0,
    confirm_poll_interval: float = 0.5,
    register_confirmation: ConfirmationRegistrar | None = None,
    wait_confirmation: ConfirmationWaiter | None = None,
) -> V2ProbeResult:
    loop_detector = loop_detector or LoopDetector()
    context_compactor = context_compactor or ContextCompactor()
    runtime_context_events: list[dict[str, Any]] = []
    runtime_session_id = str(session_id or "").strip() or None

    def _emit(event: dict[str, Any]) -> None:
        payload = dict(event)
        if runtime_session_id and not str(payload.get("session_id", "")).strip():
            payload["session_id"] = runtime_session_id

        emit_event(payload)
        runtime_context_events.append(dict(payload))
        if str(payload.get("event_type")) == "context_compaction":
            return
        compacted = context_compactor.compact(runtime_context_events)
        if compacted.get("applied", False):
            runtime_context_events[:] = list(compacted.get("events", []))
            compaction_event = {
                "run_id": run_id,
                "task_id": task_id,
                "step_id": int(payload.get("step_id", step_id)),
                "chain_mode": chain_mode,
                "event_type": "context_compaction",
                "status": "SUCCESS",
                "intent_key": str(payload.get("intent_key", "global:UNKNOWN:UNSPECIFIED_TARGET")),
                "before_count": compacted.get("before_count"),
                "after_count": compacted.get("after_count"),
                "truncated_count": compacted.get("truncated_count", 0),
                "compaction_summary": compacted.get("summary"),
            }
            if runtime_session_id:
                compaction_event["session_id"] = runtime_session_id
            emit_event(compaction_event)

    action_obj, route_context = infer_probe_action(instruction)
    step_context = {
        # Probe context uses synthetic anchor diffs to avoid false NO_STATE_CHANGE
        # when running in pure shadow mode without real perception snapshots.
        "perception_infos_pre": [{"text": "__probe_pre__", "coordinates": (1, 1)}],
        "perception_infos_post": [{"text": "__probe_post__", "coordinates": (1, 1)}],
        "screen_width": int(screen_width),
        "screen_height": int(screen_height),
        "task_type": route_context.get("task_type"),
    }
    request_context = {
        "screen_width": int(screen_width),
        "screen_height": int(screen_height),
        "task_type": route_context.get("task_type"),
    }
    request = map_legacy_action_to_request(action_obj, context=request_context)
    state_machine = ProbeStateMachine()

    def _transition_state(
        next_state: ProbeState,
        reason: str,
        *,
        status: str = "RUNNING",
        route_payload: dict[str, Any] | None = None,
    ) -> None:
        transition = state_machine.transition(next_state, reason)
        payload = {
            "run_id": run_id,
            "task_id": task_id,
            "step_id": step_id,
            "chain_mode": chain_mode,
            "event_type": "executor_state",
            "status": status if transition.ok else "FAILED",
            "intent_key": request.intent_key,
            "executor_prev_state": transition.prev_state.value,
            "executor_state": transition.next_state.value,
            "executor_reason": transition.reason,
            "executor_transition_ok": transition.ok,
        }
        if route_payload:
            payload.update(route_payload)
        _emit(payload)

    decision = router.route(
        request.intent_key,
        action=request.action,
        context=route_context,
    )
    route_info = decision.to_dict()
    page_fp = loop_detector.build_page_fingerprint(step_context.get("perception_infos_pre", []))
    loop_state = loop_detector.observe(request.action, page_fingerprint=page_fp)

    _emit(
        {
            "run_id": run_id,
            "task_id": task_id,
            "step_id": step_id,
            "chain_mode": chain_mode,
            "event_type": "step_start",
            "status": "RUNNING",
            "intent_key": request.intent_key,
            "request_id": request.request_id,
            **route_info,
        }
    )
    _transition_state(
        ProbeState.ROUTED,
        "route_decision",
        route_payload=route_info,
    )
    _emit(
        {
            "run_id": run_id,
            "task_id": task_id,
            "step_id": step_id,
            "chain_mode": chain_mode,
            "event_type": "skill_route",
            "status": "SUCCESS",
            "intent_key": request.intent_key,
            **route_info,
        }
    )
    if loop_state.get("should_warn", False):
        _emit(
            {
                "run_id": run_id,
                "task_id": task_id,
                "step_id": step_id,
                "chain_mode": chain_mode,
                "event_type": "loop_warning",
                "status": "RUNNING",
                "intent_key": request.intent_key,
                "loop_score": loop_state.get("loop_score", 0.0),
                "stagnation_steps": loop_state.get("stagnation_steps", 0),
                "repeated_action_count": loop_state.get("repeated_action_count", 0),
                **route_info,
            }
        )

    guard = guard_policy.decide(
        request.intent_key,
        request.action,
        {**route_context, **route_info},
    )
    guard_decision = str(guard.get("decision", "allow")).lower()
    _emit(
        {
            "run_id": run_id,
            "task_id": task_id,
            "step_id": step_id,
            "chain_mode": chain_mode,
            "event_type": "guard_decision",
            "status": "SUCCESS" if guard_decision == "allow" else "HANDOVER",
            "intent_key": request.intent_key,
            "policy_decision": guard_decision,
            "policy_reason": guard.get("reason"),
            "policy_category": guard.get("category"),
            "policy_source": guard.get("policy_source"),
            "policy_version": guard.get("policy_version"),
            **route_info,
        }
    )
    _transition_state(
        ProbeState.GUARDED,
        f"guard_{guard_decision}",
        route_payload=route_info,
    )

    if guard_decision != "allow":
        if guard_decision == "confirm":
            _transition_state(
                ProbeState.CONFIRM_PENDING,
                "guard_confirm_pending",
                status="BLOCKED",
                route_payload=route_info,
            )
            confirm_id = f"{run_id}:{task_id}:{step_id}"
            pending_payload = {
                "confirm_id": confirm_id,
                "run_id": run_id,
                "task_id": task_id,
                "step_id": int(step_id),
                "session_id": runtime_session_id,
                "intent_key": request.intent_key,
                "channel": route_info.get("channel"),
                "route_reason": route_info.get("route_reason"),
                "policy_decision": "confirm",
                "policy_reason": guard.get("reason"),
                "policy_category": guard.get("category"),
            }
            if register_confirmation is not None:
                try:
                    register_confirmation(pending_payload)
                except Exception:
                    pass

            _emit(
                {
                    "run_id": run_id,
                    "task_id": task_id,
                    "step_id": step_id,
                    "chain_mode": chain_mode,
                    "event_type": "pending_confirm",
                    "status": "BLOCKED",
                    "intent_key": request.intent_key,
                    "confirm_id": confirm_id,
                    "policy_decision": "confirm",
                    "policy_reason": guard.get("reason"),
                    "policy_category": guard.get("category"),
                    "confirm_wait_timeout_sec": float(max(0.0, confirm_wait_timeout)),
                    **route_info,
                }
            )

            decision = None
            if wait_confirmation is not None:
                decision = wait_confirmation(
                    confirm_id,
                    float(max(0.0, confirm_wait_timeout)),
                    float(max(0.05, confirm_poll_interval)),
                )
            if decision is not None:
                decision_value = str(decision.get("decision", "")).strip().lower()
                if decision_value in {"approve", "approved", "allow"}:
                    _emit(
                        {
                            "run_id": run_id,
                            "task_id": task_id,
                            "step_id": step_id,
                            "chain_mode": chain_mode,
                            "event_type": "confirm_approved",
                            "status": "SUCCESS",
                            "intent_key": request.intent_key,
                            "confirm_id": confirm_id,
                            "confirm_actor": decision.get("actor"),
                            "confirm_source": decision.get("source"),
                            "confirm_note": decision.get("note"),
                            **route_info,
                        }
                    )
                else:
                    _transition_state(
                        ProbeState.HANDOVER,
                        "guard_confirm_rejected",
                        status="HANDOVER",
                        route_payload=route_info,
                    )
                    _emit(
                        {
                            "run_id": run_id,
                            "task_id": task_id,
                            "step_id": step_id,
                            "chain_mode": chain_mode,
                            "event_type": "confirm_rejected",
                            "status": "HANDOVER",
                            "intent_key": request.intent_key,
                            "confirm_id": confirm_id,
                            "confirm_actor": decision.get("actor"),
                            "confirm_source": decision.get("source"),
                            "confirm_note": decision.get("note"),
                            **route_info,
                        }
                    )
                    reason_code = "GUARD_CONFIRM_REJECTED"
                    _emit(
                        {
                            "run_id": run_id,
                            "task_id": task_id,
                            "step_id": step_id,
                            "chain_mode": chain_mode,
                            "event_type": "handover",
                            "status": "HANDOVER",
                            "intent_key": request.intent_key,
                            "reason_code": reason_code,
                            **route_info,
                        }
                    )
                    _emit(
                        {
                            "run_id": run_id,
                            "task_id": task_id,
                            "step_id": step_id,
                            "chain_mode": chain_mode,
                            "event_type": "step_end",
                            "status": "HANDOVER",
                            "intent_key": request.intent_key,
                            "assertion_result": {"passed": False, "reason_code": reason_code},
                            "post_check": {"passed": False, "reason_code": reason_code},
                            "recovery_level": "L3",
                            **route_info,
                        }
                    )
                    _transition_state(
                        ProbeState.COMPLETED,
                        "handover_return",
                        status="HANDOVER",
                        route_payload=route_info,
                    )
                    return V2ProbeResult(
                        status="HANDOVER",
                        intent_key=request.intent_key,
                        channel=route_info.get("channel", "mobile_native"),
                        route_reason=route_info.get("route_reason", "unknown"),
                    )
            else:
                reason_code = "GUARD_CONFIRM_TIMEOUT" if float(confirm_wait_timeout) > 0 else "GUARD_CONFIRM_PENDING"
                if float(confirm_wait_timeout) > 0:
                    _emit(
                        {
                            "run_id": run_id,
                            "task_id": task_id,
                            "step_id": step_id,
                            "chain_mode": chain_mode,
                            "event_type": "confirm_timeout",
                            "status": "HANDOVER",
                            "intent_key": request.intent_key,
                            "confirm_id": confirm_id,
                            **route_info,
                        }
                    )
                _transition_state(
                    ProbeState.HANDOVER,
                    reason_code.lower(),
                    status="HANDOVER",
                    route_payload=route_info,
                )
                _emit(
                    {
                        "run_id": run_id,
                        "task_id": task_id,
                        "step_id": step_id,
                        "chain_mode": chain_mode,
                        "event_type": "handover",
                        "status": "HANDOVER",
                        "intent_key": request.intent_key,
                        "reason_code": reason_code,
                        **route_info,
                    }
                )
                _emit(
                    {
                        "run_id": run_id,
                        "task_id": task_id,
                        "step_id": step_id,
                        "chain_mode": chain_mode,
                        "event_type": "step_end",
                        "status": "HANDOVER",
                        "intent_key": request.intent_key,
                        "assertion_result": {"passed": False, "reason_code": reason_code},
                        "post_check": {"passed": False, "reason_code": reason_code},
                        "recovery_level": "L3",
                        **route_info,
                    }
                )
                _transition_state(
                    ProbeState.COMPLETED,
                    "handover_return",
                    status="HANDOVER",
                    route_payload=route_info,
                )
                return V2ProbeResult(
                    status="HANDOVER",
                    intent_key=request.intent_key,
                    channel=route_info.get("channel", "mobile_native"),
                    route_reason=route_info.get("route_reason", "unknown"),
                )
        else:
            reason_code = "GUARD_DENIED"
            _transition_state(
                ProbeState.HANDOVER,
                "guard_denied",
                status="HANDOVER",
                route_payload=route_info,
            )
            _emit(
                {
                    "run_id": run_id,
                    "task_id": task_id,
                    "step_id": step_id,
                    "chain_mode": chain_mode,
                    "event_type": "handover",
                    "status": "HANDOVER",
                    "intent_key": request.intent_key,
                    "reason_code": reason_code,
                    **route_info,
                }
            )
            _emit(
                {
                    "run_id": run_id,
                    "task_id": task_id,
                    "step_id": step_id,
                    "chain_mode": chain_mode,
                    "event_type": "step_end",
                    "status": "HANDOVER",
                    "intent_key": request.intent_key,
                    "assertion_result": {"passed": False, "reason_code": reason_code},
                    "post_check": {"passed": False, "reason_code": reason_code},
                    "recovery_level": "L3",
                    **route_info,
                }
            )
            _transition_state(
                ProbeState.COMPLETED,
                "handover_return",
                status="HANDOVER",
                route_payload=route_info,
            )
            return V2ProbeResult(
                status="HANDOVER",
                intent_key=request.intent_key,
                channel=route_info.get("channel", "mobile_native"),
                route_reason=route_info.get("route_reason", "unknown"),
            )

    pipeline = StepPipeline(hooks=hooks)
    registry = build_default_action_registry(pipeline=pipeline, web_skill=web_skill)

    dispatch_name = "web_skill_agent_browser" if route_info.get("channel") == "web_skill" else "mobile_native_shadow"
    final_route_info = dict(route_info)
    if route_info.get("channel") == "web_skill":
        _transition_state(
            ProbeState.EXECUTING_WEB,
            "dispatch_web_skill",
            route_payload=route_info,
        )
        web_plan = build_initial_web_plan(
            instruction=instruction,
            route_context=route_context,
            max_steps=web_max_steps,
        )
        web_plan_id = f"wp-{uuid.uuid4().hex[:12]}"
        plan_payload = [step.to_event_payload() for step in web_plan]
        _emit(
            {
                "run_id": run_id,
                "task_id": task_id,
                "step_id": step_id,
                "chain_mode": chain_mode,
                "event_type": "web_plan",
                "status": "SUCCESS",
                "intent_key": request.intent_key,
                "web_plan_id": web_plan_id,
                "web_step_count": len(plan_payload),
                "web_plan": plan_payload,
                **route_info,
            }
        )

        last_result: dict[str, Any] | None = None
        failed_reason = "WEB_SKILL_EXEC_FAILED"
        failed_on_web_step = 0
        total_latency_ms = 0
        executed_steps = 0
        replan_attempt = 0
        max_replan_attempts = max(0, int(web_replan_max_attempts))
        replan_policy = WebReplanPolicy(base_max_attempts=max_replan_attempts)
        pending_recovery_reasons: list[str] = []
        pending_steps: list[WebPlanStep] = list(web_plan)

        while pending_steps and executed_steps < int(web_max_steps):
            plan_step = pending_steps.pop(0)
            web_task = dict(plan_step.task)
            executed_steps += 1
            web_trace_id = f"wtrace-{uuid.uuid4().hex[:10]}"
            _emit(
                {
                    "run_id": run_id,
                    "task_id": task_id,
                    "step_id": step_id,
                    "chain_mode": chain_mode,
                    "event_type": "web_step_start",
                    "status": "RUNNING",
                    "intent_key": request.intent_key,
                    "web_plan_id": web_plan_id,
                    "web_trace_id": web_trace_id,
                    "web_plan_revision": int(plan_step.revision),
                    "web_step_checkpoint": plan_step.checkpoint,
                    "web_step_rationale": plan_step.rationale,
                    "web_step_index": executed_steps,
                    "web_step_count": int(web_max_steps),
                    "web_step_task": dict(web_task),
                    **route_info,
                }
            )
            try:
                step_result = registry.dispatch(
                    "web_skill_agent_browser",
                    {
                        "web_task": web_task,
                        "session_id": runtime_session_id or task_id,
                    },
                    context={},
                )
            except Exception as exc:
                step_result = {
                    "status": "FAILED",
                    "assertion_result": {"passed": False, "reason_code": "EXEC_DISPATCH_ERROR"},
                    "post_check": {"passed": False, "reason_code": "EXEC_DISPATCH_ERROR"},
                    "recovery_level": "L3",
                    "latency_ms": 0,
                    "adapter_call": {
                        "success": False,
                        "error": str(exc),
                    },
                    "session_id": runtime_session_id or task_id,
                }

            last_result = step_result
            step_latency_ms = int(step_result.get("latency_ms", 0) or 0)
            total_latency_ms += step_latency_ms
            adapter_call = step_result.get("adapter_call", {})
            adapter_success = bool(adapter_call.get("success", False))
            _emit(
                {
                    "run_id": run_id,
                    "task_id": task_id,
                    "step_id": step_id,
                    "chain_mode": chain_mode,
                    "event_type": "adapter_call",
                    "status": "SUCCESS" if adapter_success else "FAILED",
                    "intent_key": request.intent_key,
                    "adapter_backend": "agent-browser",
                    "web_plan_id": web_plan_id,
                    "web_trace_id": web_trace_id,
                    "adapter_session_id": str(step_result.get("session_id", runtime_session_id or task_id)),
                    "error": adapter_call.get("error"),
                    "adapter_trace": adapter_call.get("trace"),
                    "web_step_index": executed_steps,
                    "web_step_count": int(web_max_steps),
                    "web_step_task": dict(web_task),
                    **route_info,
                }
            )
            _emit(
                {
                    "run_id": run_id,
                    "task_id": task_id,
                    "step_id": step_id,
                    "chain_mode": chain_mode,
                    "event_type": "web_step_end",
                    "status": "SUCCESS" if adapter_success else "FAILED",
                    "intent_key": request.intent_key,
                    "web_plan_id": web_plan_id,
                    "web_trace_id": web_trace_id,
                    "web_plan_revision": int(plan_step.revision),
                    "web_step_checkpoint": plan_step.checkpoint,
                    "latency_ms": step_latency_ms,
                    "web_step_index": executed_steps,
                    "web_step_count": int(web_max_steps),
                    "web_step_task": dict(web_task),
                    **route_info,
                }
            )

            if adapter_success:
                if pending_recovery_reasons:
                    for reason in pending_recovery_reasons:
                        replan_policy.record_recovery(reason)
                        policy_decision = replan_policy.decide(reason, attempted=replan_attempt)
                        _emit(
                            {
                                "run_id": run_id,
                                "task_id": task_id,
                                "step_id": step_id,
                                "chain_mode": chain_mode,
                                "event_type": "web_replan_policy_update",
                                "status": "SUCCESS",
                                "intent_key": request.intent_key,
                                "web_plan_id": web_plan_id,
                                "replan_reason_key": policy_decision.reason_key,
                                "replan_policy_note": "record_recovery",
                                "replan_allowed_attempts": policy_decision.allowed_attempts,
                                "replan_attempted": policy_decision.attempted,
                                **route_info,
                            }
                        )
                    pending_recovery_reasons.clear()
                continue

            failed_reason = _normalize_adapter_error(step_result)
            failed_on_web_step = executed_steps
            remaining_steps = int(web_max_steps) - executed_steps
            policy_decision = replan_policy.decide(failed_reason, attempted=replan_attempt)
            _emit(
                {
                    "run_id": run_id,
                    "task_id": task_id,
                    "step_id": step_id,
                    "chain_mode": chain_mode,
                    "event_type": "web_replan_policy_decision",
                    "status": "SUCCESS" if policy_decision.allow else "HANDOVER",
                    "intent_key": request.intent_key,
                    "web_plan_id": web_plan_id,
                    "replan_reason_key": policy_decision.reason_key,
                    "replan_allowed_attempts": policy_decision.allowed_attempts,
                    "replan_attempted": policy_decision.attempted,
                    "replan_policy_note": policy_decision.policy_note,
                    "failed_reason": failed_reason,
                    **route_info,
                }
            )
            if policy_decision.allow and remaining_steps > 0:
                replan_attempt += 1
                replan_strategy, replanned_steps = build_replan_after_failure(
                    failed_step=plan_step,
                    failed_reason=failed_reason,
                    route_context=route_context,
                    remaining_steps=remaining_steps,
                    revision=replan_attempt,
                )
                if replanned_steps:
                    pending_steps = list(replanned_steps) + pending_steps
                    pending_recovery_reasons.append(failed_reason)
                    _emit(
                        {
                            "run_id": run_id,
                            "task_id": task_id,
                            "step_id": step_id,
                            "chain_mode": chain_mode,
                            "event_type": "web_replan",
                            "status": "RUNNING",
                            "intent_key": request.intent_key,
                            "web_plan_id": web_plan_id,
                            "web_replan_attempt": replan_attempt,
                            "failed_on_web_step": failed_on_web_step,
                            "failed_reason": failed_reason,
                            "web_replan_strategy": replan_strategy,
                            "replanned_steps": [item.to_event_payload() for item in replanned_steps],
                            **route_info,
                        }
                    )
                    continue
                replan_policy.record_failure(failed_reason)
                _emit(
                    {
                        "run_id": run_id,
                        "task_id": task_id,
                        "step_id": step_id,
                        "chain_mode": chain_mode,
                        "event_type": "web_replan_skipped",
                        "status": "HANDOVER",
                        "intent_key": request.intent_key,
                        "web_plan_id": web_plan_id,
                        "web_replan_attempt": replan_attempt,
                        "failed_on_web_step": failed_on_web_step,
                        "failed_reason": failed_reason,
                        "web_replan_strategy": replan_strategy,
                        "replan_reason_key": policy_decision.reason_key,
                        "replan_allowed_attempts": policy_decision.allowed_attempts,
                        **route_info,
                    }
                )
            else:
                replan_policy.record_failure(failed_reason)
                _emit(
                    {
                        "run_id": run_id,
                        "task_id": task_id,
                        "step_id": step_id,
                        "chain_mode": chain_mode,
                        "event_type": "web_replan_skipped",
                        "status": "HANDOVER",
                        "intent_key": request.intent_key,
                        "web_plan_id": web_plan_id,
                        "web_replan_attempt": replan_attempt,
                        "failed_on_web_step": failed_on_web_step,
                        "failed_reason": failed_reason,
                        "web_replan_strategy": (
                            "backend_unavailable"
                            if policy_decision.reason_key == "backend_unavailable"
                            else "policy_budget_exhausted"
                        ),
                        "replan_reason_key": policy_decision.reason_key,
                        "replan_allowed_attempts": policy_decision.allowed_attempts,
                        **route_info,
                    }
                )
            break

        if last_result is None:
            exec_result = {
                "status": "FAILED",
                "assertion_result": {"passed": False, "reason_code": "WEB_PLAN_EMPTY"},
                "post_check": {"passed": False, "reason_code": "WEB_PLAN_EMPTY"},
                "recovery_level": "L3",
                "latency_ms": 0,
                "adapter_call": {"success": False, "error": "WEB_PLAN_EMPTY"},
            }
        else:
            exec_result = dict(last_result)
            exec_result["latency_ms"] = total_latency_ms

        if str(exec_result.get("status", "")).upper() != "SUCCESS":
            _transition_state(
                ProbeState.FALLBACK,
                "web_skill_failed_fallback",
                route_payload=route_info,
            )
            _emit(
                {
                    "run_id": run_id,
                    "task_id": task_id,
                    "step_id": step_id,
                    "chain_mode": chain_mode,
                    "event_type": "skill_fallback",
                    "status": "HANDOVER",
                    "intent_key": request.intent_key,
                    "fallback_to": "mobile_native",
                    "reason_code": failed_reason,
                    "failed_on_web_step": failed_on_web_step,
                    **route_info,
                }
            )
            fallback_action = _select_mobile_fallback_action(route_context, failed_reason)
            _emit(
                {
                    "run_id": run_id,
                    "task_id": task_id,
                    "step_id": step_id,
                    "chain_mode": chain_mode,
                    "event_type": "fallback_action_selected",
                    "status": "SUCCESS",
                    "intent_key": request.intent_key,
                    "fallback_to": "mobile_native",
                    "fallback_action": fallback_action,
                    "reason_code": failed_reason,
                    **route_info,
                }
            )
            fallback_result = registry.dispatch(
                "mobile_native_shadow",
                {
                    "legacy_action": fallback_action,
                    "step_context": step_context,
                },
                context={},
            )
            _transition_state(
                ProbeState.EXECUTING_MOBILE,
                "dispatch_mobile_fallback",
                route_payload={
                    "channel": "mobile_native",
                    "route_reason": "skill_fallback_to_mobile_native",
                    "skill_name": route_info.get("skill_name"),
                },
            )
            exec_result = fallback_result
            final_route_info = {
                "channel": "mobile_native",
                "route_reason": "skill_fallback_to_mobile_native",
                "skill_name": route_info.get("skill_name"),
            }
    else:
        _transition_state(
            ProbeState.EXECUTING_MOBILE,
            "dispatch_mobile_native",
            route_payload=route_info,
        )
        try:
            exec_result = registry.dispatch(
                dispatch_name,
                {
                    "legacy_action": action_obj,
                    "step_context": step_context,
                },
                context={},
            )
        except Exception as exc:
            exec_result = {
                "status": "FAILED",
                "assertion_result": {"passed": False, "reason_code": "EXEC_DISPATCH_ERROR"},
                "post_check": {"passed": False, "reason_code": "EXEC_DISPATCH_ERROR"},
                "recovery_level": "L3",
                "latency_ms": 0,
                "adapter_call": {
                    "success": False,
                    "error": str(exc),
                },
            }

    status = _normalize_step_status(exec_result.get("status", "FAILED"))
    assertion_result = dict(exec_result.get("assertion_result", {}))
    post_check = dict(exec_result.get("post_check", {}))
    recovery_level = str(exec_result.get("recovery_level", "L3"))
    latency_ms = int(exec_result.get("latency_ms", 0) or 0)

    if str(final_route_info.get("channel", "")) == "mobile_native":
        core_conf, aux_conf, geom_conf = _extract_anchor_confidence(exec_result)
        gate_decision = "allow"
        gate_reason = "ANCHOR_CONFIDENCE_OK"

        if core_conf < _CORE_ANCHOR_MIN_CONFIDENCE:
            gate_decision = "deny"
            gate_reason = "CORE_ANCHOR_CONFIDENCE_LOW"
        elif aux_conf < _AUX_ANCHOR_RETRY_THRESHOLD:
            gate_decision = "retry"
            gate_reason = "AUX_ANCHOR_CONFIDENCE_LOW"

        _emit(
            {
                "run_id": run_id,
                "task_id": task_id,
                "step_id": step_id,
                "chain_mode": chain_mode,
                "event_type": "anchor_gate",
                "status": "SUCCESS" if gate_decision == "allow" else "HANDOVER",
                "intent_key": request.intent_key,
                "anchor_gate_decision": gate_decision,
                "anchor_gate_reason": gate_reason,
                "core_anchor_confidence": core_conf,
                "aux_anchor_confidence": aux_conf,
                "geometry_confidence": geom_conf,
                **final_route_info,
            }
        )

        if gate_decision == "retry":
            for attempt in range(1, _ANCHOR_MICRO_RETRY_MAX + 1):
                _emit(
                    {
                        "run_id": run_id,
                        "task_id": task_id,
                        "step_id": step_id,
                        "chain_mode": chain_mode,
                        "event_type": "anchor_micro_retry",
                        "status": "RUNNING",
                        "intent_key": request.intent_key,
                        "anchor_retry_attempt": attempt,
                        "anchor_retry_reason": gate_reason,
                        **final_route_info,
                    }
                )
                try:
                    retry_result = registry.dispatch(
                        "mobile_native_shadow",
                        {
                            "legacy_action": action_obj,
                            "step_context": step_context,
                        },
                        context={},
                    )
                except Exception as exc:
                    retry_result = {
                        "status": "FAILED",
                        "assertion_result": {"passed": False, "reason_code": "ANCHOR_RETRY_DISPATCH_ERROR"},
                        "post_check": {"passed": False, "reason_code": "ANCHOR_RETRY_DISPATCH_ERROR"},
                        "recovery_level": "L3",
                        "latency_ms": 0,
                        "adapter_call": {
                            "success": False,
                            "error": str(exc),
                        },
                    }
                merged = _choose_better_anchor_result(exec_result, retry_result)
                changed = merged is retry_result
                exec_result = merged
                status = _normalize_step_status(exec_result.get("status", "FAILED"))
                assertion_result = dict(exec_result.get("assertion_result", {}))
                post_check = dict(exec_result.get("post_check", {}))
                recovery_level = str(exec_result.get("recovery_level", recovery_level))
                latency_ms = int(exec_result.get("latency_ms", latency_ms) or latency_ms)
                core_conf, aux_conf, geom_conf = _extract_anchor_confidence(exec_result)
                _emit(
                    {
                        "run_id": run_id,
                        "task_id": task_id,
                        "step_id": step_id,
                        "chain_mode": chain_mode,
                        "event_type": "anchor_micro_retry",
                        "status": "SUCCESS" if status == "SUCCESS" else "FAILED",
                        "intent_key": request.intent_key,
                        "anchor_retry_attempt": attempt,
                        "anchor_retry_applied": changed,
                        "core_anchor_confidence": core_conf,
                        "aux_anchor_confidence": aux_conf,
                        "geometry_confidence": geom_conf,
                        **final_route_info,
                    }
                )
                if core_conf >= _CORE_ANCHOR_MIN_CONFIDENCE and aux_conf >= _AUX_ANCHOR_RETRY_THRESHOLD:
                    break

        if gate_decision == "deny":
            status = "FAILED"
            reason = "CORE_ANCHOR_CONFIDENCE_LOW"
            assertion_result = dict(assertion_result)
            post_check = dict(post_check)
            assertion_result["passed"] = False
            assertion_result["reason_code"] = reason
            post_check["passed"] = False
            post_check["reason_code"] = reason
            assertion_result["core_anchor_confidence"] = core_conf
            assertion_result["aux_anchor_confidence"] = aux_conf
            assertion_result["geometry_confidence"] = geom_conf
            post_check["core_anchor_confidence"] = core_conf
            post_check["aux_anchor_confidence"] = aux_conf
            post_check["geometry_confidence"] = geom_conf
            recovery_level = "L2"
            exec_result["status"] = "FAILED"
            exec_result["assertion_result"] = assertion_result
            exec_result["post_check"] = post_check
            exec_result["recovery_level"] = recovery_level
    _transition_state(
        ProbeState.VERIFYING,
        "enter_assertion_post_check",
        route_payload=final_route_info,
    )

    _emit(
        {
            "run_id": run_id,
            "task_id": task_id,
            "step_id": step_id,
            "chain_mode": chain_mode,
            "event_type": "assertion",
            "status": "SUCCESS" if assertion_result.get("passed", False) else "FAILED",
            "intent_key": request.intent_key,
            "assertion_result": assertion_result,
            "recovery_level": recovery_level,
            "s2_takeover": status != "SUCCESS",
            **final_route_info,
        }
    )
    _emit(
        {
            "run_id": run_id,
            "task_id": task_id,
            "step_id": step_id,
            "chain_mode": chain_mode,
            "event_type": "post_check",
            "status": "SUCCESS" if post_check.get("passed", False) else "FAILED",
            "intent_key": request.intent_key,
            "post_check": post_check,
            **final_route_info,
        }
    )

    final_status = "SUCCESS" if status == "SUCCESS" else "HANDOVER"
    if final_status != "SUCCESS":
        _transition_state(
            ProbeState.HANDOVER,
            "verification_failed",
            status="HANDOVER",
            route_payload=final_route_info,
        )
        reason_code = str(
            assertion_result.get("reason_code")
            or post_check.get("reason_code")
            or "UNKNOWN_ERROR"
        )
        _emit(
            {
                "run_id": run_id,
                "task_id": task_id,
                "step_id": step_id,
                "chain_mode": chain_mode,
                "event_type": "handover",
                "status": "HANDOVER",
                "intent_key": request.intent_key,
                "reason_code": reason_code,
                **final_route_info,
            }
        )
        _transition_state(
            ProbeState.COMPLETED,
            "handover_complete",
            status="HANDOVER",
            route_payload=final_route_info,
        )
    else:
        _transition_state(
            ProbeState.COMPLETED,
            "verification_passed",
            status="SUCCESS",
            route_payload=final_route_info,
        )

    _emit(
        {
            "run_id": run_id,
            "task_id": task_id,
            "step_id": step_id,
            "chain_mode": chain_mode,
            "event_type": "step_end",
            "status": final_status,
            "intent_key": request.intent_key,
            "latency_ms": latency_ms,
            "assertion_result": assertion_result,
            "post_check": post_check,
            "recovery_level": recovery_level,
            **final_route_info,
        }
    )

    return V2ProbeResult(
        status=final_status,
        intent_key=request.intent_key,
        channel=str(final_route_info.get("channel", "mobile_native")),
        route_reason=str(final_route_info.get("route_reason", "unknown")),
    )
