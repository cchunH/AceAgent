import json
import os
import time
from typing import Any

from guiagent_v2.action_engine.affine_runtime import project_action
from guiagent_v2.blueprint_hub import Blueprint, BlueprintRepository
from guiagent_v2.intent_contract import map_legacy_action_to_request
from .blueprint_sync import upsert_blueprint_from_observation
from .agent_browser_skill import AgentBrowserSkill
from .context_compaction import ContextCompactor
from .default_hooks import post_state_check_hook, semantic_pre_assertion_hook
from .event_bus import JSONLEventBus
from .guard_policy import GuardPolicy
from .hooks import HookManager
from .loop_detector import LoopDetector
from .reporting import write_runtime_summary
from .status_api import configure_global_status_store, get_global_status_store
from .v2_executor import run_probe_step
from .web_skill_router import WebSkillRouter
from .watchdogs import WatchdogManager, build_default_watchdog_manager


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
    watchdog_manager: WatchdogManager | None = None,
) -> dict[str, Any]:
    emitted = bus.emit(event)
    get_global_status_store().update(emitted)

    if watchdog_manager is not None:
        for alert in watchdog_manager.process(emitted):
            alert_emitted = bus.emit(alert)
            get_global_status_store().update(alert_emitted)
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
        "route_by_step": {},
        "screen_size": {"width": screen_width, "height": screen_height},
    }


def _default_route_info() -> dict[str, Any]:
    return {
        "channel": "mobile_native",
        "route_reason": "default_mobile_native",
    }


def _build_route_context(step: dict[str, Any]) -> dict[str, Any]:
    context = {}
    raw = step.get("route_context")
    if isinstance(raw, dict):
        context.update(raw)
    for key in ("force_channel", "task_type", "is_web_subtask"):
        if key in step:
            context[key] = step.get(key)
    return context


