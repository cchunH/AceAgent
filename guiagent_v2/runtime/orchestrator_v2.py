import json
import os
import time
from typing import Any

from guiagent_v2.intent_contract import map_legacy_action_to_request
from .event_bus import JSONLEventBus
from .hooks import HookManager
from .pipeline import StepPipeline
from .status_api import get_global_status_store


def _build_log_dir(log_root: str, run_name: str, task_id: str) -> str:
    return f"{log_root}/{run_name}/{task_id}"


def _normalize_chain_mode(runtime_mode: str) -> str:
    if runtime_mode == "legacy":
        return "legacy"
    return runtime_mode


def _load_runtime_config():
    import config  # Lazy import to avoid hard dependency during lightweight unit tests.

    return config


def _emit_and_track(
    bus: JSONLEventBus,
    event: dict[str, Any],
) -> dict[str, Any]:
    emitted = bus.emit(event)
    get_global_status_store().update(emitted)
    return emitted


def _map_operation_status(step: dict[str, Any]) -> str:
    operation = step.get("operation")
    if operation == "finish":
        finish_flag = str(step.get("finish_flag", "")).lower()
        if "success" in finish_flag:
            return "SUCCESS"
        return "FAILED"

    if operation == "action_reflection":
        outcome = str(step.get("outcome", "")).upper()
        if "A" in outcome:
            return "SUCCESS"
        if "B" in outcome or "C" in outcome:
            return "FAILED"
    return "RUNNING"


def _map_intent_key(step: dict[str, Any]) -> str:
    action_obj = step.get("action_object")
    if isinstance(action_obj, dict):
        req = map_legacy_action_to_request(action_obj)
        return req.intent_key
    return "global:UNKNOWN:UNSPECIFIED_TARGET"


def _translate_legacy_step_to_events(step: dict[str, Any]) -> list[dict[str, Any]]:
    operation = str(step.get("operation", "unknown"))
    step_id = int(step.get("step", 0))
    duration = step.get("duration")
    latency_ms = int(duration * 1000) if isinstance(duration, (int, float)) else None
    intent_key = _map_intent_key(step)

    if operation == "perception":
        return [
            {
                "step_id": step_id,
                "event_type": "step_start",
                "status": "RUNNING",
                "intent_key": "global:STEP:START",
            }
        ]

    if operation == "action":
        action_obj = step.get("action_object")
        event = {
            "step_id": step_id,
            "event_type": "action_exec",
            "status": "RUNNING",
            "intent_key": intent_key,
            "action": action_obj,
            "timeout_ms": 3000,
            "retry_count": 0,
        }
        if latency_ms is not None:
            event["latency_ms"] = latency_ms
        return [event]

    if operation == "action_reflection":
        outcome = str(step.get("outcome", "")).upper()
        success = "A" in outcome
        reason = "OK" if success else str(step.get("error_description", "UNKNOWN_ERROR"))
        status = "SUCCESS" if success else "HANDOVER"
        recovery = "NONE" if success else ("L2" if "B" in outcome else "L1")

        events = [
            {
                "step_id": step_id,
                "event_type": "assertion",
                "status": "SUCCESS" if success else "FAILED",
                "intent_key": intent_key,
                "assertion_result": {"passed": success, "reason_code": reason},
                "recovery_level": recovery,
                "s2_takeover": not success,
            }
        ]
        if not success:
            events.append(
                {
                    "step_id": step_id,
                    "event_type": "handover",
                    "status": "HANDOVER",
                    "intent_key": intent_key,
                    "reason_code": reason,
                }
            )
        step_end_event = {
            "step_id": step_id,
            "event_type": "step_end",
            "status": status,
            "intent_key": intent_key,
        }
        if latency_ms is not None:
            step_end_event["latency_ms"] = latency_ms
        events.append(step_end_event)
        return events

    event = {
        "step_id": step_id,
        "event_type": operation,
        "status": _map_operation_status(step),
        "intent_key": intent_key,
    }
    if latency_ms is not None:
        event["latency_ms"] = latency_ms
    return [event]


