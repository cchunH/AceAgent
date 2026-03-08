import importlib
import json
import os
import re
import time
import shutil
from typing import Any

from guiagent_v2.action_engine.affine_runtime import project_action
from guiagent_v2.blueprint_hub import Blueprint, BlueprintRepository
from guiagent_v2.intent_contract import map_legacy_action_to_request
from guiagent_v2.state_engine import build_static_skeleton
from .blueprint_sync import upsert_blueprint_from_observation
from .agent_browser_skill import AgentBrowserSkill
from .context_compaction import ContextCompactor
from .default_hooks import post_state_check_hook, semantic_pre_assertion_hook
from .event_bus import JSONLEventBus
from .guard_policy import GuardPolicy
from .hooks import HookManager
from .loop_detector import LoopDetector
from .reporting import write_runtime_summary
from .status_api import (
    configure_global_status_store,
    get_global_status_store,
    register_pending_confirmation,
    wait_confirmation_decision,
)
from .v2_executor import run_probe_step
from .web_skill_router import WebSkillRouter
from .watchdogs import WatchdogManager, build_default_watchdog_manager


def _build_log_dir(log_root: str, run_name: str, task_id: str) -> str:
    return f"{log_root}/{run_name}/{task_id}"


def _normalize_chain_mode(runtime_mode: str) -> str:
    if runtime_mode == "legacy":
        return "legacy"
    return runtime_mode


_STEP_SPLIT_PATTERN = re.compile(r"[;\n。！？!?；]+")
_CONNECTOR_SPLIT_PATTERN = re.compile(
    r"\b(?:and then|then|next)\b|然后|接着|随后|接下来|下一步",
    flags=re.IGNORECASE,
)


def _split_instruction_into_steps(instruction: str, max_steps: int) -> list[str]:
    raw = str(instruction or "").strip()
    if not raw:
        return []

    cap = max(1, int(max_steps))
    stage1 = [part.strip() for part in _STEP_SPLIT_PATTERN.split(raw) if str(part).strip()]
    if not stage1:
        stage1 = [raw]

    chunks: list[str] = []
    for part in stage1:
        sub_parts = [
            p.strip().strip("，,")
            for p in _CONNECTOR_SPLIT_PATTERN.split(part)
            if str(p).strip().strip("，,")
        ]
        if sub_parts:
            chunks.extend(sub_parts)
        else:
            chunks.append(part.strip().strip("，,"))

    deduped: list[str] = []
    for chunk in chunks:
        if deduped and deduped[-1] == chunk:
            continue
        deduped.append(chunk)
        if len(deduped) >= cap:
            break
    return deduped or [raw]


def _load_runtime_config():
    import config  # Lazy import to avoid hard dependency during lightweight unit tests.

    return config


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _sanitize_file_token(value: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value or "").strip())
    return token.strip("_") or "snapshot"


def _build_live_perception_provider(
    *,
    perceptor: Any,
    runtime_config: Any,
    screenshot_trace_dir: str | None = None,
):
    if perceptor is None or not hasattr(perceptor, "get_perception_infos"):
        return None

    paths_obj = getattr(runtime_config, "paths", None)
    screenshot_dir = str(getattr(paths_obj, "SCREENSHOT_DIR", "screenshot") or "screenshot")
    temp_dir = str(getattr(paths_obj, "TEMP_DIR", "temp") or "temp")
    screenshot_file = os.path.join(".", screenshot_dir, "screenshot.jpg")

    os.makedirs(screenshot_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)
    if screenshot_trace_dir:
        os.makedirs(str(screenshot_trace_dir), exist_ok=True)
    sequence = {"idx": 0}

    def _provider(
        *,
        snapshot_role: str = "snapshot",
        step_id: int = 0,
        run_id: str = "",
        task_id: str = "",
        chain_mode: str = "",
    ) -> dict[str, Any]:
        try:
            infos, width, height = perceptor.get_perception_infos(
                screenshot_file,
                temp_file=temp_dir,
            )
        except Exception:
            return {}

        captured_path = None
        if screenshot_trace_dir and os.path.exists(screenshot_file):
            sequence["idx"] += 1
            safe_role = _sanitize_file_token(snapshot_role)
            safe_task = _sanitize_file_token(task_id or "task")
            safe_mode = _sanitize_file_token(chain_mode or "runtime")
            filename = (
                f"{sequence['idx']:04d}__{safe_task}__step{int(step_id):04d}"
                f"__{safe_role}__{safe_mode}.jpg"
            )
            target = os.path.join(str(screenshot_trace_dir), filename)
            try:
                shutil.copy2(screenshot_file, target)
                captured_path = target
            except Exception:
                captured_path = None

        return {
            "perception_infos": infos if isinstance(infos, list) else [],
            "screen_width": _safe_int(width, 1080),
            "screen_height": _safe_int(height, 2340),
            "keyboard": False,
            "screenshot_path": captured_path,
            "snapshot_seq": int(sequence["idx"]),
            "snapshot_role": snapshot_role,
            "run_id": run_id,
            "task_id": task_id,
        }

    return _provider


