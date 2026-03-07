from __future__ import annotations

import re
import time
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
from .web_skill_router import WebSkillRouter


EventEmitter = Callable[[dict[str, Any]], None]
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
_WEB_SNAPSHOT_HINTS = (
    "snapshot",
    "截图",
    "检查",
    "校验",
)


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


def _build_web_execution_plan(
    instruction: str,
    route_context: dict[str, Any],
    max_steps: int,
) -> list[dict[str, Any]]:
    max_steps = max(1, int(max_steps))
    text = str(instruction or "").strip().lower()
    base_task = route_context.get("web_task")
    if not isinstance(base_task, dict):
        base_task = {"action": "snapshot", "interactive": True}

    plan: list[dict[str, Any]] = []
    action_name = str(base_task.get("action", "snapshot")).strip().lower()
    if action_name == "open":
        url = str(base_task.get("url", "")).strip()
        if url:
            plan.append({"action": "open", "url": url})
        else:
            plan.append({"action": "snapshot", "interactive": True})
        if len(plan) < max_steps:
            plan.append({"action": "snapshot", "interactive": True})
    elif action_name:
        plan.append(dict(base_task))
    else:
        plan.append({"action": "snapshot", "interactive": True})

    if len(plan) < max_steps and any(hint in text for hint in _WEB_SNAPSHOT_HINTS):
        plan.append({"action": "snapshot", "interactive": True})

    deduped: list[dict[str, Any]] = []
    for task in plan:
        if not deduped or deduped[-1] != task:
            deduped.append(task)
    return deduped[:max_steps]


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

    if guard_decision != "allow":
        reason_code = "GUARD_CONFIRM_REQUIRED" if guard_decision == "confirm" else "GUARD_DENIED"
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
        web_plan = _build_web_execution_plan(
            instruction=instruction,
            route_context=route_context,
            max_steps=web_max_steps,
        )
        _emit(
            {
                "run_id": run_id,
                "task_id": task_id,
                "step_id": step_id,
                "chain_mode": chain_mode,
                "event_type": "web_plan",
                "status": "SUCCESS",
                "intent_key": request.intent_key,
                "web_step_count": len(web_plan),
                "web_plan": web_plan,
                **route_info,
            }
        )

        last_result: dict[str, Any] | None = None
        failed_reason = "WEB_SKILL_EXEC_FAILED"
        failed_on_web_step = 0
        total_latency_ms = 0
        for idx, web_task in enumerate(web_plan, start=1):
            _emit(
                {
                    "run_id": run_id,
                    "task_id": task_id,
                    "step_id": step_id,
                    "chain_mode": chain_mode,
                    "event_type": "web_step_start",
                    "status": "RUNNING",
                    "intent_key": request.intent_key,
                    "web_step_index": idx,
                    "web_step_count": len(web_plan),
                    "web_step_task": dict(web_task),
                    **route_info,
                }
            )
            try:
                step_result = registry.dispatch(
                    "web_skill_agent_browser",
                    {
                        "web_task": dict(web_task),
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
                    "adapter_session_id": str(step_result.get("session_id", runtime_session_id or task_id)),
                    "error": adapter_call.get("error"),
                    "web_step_index": idx,
                    "web_step_count": len(web_plan),
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
                    "latency_ms": step_latency_ms,
                    "web_step_index": idx,
                    "web_step_count": len(web_plan),
                    "web_step_task": dict(web_task),
                    **route_info,
                }
            )

            if not adapter_success:
                failed_reason = str(adapter_call.get("error") or "WEB_SKILL_EXEC_FAILED")
                failed_on_web_step = idx
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
            fallback_result = registry.dispatch(
                "mobile_native_shadow",
                {
                    "legacy_action": {"name": "Wait", "arguments": {}},
                    "step_context": step_context,
                },
                context={},
            )
            exec_result = fallback_result
            final_route_info = {
                "channel": "mobile_native",
                "route_reason": "skill_fallback_to_mobile_native",
                "skill_name": route_info.get("skill_name"),
            }
    else:
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