def _emit_events_from_legacy_steps(
    bus: JSONLEventBus,
    run_id: str,
    task_id: str,
    chain_mode: str,
    log_dir: str,
) -> str:
    steps_path = os.path.join(log_dir, "steps.json")
    if not os.path.exists(steps_path):
        return "FAILED"
    try:
        with open(steps_path, "r", encoding="utf-8") as f:
            steps = json.load(f)
    except Exception:
        return "FAILED"

    final_status = "FAILED"

    for step in steps:
        translated_events = _translate_legacy_step_to_events(step)
        for event in translated_events:
            event["run_id"] = run_id
            event["task_id"] = task_id
            event["chain_mode"] = chain_mode
            _emit_and_track(bus, event)
        if str(step.get("operation")) == "finish":
            final_status = _map_operation_status(step)

    return final_status


def run_single_task_with_runtime(
    instruction,
    future_tasks=None,
    run_name="test",
    log_root=None,
    task_id=None,
    heuristics_path=None,
    skills_path=None,
    persistent_heuristics_path=None,
    persistent_skills_path=None,
    perceptor=None,
    perception_args=None,
    max_itr=40,
    max_consecutive_failures=3,
    max_repetitive_actions=3,
    overwrite_log_dir=False,
    err_to_planner_thresh=2,
    enable_experience_retriever=False,
    temperature=0.0,
    screenrecord=False,
    runtime_mode="legacy",
):
    future_tasks = future_tasks or []
    runtime_config = _load_runtime_config()
    if task_id is None:
        task_id = time.strftime("%Y%m%d-%H%M%S")
    if log_root is None:
        log_root = f"logs/{runtime_config.models.DEFAULT}/unimind_agent"
    chain_mode = _normalize_chain_mode(runtime_mode)
    run_id = f"{run_name}:{task_id}"
    log_dir = _build_log_dir(log_root, run_name, task_id)
    os.makedirs(log_dir, exist_ok=True)
    bus = JSONLEventBus(
        file_path=os.path.join(log_dir, "events.jsonl"),
        default_chain_mode=chain_mode,
    )

    _emit_and_track(
        bus,
        {
            "run_id": run_id,
            "task_id": task_id,
            "step_id": 0,
            "event_type": "task_start",
            "status": "RUNNING",
            "intent_key": "global:TASK:START",
        },
    )

    if runtime_mode in {"guiagent_v2_shadow", "guiagent_v2"}:
        hooks = HookManager()
        pipeline = StepPipeline(hooks=hooks)
        request, result = pipeline.run_shadow_step({"name": "Wait", "arguments": {}})
        _emit_and_track(
            bus,
            {
                "run_id": run_id,
                "task_id": task_id,
                "step_id": 1,
                "event_type": "step_start",
                "status": "RUNNING",
                "intent_key": request["intent_key"],
                "request_id": request["request_id"],
            },
        )
        _emit_and_track(
            bus,
            {
                "run_id": run_id,
                "task_id": task_id,
                "step_id": 1,
                "event_type": "step_end",
                "status": result.status,
                "intent_key": request["intent_key"],
                "latency_ms": result.latency_ms,
                "assertion_result": result.assertion_result,
                "post_check": result.post_check,
            },
        )

    # Delegate to legacy runner while v2 runtime is incubated.
    from orchestrator import run_single_task as legacy_run_single_task

    legacy_run_single_task(
        instruction=instruction,
        future_tasks=future_tasks,
        run_name=run_name,
        log_root=log_root,
        task_id=task_id,
        heuristics_path=heuristics_path,
        skills_path=skills_path,
        persistent_heuristics_path=persistent_heuristics_path,
        persistent_skills_path=persistent_skills_path,
        perceptor=perceptor,
        perception_args=perception_args or runtime_config.models.perceptor.to_dict(),
        max_itr=max_itr,
        max_consecutive_failures=max_consecutive_failures,
        max_repetitive_actions=max_repetitive_actions,
        overwrite_log_dir=overwrite_log_dir,
        err_to_planner_thresh=err_to_planner_thresh,
        enable_experience_retriever=enable_experience_retriever,
        temperature=temperature,
        screenrecord=screenrecord,
    )

    final_status = _emit_events_from_legacy_steps(
        bus=bus,
        run_id=run_id,
        task_id=task_id,
        chain_mode=chain_mode,
        log_dir=log_dir,
    )

    _emit_and_track(
        bus,
        {
            "run_id": run_id,
            "task_id": task_id,
            "step_id": 999999,
            "event_type": "task_end",
            "status": final_status,
            "intent_key": "global:TASK:END",
        },
    )

    return {
        "run_id": run_id,
        "task_id": task_id,
        "log_dir": log_dir,
        "event_log": os.path.join(log_dir, "events.jsonl"),
    }
