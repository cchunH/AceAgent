import json
import os
import time
from typing import Any

import config
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


def _emit_events_from_legacy_steps(
    bus: JSONLEventBus,
    run_id: str,
    task_id: str,
    chain_mode: str,
    log_dir: str,
) -> None:
    steps_path = os.path.join(log_dir, "steps.json")
    if not os.path.exists(steps_path):
        return
    try:
        with open(steps_path, "r", encoding="utf-8") as f:
            steps = json.load(f)
    except Exception:
        return

    for step in steps:
        event = {
            "run_id": run_id,
            "task_id": task_id,
            "step_id": int(step.get("step", 0)),
            "chain_mode": chain_mode,
            "event_type": str(step.get("operation", "unknown")),
            "status": _map_operation_status(step),
            "intent_key": _map_intent_key(step),
        }
        duration = step.get("duration")
        if isinstance(duration, (int, float)):
            event["latency_ms"] = int(duration * 1000)
        _emit_and_track(bus, event)


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
    if task_id is None:
        task_id = time.strftime("%Y%m%d-%H%M%S")
    if log_root is None:
        log_root = f"logs/{config.models.DEFAULT}/unimind_agent"
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
        perception_args=perception_args or config.models.perceptor.to_dict(),
        max_itr=max_itr,
        max_consecutive_failures=max_consecutive_failures,
        max_repetitive_actions=max_repetitive_actions,
        overwrite_log_dir=overwrite_log_dir,
        err_to_planner_thresh=err_to_planner_thresh,
        enable_experience_retriever=enable_experience_retriever,
        temperature=temperature,
        screenrecord=screenrecord,
    )

    _emit_events_from_legacy_steps(
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
            "status": "SUCCESS",
            "intent_key": "global:TASK:END",
        },
    )

    return {
        "run_id": run_id,
        "task_id": task_id,
        "log_dir": log_dir,
        "event_log": os.path.join(log_dir, "events.jsonl"),
    }

