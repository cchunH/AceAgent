import json
import os
import time
from typing import Any

from guiagent_v2.action_engine.affine_runtime import project_action
from guiagent_v2.blueprint_hub import Blueprint, BlueprintRepository
from guiagent_v2.intent_contract import map_legacy_action_to_request
from .default_hooks import post_state_check_hook, semantic_pre_assertion_hook
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


def _build_hook_manager() -> HookManager:
    hooks = HookManager()
    hooks.register_pre_assertion_hook(semantic_pre_assertion_hook)
    hooks.register_post_check_hook(post_state_check_hook)
    return hooks


def _build_legacy_context_index(steps: list[dict[str, Any]]) -> dict[str, dict[int, Any]]:
    perception_by_step: dict[int, Any] = {}
    action_by_step: dict[int, Any] = {}
    screen_width = 1080
    screen_height = 2340
    for step in steps:
        operation = str(step.get("operation", ""))
        step_id = int(step.get("step", 0))
        if operation == "perception":
            perception_by_step[step_id] = step.get("perception_infos", [])
        elif operation == "action":
            action_by_step[step_id] = step
        elif operation == "init":
            init_pool = step.get("init_info_pool", {})
            try:
                screen_width = int(init_pool.get("width", screen_width))
                screen_height = int(init_pool.get("height", screen_height))
            except Exception:
                pass
    return {
        "perception_by_step": perception_by_step,
        "action_by_step": action_by_step,
        "screen_size": {"width": screen_width, "height": screen_height},
    }


def _translate_legacy_step_to_events(
    step: dict[str, Any],
    context_index: dict[str, dict[int, Any]],
    hooks: HookManager,
    blueprint_repo: BlueprintRepository | None = None,
) -> list[dict[str, Any]]:
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
        screen_size = context_index.get("screen_size", {"width": 1080, "height": 2340})
        screen_width = int(screen_size.get("width", 1080))
        screen_height = int(screen_size.get("height", 2340))
        request_context = {"screen_width": screen_width, "screen_height": screen_height}
        request = map_legacy_action_to_request(action_obj, context=request_context)

        blueprint = None
        if blueprint_repo is not None:
            blueprint = blueprint_repo.get_blueprint(request.intent_key, app_state="global:DEFAULT")
            if blueprint is None:
                blueprint_repo.save_blueprint(
                    Blueprint(
                        intent_key=request.intent_key,
                        app_state="global:DEFAULT",
                        reference_screen={"width": screen_width, "height": screen_height},
                    )
                )
            else:
                request_context["post_expectations"] = blueprint.get("post_expectations", [])

        reference_screen = (
            blueprint.get("reference_screen", {"width": screen_width, "height": screen_height})
            if blueprint
            else {"width": screen_width, "height": screen_height}
        )
        topology_result = {
            "reference_screen": reference_screen,
            "target_screen": {"width": screen_width, "height": screen_height},
            "confidence": 1.0,
        }
        projected_action = project_action(request=request, topology_result=topology_result)
        event = {
            "step_id": step_id,
            "event_type": "action_exec",
            "status": "RUNNING",
            "intent_key": intent_key,
            "action": projected_action,
            "timeout_ms": 3000,
            "retry_count": 0,
        }
        if blueprint:
            event["blueprint_version"] = blueprint.get("version", "v0.1.0")
        if latency_ms is not None:
            event["latency_ms"] = latency_ms
        return [event]

    if operation == "action_reflection":
        action_step = context_index.get("action_by_step", {}).get(step_id, {})
        action_obj = action_step.get("action_object")
        screen_size = context_index.get("screen_size", {"width": 1080, "height": 2340})
        step_context = {
            "perception_infos_pre": context_index.get("perception_by_step", {}).get(step_id, []),
            "perception_infos_post": context_index.get("perception_by_step", {}).get(step_id + 1, []),
            "screen_width": int(screen_size.get("width", 1080)),
            "screen_height": int(screen_size.get("height", 2340)),
        }
        request = map_legacy_action_to_request(action_obj, context=step_context)
        assertion_result = hooks.run_pre_assertion(request, context=step_context)
        post_check_result = hooks.run_post_check(request, context=step_context)

        outcome = str(step.get("outcome", "")).upper()
        success = "A" in outcome
        reason = "OK" if success else str(step.get("error_description", "UNKNOWN_ERROR"))
        status = "SUCCESS" if success else "HANDOVER"
        if "B" in outcome:
            recovery = "L2"
        elif "C" in outcome:
            recovery = "L1"
        else:
            recovery = "NONE" if success else "L3"

        if not success:
            if "C" in outcome and assertion_result.get("passed", True):
                assertion_result = {
                    "passed": False,
                    "reason_code": "ASSERTION_MISMATCH",
                }
            if "B" in outcome and post_check_result.get("passed", True):
                post_check_result = {
                    "passed": False,
                    "reason_code": "POST_CHECK_FAILED",
                }

        events = [
            {
                "step_id": step_id,
                "event_type": "assertion",
                "status": "SUCCESS" if assertion_result.get("passed", False) else "FAILED",
                "intent_key": intent_key,
                "assertion_result": assertion_result,
                "recovery_level": recovery,
                "s2_takeover": not success or not assertion_result.get("passed", False),
            }
        ]
        events.append(
            {
                "step_id": step_id,
                "event_type": "post_check",
                "status": "SUCCESS" if post_check_result.get("passed", False) else "FAILED",
                "intent_key": intent_key,
                "post_check": post_check_result,
            }
        )
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
            "assertion_result": assertion_result,
            "post_check": post_check_result,
            "recovery_level": recovery,
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
    blueprint_repo: BlueprintRepository | None = None,
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
    context_index = _build_legacy_context_index(steps)
    hooks = _build_hook_manager()

    for step in steps:
        translated_events = _translate_legacy_step_to_events(
            step,
            context_index,
            hooks,
            blueprint_repo=blueprint_repo,
        )
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
    blueprint_repo = BlueprintRepository(os.path.join(log_dir, "blueprints.json"))

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
        hooks = _build_hook_manager()
        pipeline = StepPipeline(hooks=hooks)
        request, result = pipeline.run_shadow_step(
            {"name": "Wait", "arguments": {}},
            context={
                "perception_infos_pre": [],
                "perception_infos_post": [],
                "screen_width": 1080,
                "screen_height": 2340,
            },
        )
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
                "event_type": "assertion",
                "status": "SUCCESS" if result.assertion_result.get("passed", False) else "FAILED",
                "intent_key": request["intent_key"],
                "assertion_result": result.assertion_result,
                "recovery_level": result.recovery_level,
                "s2_takeover": not result.assertion_result.get("passed", False),
            },
        )
        _emit_and_track(
            bus,
            {
                "run_id": run_id,
                "task_id": task_id,
                "step_id": 1,
                "event_type": "post_check",
                "status": "SUCCESS" if result.post_check.get("passed", False) else "FAILED",
                "intent_key": request["intent_key"],
                "post_check": result.post_check,
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
        blueprint_repo=blueprint_repo,
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