def _load_vector_backend_plugin(plugin_spec: str) -> dict[str, Any]:
    spec = str(plugin_spec or "").strip()
    if not spec or ":" not in spec:
        raise ValueError("blueprint_vector_plugin must be '<module>:<factory>'")
    module_name, factory_name = spec.split(":", 1)
    module_name = module_name.strip()
    factory_name = factory_name.strip()
    if not module_name or not factory_name:
        raise ValueError("blueprint_vector_plugin must be '<module>:<factory>'")
    module = importlib.import_module(module_name)
    factory = getattr(module, factory_name)
    payload = factory()

    vector_index = None
    embedding_fn = None
    source = "vector_custom"
    if isinstance(payload, dict):
        vector_index = payload.get("vector_index")
        embedding_fn = payload.get("embedding_fn")
        source = str(payload.get("source", source) or source)
    elif isinstance(payload, tuple):
        if len(payload) >= 1:
            vector_index = payload[0]
        if len(payload) >= 2:
            embedding_fn = payload[1]
        if len(payload) >= 3:
            source = str(payload[2] or source)
    else:
        vector_index = payload

    if vector_index is None:
        raise ValueError("custom vector plugin must return vector_index")
    return {
        "vector_index": vector_index,
        "embedding_fn": embedding_fn,
        "source": source,
    }