def _translate_legacy_step_to_events(
    step: dict[str, Any],
    context_index: dict[str, dict[int, Any]],
    hooks: HookManager,
    blueprint_repo: BlueprintRepository | None = None,
    router: WebSkillRouter | None = None,
    loop_detector: LoopDetector | None = None,
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
        loop_events: list[dict[str, Any]] = []
        if loop_detector is not None:
            perception_infos = context_index.get("perception_by_step", {}).get(step_id, [])
            page_fp = loop_detector.build_page_fingerprint(perception_infos)
            loop_state = loop_detector.observe(request.action, page_fingerprint=page_fp)
            if loop_state.get("should_warn", False):
                loop_events.append(
                    {
                        "step_id": step_id,
                        "event_type": "loop_warning",
                        "status": "RUNNING",
                        "intent_key": intent_key,
                        "loop_score": loop_state.get("loop_score", 0.0),
                        "stagnation_steps": loop_state.get("stagnation_steps", 0),
                        "repeated_action_count": loop_state.get("repeated_action_count", 0),
                    }
                )
        route_info = _default_route_info()
        if router is not None:
            decision = router.route(
                request.intent_key,
                action=request.action,
                context=_build_route_context(step),
            )
            route_info = decision.to_dict()
        context_index.setdefault("route_by_step", {})[step_id] = route_info
        route_event = {
            "step_id": step_id,
            "event_type": "skill_route",
            "status": "SUCCESS",
            "intent_key": intent_key,
            **route_info,
        }
        event = {
            "step_id": step_id,
            "event_type": "action_exec",
            "status": "RUNNING",
            "intent_key": intent_key,
            "action": projected_action,
            "timeout_ms": 3000,
            "retry_count": 0,
            **route_info,
        }
        if blueprint:
            event["blueprint_version"] = blueprint.get("version", "v0.1.0")
        if latency_ms is not None:
            event["latency_ms"] = latency_ms
            route_event["latency_ms"] = latency_ms
        return [*loop_events, route_event, event]

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

        if blueprint_repo is not None:
            upsert_blueprint_from_observation(
                repo=blueprint_repo,
                intent_key=request.intent_key,
                screen_width=int(screen_size.get("width", 1080)),
                screen_height=int(screen_size.get("height", 2340)),
                perception_infos_pre=step_context["perception_infos_pre"],
                perception_infos_post=step_context["perception_infos_post"],
                action_outcome="A" if success else ("B" if "B" in outcome else "C"),
                post_check_result=post_check_result,
            )

        route_info = (
            context_index.get("route_by_step", {}).get(step_id)
            or _default_route_info()
        )
        events = [
            {
                "step_id": step_id,
                "event_type": "assertion",
                "status": "SUCCESS" if assertion_result.get("passed", False) else "FAILED",
                "intent_key": intent_key,
                "assertion_result": assertion_result,
                "recovery_level": recovery,
                "s2_takeover": not success or not assertion_result.get("passed", False),
                **route_info,
            }
        ]
        events.append(
            {
                "step_id": step_id,
                "event_type": "post_check",
                "status": "SUCCESS" if post_check_result.get("passed", False) else "FAILED",
                "intent_key": intent_key,
                "post_check": post_check_result,
                **route_info,
            }
        )
        if not success and route_info.get("channel") == "web_skill":
            events.append(
                {
                    "step_id": step_id,
                    "event_type": "skill_fallback",
                    "status": "HANDOVER",
                    "intent_key": intent_key,
                    "fallback_to": "mobile_native",
                    "reason_code": reason,
                    **route_info,
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
                    **route_info,
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
            **route_info,
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
    session_id: str | None = None,
    watchdog_manager: WatchdogManager | None = None,
    blueprint_repo: BlueprintRepository | None = None,
    router: WebSkillRouter | None = None,
    loop_detector: LoopDetector | None = None,
    context_compactor: ContextCompactor | None = None,
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
    loop_detector = loop_detector or LoopDetector()
    context_compactor = context_compactor or ContextCompactor()
    runtime_context_events: list[dict[str, Any]] = []

    for step in steps:
        translated_events = _translate_legacy_step_to_events(
            step,
            context_index,
            hooks,
            blueprint_repo=blueprint_repo,
            router=router,
            loop_detector=loop_detector,
        )
        for event in translated_events:
            event["run_id"] = run_id
            event["task_id"] = task_id
            event["chain_mode"] = chain_mode
            if session_id:
                event["session_id"] = session_id
            emitted = _emit_and_track(bus, event, watchdog_manager=watchdog_manager)
            runtime_context_events.append(emitted)

            if str(emitted.get("event_type")) == "context_compaction":
                continue
            compacted = context_compactor.compact(runtime_context_events)
            if compacted.get("applied", False):
                runtime_context_events = list(compacted.get("events", []))
                _emit_and_track(
                    bus,
                    {
                        "run_id": run_id,
                        "task_id": task_id,
                        "step_id": int(event.get("step_id", 0)),
                        "chain_mode": chain_mode,
                        "event_type": "context_compaction",
                        "status": "SUCCESS",
                        "intent_key": str(event.get("intent_key", "global:UNKNOWN:UNSPECIFIED_TARGET")),
                        "before_count": compacted.get("before_count"),
                        "after_count": compacted.get("after_count"),
                        "truncated_count": compacted.get("truncated_count", 0),
                        "compaction_summary": compacted.get("summary"),
                        **({"session_id": session_id} if session_id else {}),
                    },
                    watchdog_manager=watchdog_manager,
                )
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
    v2_skip_legacy=False,
    guard_policy_path=None,
    guard_policy_reload_interval=1.0,
    watchdog_policy_path=None,
    watchdog_policy_reload_interval=1.0,
    session_id=None,
    strict_event_schema=False,
    status_timeline_max_events=None,
    web_max_steps=3,
    web_replan_max_attempts=1,
):
    future_tasks = future_tasks or []
    runtime_config = _load_runtime_config()
    if task_id is None:
        task_id = time.strftime("%Y%m%d-%H%M%S")
    if log_root is None:
        log_root = f"logs/{runtime_config.models.DEFAULT}/unimind_agent"
    chain_mode = _normalize_chain_mode(runtime_mode)
    run_id = f"{run_name}:{task_id}"
    runtime_session_id = str(session_id or "").strip() or None
    if status_timeline_max_events is not None:
        configure_global_status_store(
            max_timeline_events_per_task=int(status_timeline_max_events),
        )
    log_dir = _build_log_dir(log_root, run_name, task_id)
    os.makedirs(log_dir, exist_ok=True)
    bus = JSONLEventBus(
        file_path=os.path.join(log_dir, "events.jsonl"),
        default_chain_mode=chain_mode,
        strict_schema=bool(strict_event_schema),
    )
    blueprint_repo = BlueprintRepository(os.path.join(log_dir, "blueprints.json"))
    router = WebSkillRouter()
    if guard_policy_path:
        guard_policy = GuardPolicy.from_policy_file(
            policy_path=str(guard_policy_path),
            reload_interval_sec=float(guard_policy_reload_interval),
        )
    else:
        guard_policy = GuardPolicy()
    web_skill = AgentBrowserSkill()
    loop_detector = LoopDetector()
    context_compactor = ContextCompactor()
    watchdog_manager = build_default_watchdog_manager(
        policy_path=str(watchdog_policy_path) if watchdog_policy_path else None,
        reload_interval_sec=float(watchdog_policy_reload_interval),
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
            **({"session_id": runtime_session_id} if runtime_session_id else {}),
        },
        watchdog_manager=watchdog_manager,
    )

    probe_result = None
    if runtime_mode in {"guiagent_v2_shadow", "guiagent_v2"}:
        hooks = _build_hook_manager()
        probe_result = run_probe_step(
            instruction=instruction,
            run_id=run_id,
            task_id=task_id,
            session_id=runtime_session_id,
            step_id=1,
            chain_mode=chain_mode,
            emit_event=lambda event: _emit_and_track(bus, event, watchdog_manager=watchdog_manager),
            hooks=hooks,
            router=router,
            guard_policy=guard_policy,
            web_skill=web_skill,
            loop_detector=loop_detector,
            context_compactor=context_compactor,
            screen_width=1080,
            screen_height=2340,
            web_max_steps=int(web_max_steps),
            web_replan_max_attempts=int(web_replan_max_attempts),
        )

    should_delegate_legacy = not (runtime_mode == "guiagent_v2" and bool(v2_skip_legacy))
    if should_delegate_legacy:
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
            session_id=runtime_session_id,
            watchdog_manager=watchdog_manager,
            blueprint_repo=blueprint_repo,
            router=router,
            loop_detector=loop_detector,
            context_compactor=context_compactor,
        )
    else:
        final_status = probe_result.status if probe_result is not None else "SUCCESS"

    _emit_and_track(
        bus,
        {
            "run_id": run_id,
            "task_id": task_id,
            "step_id": 999999,
            "event_type": "task_end",
            "status": final_status,
            "intent_key": "global:TASK:END",
            **({"session_id": runtime_session_id} if runtime_session_id else {}),
        },
        watchdog_manager=watchdog_manager,
    )

    summary_info = write_runtime_summary(
        log_dir=log_dir,
        event_log_path=os.path.join(log_dir, "events.jsonl"),
        blueprint_repo=blueprint_repo,
    )

    return {
        "status": final_status,
        "run_id": run_id,
        "task_id": task_id,
        "session_id": runtime_session_id,
        "log_dir": log_dir,
        "event_log": os.path.join(log_dir, "events.jsonl"),
        "summary_log": summary_info["summary_path"],
    }