def _build_blueprint_repository(
    *,
    log_dir: str,
    vector_backend: str | None = None,
    vector_plugin: str | None = None,
    embedding_dim: int | None = None,
) -> tuple[BlueprintRepository, dict[str, Any]]:
    repo = BlueprintRepository(os.path.join(log_dir, "blueprints.json"))
    backend = str(
        vector_backend
        if vector_backend is not None
        else os.getenv("GUIAGENT_BLUEPRINT_VECTOR_BACKEND", "memory")
    ).strip().lower() or "memory"
    plugin_spec = str(
        vector_plugin
        if vector_plugin is not None
        else os.getenv("GUIAGENT_BLUEPRINT_VECTOR_PLUGIN", "")
    ).strip()
    resolved_dim = _safe_int(
        embedding_dim if embedding_dim is not None else os.getenv("GUIAGENT_BLUEPRINT_EMBEDDING_DIM", "32"),
        32,
    )
    if resolved_dim <= 0:
        resolved_dim = 32

    info: dict[str, Any] = {
        "status": "SUCCESS",
        "backend": backend,
        "plugin": plugin_spec or None,
        "embedding_dim": int(resolved_dim),
    }

    memory_aliases = {"memory", "in_memory", "default"}
    if backend in memory_aliases:
        backend_info = repo.configure_vector_backend(
            embedding_dim=resolved_dim,
            source="vector_mock",
            rebuild=False,
        )
        info["applied"] = backend_info
        return repo, info

    if backend == "custom":
        if not plugin_spec:
            backend_info = repo.configure_vector_backend(
                embedding_dim=resolved_dim,
                source="vector_mock",
                rebuild=False,
            )
            info.update(
                {
                    "status": "FAILED",
                    "reason_code": "BLUEPRINT_VECTOR_PLUGIN_MISSING",
                    "applied": backend_info,
                }
            )
            return repo, info
        try:
            loaded = _load_vector_backend_plugin(plugin_spec)
            backend_info = repo.configure_vector_backend(
                vector_index=loaded.get("vector_index"),
                embedding_fn=loaded.get("embedding_fn"),
                embedding_dim=resolved_dim,
                source=str(loaded.get("source", "vector_custom")),
                rebuild=False,
            )
            info["applied"] = backend_info
            return repo, info
        except Exception as exc:
            backend_info = repo.configure_vector_backend(
                embedding_dim=resolved_dim,
                source="vector_mock",
                rebuild=False,
            )
            info.update(
                {
                    "status": "FAILED",
                    "reason_code": "BLUEPRINT_VECTOR_PLUGIN_LOAD_FAILED",
                    "error": str(exc),
                    "applied": backend_info,
                }
            )
            return repo, info

    backend_info = repo.configure_vector_backend(
        embedding_dim=resolved_dim,
        source="vector_mock",
        rebuild=False,
    )
    info.update(
        {
            "status": "FAILED",
            "reason_code": "BLUEPRINT_VECTOR_BACKEND_UNSUPPORTED",
            "applied": backend_info,
        }
    )
    return repo, info


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
        fast_match_hint: dict[str, Any] | None = None
        if blueprint_repo is not None:
            selected_blueprint = blueprint_repo.get_blueprint(
                request.intent_key,
                app_state="global:DEFAULT",
            )
            if selected_blueprint is None:
                observed_skeleton = build_static_skeleton(
                    frames=[step_context["perception_infos_pre"]],
                    screen_size=(
                        int(screen_size.get("width", 1080)),
                        int(screen_size.get("height", 2340)),
                    ),
                    min_presence_ratio=1.0,
                    max_nodes=8,
                )
                candidates = blueprint_repo.match_by_skeleton(
                    observed_skeleton=observed_skeleton.to_dict(),
                    app_state="global:DEFAULT",
                    top_k=1,
                )
                if candidates:
                    top = candidates[0]
                    if float(top.get("score", 0.0)) >= 0.55:
                        selected_blueprint = blueprint_repo.get_blueprint(
                            str(top.get("intent_key", "")),
                            app_state="global:DEFAULT",
                        )
                        fast_match_hint = {
                            "matched_intent_key": top.get("intent_key"),
                            "matched_score": top.get("score"),
                            "signature_hit": top.get("signature_hit"),
                        }
            if selected_blueprint is not None:
                step_context["expected_anchors"] = list(selected_blueprint.get("anchors", []))
                step_context["expected_skeleton"] = selected_blueprint.get("static_skeleton")
                step_context["post_expectations"] = list(
                    selected_blueprint.get("post_expectations", step_context.get("post_expectations", []))
                )
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
                **({"fast_match_hint": fast_match_hint} if fast_match_hint else {}),
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
    confirm_wait_timeout=0.0,
    confirm_poll_interval=0.5,
    mobile_execution_mode="auto",
    mobile_wait_ms=1000,
    v2_max_steps=4,
    v2_use_live_perception=False,
    v2_capture_action_screenshots=True,
    v2_screenshot_subdir="screenshots",
    blueprint_vector_backend=None,
    blueprint_vector_plugin=None,
    blueprint_embedding_dim=None,
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
    screenshot_log_dir = os.path.join(log_dir, str(v2_screenshot_subdir or "screenshots"))
    os.makedirs(screenshot_log_dir, exist_ok=True)
    bus = JSONLEventBus(
        file_path=os.path.join(log_dir, "events.jsonl"),
        default_chain_mode=chain_mode,
        strict_schema=bool(strict_event_schema),
    )
    blueprint_repo, blueprint_backend_info = _build_blueprint_repository(
        log_dir=log_dir,
        vector_backend=blueprint_vector_backend,
        vector_plugin=blueprint_vector_plugin,
        embedding_dim=blueprint_embedding_dim,
    )
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
    _emit_and_track(
        bus,
        {
            "run_id": run_id,
            "task_id": task_id,
            "step_id": 0,
            "chain_mode": chain_mode,
            "event_type": "blueprint_backend_config",
            "status": str(blueprint_backend_info.get("status", "SUCCESS")).upper(),
            "intent_key": "global:BLUEPRINT:VECTOR_BACKEND",
            "blueprint_backend": blueprint_backend_info.get("backend"),
            "blueprint_plugin": blueprint_backend_info.get("plugin"),
            "blueprint_embedding_dim": blueprint_backend_info.get("embedding_dim"),
            "blueprint_backend_info": blueprint_backend_info.get("applied", {}),
            "reason_code": blueprint_backend_info.get("reason_code"),
            "error": blueprint_backend_info.get("error"),
            **({"session_id": runtime_session_id} if runtime_session_id else {}),
        },
        watchdog_manager=watchdog_manager,
    )

    probe_result = None
    if runtime_mode in {"guiagent_v2_shadow", "guiagent_v2"}:
        hooks = _build_hook_manager()
        perception_provider = None
        if bool(v2_use_live_perception):
            perception_provider = _build_live_perception_provider(
                perceptor=perceptor,
                runtime_config=runtime_config,
                screenshot_trace_dir=screenshot_log_dir,
            )
        if runtime_mode == "guiagent_v2" and bool(v2_skip_legacy):
            step_instructions = _split_instruction_into_steps(instruction, max_steps=int(v2_max_steps))
            if not step_instructions:
                step_instructions = [str(instruction or "").strip() or "Wait"]

            for idx, step_instruction in enumerate(step_instructions, start=1):
                _emit_and_track(
                    bus,
                    {
                        "run_id": run_id,
                        "task_id": task_id,
                        "step_id": idx,
                        "chain_mode": chain_mode,
                        "event_type": "v2_task_step",
                        "status": "RUNNING",
                        "intent_key": "global:TASK:STEP",
                        "v2_step_instruction": step_instruction,
                        "v2_step_total": len(step_instructions),
                        **({"session_id": runtime_session_id} if runtime_session_id else {}),
                    },
                    watchdog_manager=watchdog_manager,
                )
                probe_result = run_probe_step(
                    instruction=step_instruction,
                    run_id=run_id,
                    task_id=task_id,
                    session_id=runtime_session_id,
                    step_id=idx,
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
                    confirm_wait_timeout=float(confirm_wait_timeout),
                    confirm_poll_interval=float(confirm_poll_interval),
                    register_confirmation=register_pending_confirmation,
                    wait_confirmation=wait_confirmation_decision,
                    mobile_execution_mode=str(mobile_execution_mode or "auto"),
                    adb_path=str(getattr(runtime_config.paths, "ADB_PATH", "adb")),
                    mobile_wait_ms=int(max(0, int(mobile_wait_ms))),
                    perception_provider=perception_provider,
                    blueprint_repo=blueprint_repo,
                    screenshot_log_dir=screenshot_log_dir,
                    capture_action_screenshot=bool(v2_capture_action_screenshots),
                )
                _emit_and_track(
                    bus,
                    {
                        "run_id": run_id,
                        "task_id": task_id,
                        "step_id": idx,
                        "chain_mode": chain_mode,
                        "event_type": "v2_task_step",
                        "status": str(probe_result.status).upper(),
                        "intent_key": str(probe_result.intent_key or "global:TASK:STEP"),
                        "v2_step_instruction": step_instruction,
                        "v2_step_total": len(step_instructions),
                        "channel": probe_result.channel,
                        "route_reason": probe_result.route_reason,
                        **({"session_id": runtime_session_id} if runtime_session_id else {}),
                    },
                    watchdog_manager=watchdog_manager,
                )
                if probe_result.status != "SUCCESS":
                    break
        else:
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
                confirm_wait_timeout=float(confirm_wait_timeout),
                confirm_poll_interval=float(confirm_poll_interval),
                register_confirmation=register_pending_confirmation,
                wait_confirmation=wait_confirmation_decision,
                mobile_execution_mode=str(mobile_execution_mode or "auto"),
                adb_path=str(getattr(runtime_config.paths, "ADB_PATH", "adb")),
                mobile_wait_ms=int(max(0, int(mobile_wait_ms))),
                perception_provider=perception_provider,
                blueprint_repo=blueprint_repo,
                screenshot_log_dir=screenshot_log_dir,
                capture_action_screenshot=bool(v2_capture_action_screenshots),
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
        "screenshot_log_dir": screenshot_log_dir,
    }
