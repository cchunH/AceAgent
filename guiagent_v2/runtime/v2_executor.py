from __future__ import annotations

import re
import time
import uuid
import hashlib
from dataclasses import dataclass
from typing import Any, Callable

from guiagent_v2.intent_contract import map_legacy_action_to_request
from guiagent_v2.state_engine import (
    build_static_skeleton,
    denoise_perception_frames,
    extract_anchors,
    match_topology,
)
from .action_registry import ActionRegistry
from .agent_browser_skill import AgentBrowserSkill
from .blueprint_sync import upsert_blueprint_from_observation_with_gate
from .context_compaction import ContextCompactor
from .guard_policy import GuardPolicy
from .hooks import HookManager
from .loop_detector import LoopDetector
from .mobile_device_executor import MobileDeviceExecutor
from .model_assertion_repair import repair_assertion_with_model
from .model_intent_parser import parse_probe_instruction_with_model
from .model_web_replan import build_replan_after_failure_with_model
from .pipeline import StepPipeline
from .executor_state_machine import ProbeState, ProbeStateMachine
from .v2_model_settings import V2ModelSettings
from .web_skill_router import WebSkillRouter
from .web_planner import WebPlanStep, build_initial_web_plan, build_replan_after_failure
from .web_replan_policy import WebReplanPolicy


EventEmitter = Callable[[dict[str, Any]], None]
ConfirmationRegistrar = Callable[[dict[str, Any]], dict[str, Any] | None]
ConfirmationWaiter = Callable[[str, float, float], dict[str, Any] | None]
PerceptionProvider = Callable[..., dict[str, Any] | None]
_URL_PATTERN = re.compile(r"(?:https?://[^\s]+|about:[^\s]+)", re.IGNORECASE)
_WEB_HINTS = (
    "http://",
    "https://",
    "about:",
    "网页",
    "浏览器",
    "website",
    "browser",
    "web",
    "h5",
)
_BACK_HINTS = ("返回", "回退", "back")
_HOME_HINTS = ("回到桌面", "返回桌面", "回桌面", "主页", "首页", "home screen", "go home")
_WAIT_HINTS = ("等待", "稍等", "等一下", "wait", "sleep", "pause", "暂停")
_COMPLEX_ACTION_HINTS = (
    "微信",
    "好友",
    "联系人",
    "发送",
    "发给",
    "发一个",
    "消息",
    "打开",
    "点击",
    "输入",
    "搜索",
    "进入",
    "切换",
    "然后",
    "并且",
    "并",
    "设置",
    "领取",
    "导航",
)
_CORE_ANCHOR_MIN_CONFIDENCE = 0.45
_AUX_ANCHOR_RETRY_THRESHOLD = 0.35
_ANCHOR_MICRO_RETRY_MAX = 1
_BLUEPRINT_SKELETON_ACCEPT_SCORE = 0.55
_BLUEPRINT_FUSED_ACCEPT_SCORE = 0.38
_BLUEPRINT_VECTOR_STRONG_SCORE = 0.72
_TOPOLOGY_AFFINE_MAX_FIT_ERROR = 0.12
_TOPOLOGY_AFFINE_MIN_PAIR_COUNT = 2
_TOPOLOGY_AFFINE_MIN_CORE_CONFIDENCE = 0.35


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

    if any(hint in text for hint in _HOME_HINTS) or " home" in lower:
        return (
            {"name": "Home", "arguments": {}},
            {
                "task_type": "mobile",
                "is_web_subtask": False,
                "web_task": None,
            },
        )

    if any(hint in text for hint in _BACK_HINTS):
        return (
            {"name": "Back", "arguments": {}},
            {
                "task_type": "mobile",
                "is_web_subtask": False,
                "web_task": None,
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


def _is_explicit_wait_instruction(text: str) -> bool:
    raw = str(text or "").strip()
    lower = raw.lower()
    if any(h in raw for h in ("等待", "稍等", "等一下", "暂停")):
        return True
    if re.search(r"\b(wait|sleep|pause)\b", lower):
        return True
    return False


def _is_complex_instruction(text: str) -> bool:
    raw = str(text or "").strip()
    if len(raw) < 6:
        return False
    return any(hint in raw for hint in _COMPLEX_ACTION_HINTS)


def _page_hint_match_score(
    page_hint: str,
    perception_infos: list[dict[str, Any]],
    fast_match_hint: dict[str, Any] | None,
) -> float:
    hint = str(page_hint or "").strip().lower()
    if not hint:
        return 1.0

    score = 0.0
    for item in list(perception_infos or []):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip().lower()
        if not text:
            continue
        if hint in text or text in hint:
            score = max(score, 1.0)
            break

    if isinstance(fast_match_hint, dict):
        matched_intent_key = str(fast_match_hint.get("matched_intent_key", "")).strip().lower()
        if matched_intent_key and hint in matched_intent_key:
            score = max(score, 0.7)
        if bool(fast_match_hint.get("signature_hit", False)):
            score = max(score, 0.6 if score < 0.6 else score)

    return float(score)


def _fuse_page_fingerprint_score(
    *,
    ocr_fast_score: float,
    topology_result: dict[str, Any] | None,
) -> dict[str, float]:
    topo_conf = 0.0
    core_conf = 0.0
    geom_conf = 0.0
    if isinstance(topology_result, dict):
        try:
            topo_conf = float(topology_result.get("confidence", 0.0) or 0.0)
        except Exception:
            topo_conf = 0.0
        try:
            core_conf = float(topology_result.get("core_confidence", 0.0) or 0.0)
        except Exception:
            core_conf = 0.0
        try:
            geom_conf = float(topology_result.get("geometry_confidence", 0.0) or 0.0)
        except Exception:
            geom_conf = 0.0

    base = max(0.0, min(1.0, float(ocr_fast_score)))
    topo = max(0.0, min(1.0, topo_conf))
    core = max(0.0, min(1.0, core_conf))
    geom = max(0.0, min(1.0, geom_conf))

    # Conservative fusion: textual/intent evidence dominates; topology boosts confidence.
    fused = (base * 0.65) + (topo * 0.20) + (core * 0.10) + (geom * 0.05)
    fused = max(0.0, min(1.0, fused))
    return {
        "page_fingerprint_score": float(fused),
        "page_hint_ocr_fast_score": float(base),
        "page_hint_topology_confidence": float(topo),
        "page_hint_core_confidence": float(core),
        "page_hint_geometry_confidence": float(geom),
    }


def _build_runtime_page_fingerprint_id(
    *,
    perception_infos: list[dict[str, Any]],
    screen_width: int,
    screen_height: int,
) -> str:
    try:
        skeleton = build_static_skeleton(
            frames=[list(perception_infos or [])],
            screen_size=(int(screen_width), int(screen_height)),
            min_presence_ratio=1.0,
            max_nodes=8,
        )
        signature = str(skeleton.signature or "").strip()
        if signature:
            digest = hashlib.sha1(signature.encode("utf-8")).hexdigest()[:16]
            return f"pfid:{digest}"
    except Exception:
        pass
    basis = f"{int(screen_width)}x{int(screen_height)}::{len(list(perception_infos or []))}"
    digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]
    return f"pfid:{digest}"


def build_default_action_registry(
    pipeline: StepPipeline,
    web_skill: AgentBrowserSkill,
) -> ActionRegistry:
    registry = ActionRegistry()

    def mobile_native_handler(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        del context
        legacy_action = payload.get("legacy_action")
        raw_step_context = payload.get("step_context")
        step_context = dict(raw_step_context or {}) if isinstance(raw_step_context, dict) else {}
        post_context_provider = step_context.pop("post_context_provider", None)
        request, result, exec_detail = pipeline.run_step(
            legacy_action,
            context=step_context,
            post_context_provider=post_context_provider if callable(post_context_provider) else None,
        )
        return {
            "status": result.status,
            "request_id": request.get("request_id"),
            "intent_key": request.get("intent_key"),
            "assertion_result": result.assertion_result,
            "post_check": result.post_check,
            "recovery_level": result.recovery_level,
            "latency_ms": result.latency_ms,
            "adapter_call": exec_detail,
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
        "mobile_native",
        schema={
            "required": ["legacy_action", "step_context"],
            "field_types": {"legacy_action": "dict", "step_context": "dict"},
        },
        handler=mobile_native_handler,
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


def _clip01(value: Any) -> float:
    return max(0.0, min(1.0, _as_float(value, 0.0)))


def _normalize_vector_similarity(value: Any) -> float:
    score = _as_float(value, 0.0)
    if score < 0.0:
        score = (score + 1.0) / 2.0
    return _clip01(score)


def _build_vector_query_candidates(instruction: str, step_context: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    base = str(instruction or "").strip()
    if base:
        parts.append(base)
    for item in list(step_context.get("perception_infos_pre", []))[:12]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text or text == "icon: None":
            continue
        parts.append(text)

    candidates: list[str] = []
    full_query = " | ".join(parts).strip()
    if full_query:
        candidates.append(full_query)

    token_query_parts: list[str] = []
    seen_tokens: set[str] = set()
    for text in parts:
        for token in re.findall(r"[a-z0-9_]+", str(text).lower()):
            if len(token) <= 1 or token in seen_tokens:
                continue
            seen_tokens.add(token)
            token_query_parts.append(token)
    token_query = " ".join(token_query_parts).strip()
    if token_query and token_query not in candidates:
        candidates.append(token_query)
    return candidates


def _resolve_blueprint_context(
    *,
    blueprint_repo: Any,
    request_intent_key: str,
    instruction: str,
    step_context: dict[str, Any],
    screen_width: int,
    screen_height: int,
) -> dict[str, Any] | None:
    if blueprint_repo is None:
        return None
    selected_blueprint = blueprint_repo.get_blueprint(
        request_intent_key,
        app_state="global:DEFAULT",
    )
    fast_match_hint = None
    if selected_blueprint is None:
        observed_skeleton = build_static_skeleton(
            frames=[list(step_context.get("perception_infos_pre", []))],
            screen_size=(int(screen_width), int(screen_height)),
            min_presence_ratio=1.0,
            max_nodes=8,
        )
        skeleton_candidates = blueprint_repo.match_by_skeleton(
            observed_skeleton=observed_skeleton.to_dict(),
            app_state="global:DEFAULT",
            top_k=3,
        )
        top_skeleton = skeleton_candidates[0] if skeleton_candidates else None
        if top_skeleton and _clip01(top_skeleton.get("score", 0.0)) >= _BLUEPRINT_SKELETON_ACCEPT_SCORE:
            selected_blueprint = blueprint_repo.get_blueprint(
                str(top_skeleton.get("intent_key", "")),
                app_state="global:DEFAULT",
            )
            fast_match_hint = {
                "matched_intent_key": top_skeleton.get("intent_key"),
                "match_source": "skeleton",
                "skeleton_score": _clip01(top_skeleton.get("score", 0.0)),
                "vector_score": 0.0,
                "fused_score": _clip01(top_skeleton.get("score", 0.0)),
                "signature_hit": bool(top_skeleton.get("signature_hit", False)),
            }
        else:
            vector_candidates: list[dict[str, Any]] = []
            for vector_query in _build_vector_query_candidates(instruction, step_context):
                try:
                    rows = blueprint_repo.match_by_vector(
                        query_text=vector_query,
                        app_state="global:DEFAULT",
                        top_k=3,
                    )
                except Exception:
                    rows = []
                if rows:
                    vector_candidates.extend(rows)

            merged: dict[str, dict[str, Any]] = {}
            for row in skeleton_candidates:
                intent = str(row.get("intent_key", "")).strip()
                if not intent:
                    continue
                merged[intent] = {
                    "intent_key": intent,
                    "skeleton_score": _clip01(row.get("score", 0.0)),
                    "vector_score": 0.0,
                    "signature_hit": bool(row.get("signature_hit", False)),
                }
            for row in vector_candidates:
                intent = str(row.get("intent_key", "")).strip()
                if not intent:
                    continue
                record = merged.setdefault(
                    intent,
                    {
                        "intent_key": intent,
                        "skeleton_score": 0.0,
                        "vector_score": 0.0,
                        "signature_hit": False,
                    },
                )
                record["vector_score"] = max(
                    float(record.get("vector_score", 0.0)),
                    _normalize_vector_similarity(row.get("score", 0.0)),
                )

            for record in merged.values():
                fused = (
                    _clip01(record.get("skeleton_score", 0.0)) * 0.65
                    + _clip01(record.get("vector_score", 0.0)) * 0.35
                )
                if bool(record.get("signature_hit", False)):
                    fused += 0.05
                record["fused_score"] = _clip01(fused)

            if merged:
                top = max(
                    merged.values(),
                    key=lambda x: (x.get("fused_score", 0.0), x.get("vector_score", 0.0), x.get("skeleton_score", 0.0)),
                )
                skeleton_score = _clip01(top.get("skeleton_score", 0.0))
                vector_score = _clip01(top.get("vector_score", 0.0))
                fused_score = _clip01(top.get("fused_score", 0.0))
                accepted = (
                    fused_score >= _BLUEPRINT_FUSED_ACCEPT_SCORE
                    or vector_score >= _BLUEPRINT_VECTOR_STRONG_SCORE
                    or skeleton_score >= _BLUEPRINT_SKELETON_ACCEPT_SCORE
                )
                if accepted:
                    selected_blueprint = blueprint_repo.get_blueprint(
                        str(top.get("intent_key", "")),
                        app_state="global:DEFAULT",
                    )
                    if selected_blueprint is not None:
                        source = "fused"
                        if skeleton_score >= _BLUEPRINT_SKELETON_ACCEPT_SCORE and vector_score < 0.2:
                            source = "skeleton"
                        elif vector_score >= _BLUEPRINT_VECTOR_STRONG_SCORE and skeleton_score < 0.2:
                            source = "vector"
                        fast_match_hint = {
                            "matched_intent_key": top.get("intent_key"),
                            "match_source": source,
                            "skeleton_score": skeleton_score,
                            "vector_score": vector_score,
                            "fused_score": fused_score,
                            "signature_hit": bool(top.get("signature_hit", False)),
                        }
    if selected_blueprint is not None:
        step_context["expected_anchors"] = list(selected_blueprint.get("anchors", []))
        step_context["expected_skeleton"] = selected_blueprint.get("static_skeleton")
        step_context["post_expectations"] = list(selected_blueprint.get("post_expectations", []))
        step_context["reference_screen"] = dict(selected_blueprint.get("reference_screen", {}) or {})
    return fast_match_hint


def _build_runtime_topology_result(step_context: dict[str, Any]) -> dict[str, Any] | None:
    expected_anchors = list(step_context.get("expected_anchors", []))
    if not expected_anchors:
        return None

    width = int(step_context.get("screen_width", 1080))
    height = int(step_context.get("screen_height", 2340))
    pre_infos = list(step_context.get("perception_infos_pre", []))
    denoise = denoise_perception_frames(
        frames=[pre_infos],
        screen_size=(width, height),
        min_presence_ratio=1.0,
        max_items=24,
    )
    observed_infos = list(denoise.get("stable_infos", [])) or pre_infos
    observed_anchors = extract_anchors(
        observed_infos,
        (width, height),
        max_anchors=max(8, len(expected_anchors) + 2),
    )
    topo = match_topology(observed_anchors, expected_anchors)

    reference_screen = dict(step_context.get("reference_screen", {}) or {})
    if not reference_screen:
        reference_screen = {
            "width": int(width),
            "height": int(height),
        }
    target_screen = {
        "width": int(width),
        "height": int(height),
    }
    affine_norm = dict(topo.affine_norm or {})
    guard_reason = "OK"
    if not affine_norm:
        guard_reason = "NO_AFFINE_TRANSFORM"
    elif int(topo.transform_pair_count) < _TOPOLOGY_AFFINE_MIN_PAIR_COUNT:
        guard_reason = "INSUFFICIENT_ANCHOR_PAIRS"
    elif float(topo.transform_fit_error) > _TOPOLOGY_AFFINE_MAX_FIT_ERROR:
        guard_reason = "AFFINE_FIT_ERROR_HIGH"
    elif float(topo.core_confidence) < _TOPOLOGY_AFFINE_MIN_CORE_CONFIDENCE:
        guard_reason = "CORE_CONFIDENCE_LOW"

    affine_enabled = guard_reason == "OK"
    if not affine_enabled:
        affine_norm = {}

    return {
        "reference_screen": reference_screen,
        "target_screen": target_screen,
        "confidence": float(topo.confidence),
        "core_confidence": float(topo.core_confidence),
        "aux_confidence": float(topo.aux_confidence),
        "geometry_confidence": float(topo.geometry_confidence),
        "transform_mode": str(topo.transform_mode),
        "affine_norm": affine_norm,
        "transform_fit_error": float(topo.transform_fit_error),
        "transform_pair_count": int(topo.transform_pair_count),
        "projection_mode": "affine_norm" if affine_enabled else "scale",
        "projection_guard_reason": guard_reason,
        "projection_affine_enabled": affine_enabled,
    }


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
    mobile_executor: MobileDeviceExecutor | None = None,
    mobile_execution_mode: str = "auto",
    adb_path: str = "adb",
    mobile_wait_ms: int = 1000,
    perception_provider: PerceptionProvider | None = None,
    blueprint_repo: Any | None = None,
    replay_gate_config: dict[str, Any] | None = None,
    model_settings: V2ModelSettings | None = None,
    screenshot_log_dir: str | None = None,
    capture_action_screenshot: bool = True,
    page_hint: str | None = None,
    page_fingerprint_id: str | None = None,
    page_match_threshold: float | None = None,
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

    model_settings = model_settings or V2ModelSettings()
    action_obj, route_context = infer_probe_action(instruction)
    if bool(model_settings.enable_intent_parser) and str(model_settings.intent_parser_model).strip():
        try:
            parse_result = parse_probe_instruction_with_model(
                instruction=instruction,
                model=str(model_settings.intent_parser_model),
                model_type=str(model_settings.api_type or "").strip() or None,
                api_url=str(model_settings.api_url or "").strip() or None,
                api_key=str(model_settings.api_key or "").strip() or None,
                extra_body=model_settings.extra_body,
                temperature=float(model_settings.temperature),
            )
            if parse_result.get("ok", False):
                action_obj = dict(parse_result.get("action_obj", action_obj))
                route_context = dict(parse_result.get("route_context", route_context))
                _emit(
                    {
                        "run_id": run_id,
                        "task_id": task_id,
                        "step_id": step_id,
                        "chain_mode": chain_mode,
                        "event_type": "model_intent_parse",
                        "status": "SUCCESS",
                        "intent_key": "global:MODEL_INTENT_PARSE:APPLIED",
                        "model_name": str(model_settings.intent_parser_model),
                        "model_confidence": parse_result.get("confidence"),
                        "parsed_action": dict(action_obj),
                    }
                )
            else:
                _emit(
                    {
                        "run_id": run_id,
                        "task_id": task_id,
                        "step_id": step_id,
                        "chain_mode": chain_mode,
                        "event_type": "model_intent_parse",
                        "status": "FAILED",
                        "intent_key": "global:MODEL_INTENT_PARSE:FALLBACK",
                        "model_name": str(model_settings.intent_parser_model),
                        "reason_code": str(parse_result.get("error", "MODEL_INTENT_PARSE_FAILED")),
                    }
                )
        except Exception as exc:
            _emit(
                {
                    "run_id": run_id,
                    "task_id": task_id,
                    "step_id": step_id,
                    "chain_mode": chain_mode,
                    "event_type": "model_intent_parse",
                    "status": "FAILED",
                    "intent_key": "global:MODEL_INTENT_PARSE:ERROR",
                    "model_name": str(model_settings.intent_parser_model),
                    "reason_code": "MODEL_INTENT_PARSE_EXCEPTION",
                    "error": str(exc),
                }
            )

    action_name = str(action_obj.get("name", "")).strip().lower()
    collapse_to_wait = (
        action_name == "wait"
        and not _is_explicit_wait_instruction(instruction)
        and _is_complex_instruction(instruction)
    )
    collapse_reason_code = "INTENT_COLLAPSED_TO_WAIT"

    def _default_snapshot(pre: bool) -> dict[str, Any]:
        infos = [{"text": "__probe_pre__", "coordinates": (1, 1)}] if pre else [{"text": "__probe_post__", "coordinates": (1, 1)}]
        return {
            "perception_infos": infos,
            "screen_width": int(screen_width),
            "screen_height": int(screen_height),
            "keyboard": False,
        }

    def _capture_snapshot(*, pre: bool) -> dict[str, Any]:
        if perception_provider is None:
            return _default_snapshot(pre=pre)
        try:
            role = "pre" if pre else "post"
            try:
                raw = perception_provider(
                    snapshot_role=role,
                    step_id=step_id,
                    run_id=run_id,
                    task_id=task_id,
                    chain_mode=chain_mode,
                ) or {}
            except TypeError:
                raw = perception_provider() or {}
        except Exception:
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        infos = raw.get("perception_infos")
        if not isinstance(infos, list):
            infos = []
        return {
            "perception_infos": infos,
            "screen_width": int(raw.get("screen_width", screen_width) or screen_width),
            "screen_height": int(raw.get("screen_height", screen_height) or screen_height),
            "keyboard": bool(raw.get("keyboard", False)),
            "screenshot_path": str(raw.get("screenshot_path", "")).strip() or None,
            "snapshot_seq": int(raw.get("snapshot_seq", 0) or 0),
        }

    pre_snapshot = _capture_snapshot(pre=True)
    post_seed = _default_snapshot(pre=False) if perception_provider is None else pre_snapshot
    step_context = {
        "perception_infos_pre": list(pre_snapshot.get("perception_infos", [])),
        "perception_infos_post": list(post_seed.get("perception_infos", [])),
        "screen_width": int(pre_snapshot.get("screen_width", screen_width)),
        "screen_height": int(pre_snapshot.get("screen_height", screen_height)),
        "mobile_execution_mode": str(mobile_execution_mode or "").strip().lower(),
        "task_type": route_context.get("task_type"),
        "keyboard_pre": bool(pre_snapshot.get("keyboard", False)),
        "keyboard_post": bool(post_seed.get("keyboard", False)),
        "run_id": run_id,
        "task_id": task_id,
        "step_id": int(step_id),
        "screenshot_pre": pre_snapshot.get("screenshot_path"),
        "screenshot_post": post_seed.get("screenshot_path"),
        "screenshot_prefix": f"{task_id}",
    }
    runtime_page_fingerprint_id = _build_runtime_page_fingerprint_id(
        perception_infos=list(step_context.get("perception_infos_pre", []) or []),
        screen_width=int(step_context.get("screen_width", screen_width)),
        screen_height=int(step_context.get("screen_height", screen_height)),
    )
    step_context["runtime_page_fingerprint_id"] = runtime_page_fingerprint_id
    if pre_snapshot.get("screenshot_path"):
        _emit(
            {
                "run_id": run_id,
                "task_id": task_id,
                "step_id": step_id,
                "chain_mode": chain_mode,
                "event_type": "snapshot_captured",
                "status": "SUCCESS",
                "intent_key": "global:SNAPSHOT:CAPTURE",
                "snapshot_role": "pre",
                "snapshot_seq": int(pre_snapshot.get("snapshot_seq", 0) or 0),
                "snapshot_path": pre_snapshot.get("screenshot_path"),
            }
        )
    if perception_provider is not None:
        def _post_context_provider() -> dict[str, Any]:
            post_snapshot = _capture_snapshot(pre=False)
            post_path = post_snapshot.get("screenshot_path")
            if post_path:
                _emit(
                    {
                        "run_id": run_id,
                        "task_id": task_id,
                        "step_id": step_id,
                        "chain_mode": chain_mode,
                        "event_type": "snapshot_captured",
                        "status": "SUCCESS",
                        "intent_key": "global:SNAPSHOT:CAPTURE",
                        "snapshot_role": "post",
                        "snapshot_seq": int(post_snapshot.get("snapshot_seq", 0) or 0),
                        "snapshot_path": post_path,
                    }
                )
            return {
                "perception_infos_post": list(post_snapshot.get("perception_infos", [])),
                "screen_width": int(post_snapshot.get("screen_width", step_context.get("screen_width", 1080))),
                "screen_height": int(post_snapshot.get("screen_height", step_context.get("screen_height", 2340))),
                "keyboard_post": bool(post_snapshot.get("keyboard", False)),
                "screenshot_post": post_path,
            }

        step_context["post_context_provider"] = _post_context_provider
    request_context = {
        "screen_width": int(screen_width),
        "screen_height": int(screen_height),
        "task_type": route_context.get("task_type"),
    }
    request = map_legacy_action_to_request(action_obj, context=request_context)
    fast_match_hint = None
    if blueprint_repo is not None:
        try:
            fast_match_hint = _resolve_blueprint_context(
                blueprint_repo=blueprint_repo,
                request_intent_key=request.intent_key,
                instruction=str(instruction or ""),
                step_context=step_context,
                screen_width=int(step_context.get("screen_width", screen_width)),
                screen_height=int(step_context.get("screen_height", screen_height)),
            )
        except Exception:
            fast_match_hint = None
    topology_result = _build_runtime_topology_result(step_context)
    if topology_result is not None:
        step_context["topology_result"] = topology_result

    resolved_page_hint = str(page_hint or "").strip()
    expected_page_fingerprint_id = str(page_fingerprint_id or "").strip()
    page_hint_threshold = float(page_match_threshold) if page_match_threshold is not None else 0.55
    if resolved_page_hint or expected_page_fingerprint_id:
        page_match_score = _page_hint_match_score(
            resolved_page_hint,
            list(step_context.get("perception_infos_pre", []) or []),
            fast_match_hint,
        )
        fused = _fuse_page_fingerprint_score(
            ocr_fast_score=page_match_score,
            topology_result=topology_result,
        )
        page_fingerprint_score = float(fused.get("page_fingerprint_score", 0.0))
        page_matched = bool(page_fingerprint_score >= page_hint_threshold)
        fingerprint_id_matched = True
        if expected_page_fingerprint_id:
            fingerprint_id_matched = expected_page_fingerprint_id == runtime_page_fingerprint_id
            page_matched = bool(page_matched and fingerprint_id_matched)
        _emit(
            {
                "run_id": run_id,
                "task_id": task_id,
                "step_id": step_id,
                "chain_mode": chain_mode,
                "event_type": "page_hint_gate",
                "status": "SUCCESS" if page_matched else "HANDOVER",
                "intent_key": request.intent_key,
                "page_hint": resolved_page_hint,
                "expected_page_fingerprint_id": expected_page_fingerprint_id,
                "runtime_page_fingerprint_id": runtime_page_fingerprint_id,
                "fingerprint_id_matched": fingerprint_id_matched,
                "fingerprint_match_score": page_match_score,
                "page_fingerprint_score": page_fingerprint_score,
                "page_hint_threshold": page_hint_threshold,
                "matched": page_matched,
                **fused,
                **({"fast_match_hint": fast_match_hint} if fast_match_hint else {}),
            }
        )
        if not page_matched:
            reason_code = "PAGE_HINT_MISMATCH"
            if expected_page_fingerprint_id and not fingerprint_id_matched:
                reason_code = "PAGE_FINGERPRINT_ID_MISMATCH"
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
                    "page_hint": resolved_page_hint,
                    "expected_page_fingerprint_id": expected_page_fingerprint_id,
                    "runtime_page_fingerprint_id": runtime_page_fingerprint_id,
                    "fingerprint_id_matched": fingerprint_id_matched,
                    "fingerprint_match_score": page_match_score,
                    "page_fingerprint_score": page_fingerprint_score,
                    "page_hint_threshold": page_hint_threshold,
                    **fused,
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
                    "recovery_level": "L2",
                    "page_hint": resolved_page_hint,
                    "expected_page_fingerprint_id": expected_page_fingerprint_id,
                    "runtime_page_fingerprint_id": runtime_page_fingerprint_id,
                    "fingerprint_id_matched": fingerprint_id_matched,
                    "fingerprint_match_score": page_match_score,
                    "page_fingerprint_score": page_fingerprint_score,
                    "page_hint_threshold": page_hint_threshold,
                    **fused,
                    **({"fast_match_hint": fast_match_hint} if fast_match_hint else {}),
                }
            )
            return V2ProbeResult(
                status="HANDOVER",
                intent_key=request.intent_key,
                channel="mobile_native",
                route_reason="page_hint_mismatch",
            )

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
    if collapse_to_wait:
        _transition_state(
            ProbeState.HANDOVER,
            "intent_collapsed_to_wait",
            status="HANDOVER",
            route_payload=route_info,
        )
        _emit(
            {
                "run_id": run_id,
                "task_id": task_id,
                "step_id": step_id,
                "chain_mode": chain_mode,
                "event_type": "intent_parse_guard",
                "status": "HANDOVER",
                "intent_key": request.intent_key,
                "reason_code": collapse_reason_code,
                "instruction": str(instruction or ""),
                "parsed_action": dict(action_obj),
                **route_info,
            }
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
                "reason_code": collapse_reason_code,
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
                "assertion_result": {"passed": False, "reason_code": collapse_reason_code},
                "post_check": {"passed": False, "reason_code": collapse_reason_code},
                "recovery_level": "L2",
                "screenshot_pre": step_context.get("screenshot_pre"),
                "screenshot_post": step_context.get("screenshot_post"),
                "action_screenshot": None,
                **route_info,
            }
        )
        _transition_state(
            ProbeState.COMPLETED,
            "handover_complete",
            status="HANDOVER",
            route_payload=route_info,
        )
        return V2ProbeResult(
            status="HANDOVER",
            intent_key=request.intent_key,
            channel=route_info.get("channel", "mobile_native"),
            route_reason=route_info.get("route_reason", "unknown"),
        )

    if topology_result is not None:
        _emit(
            {
                "run_id": run_id,
                "task_id": task_id,
                "step_id": step_id,
                "chain_mode": chain_mode,
                "event_type": "topology_projection",
                "status": "SUCCESS",
                "intent_key": request.intent_key,
                "topology_confidence": topology_result.get("confidence"),
                "core_anchor_confidence": topology_result.get("core_confidence"),
                "aux_anchor_confidence": topology_result.get("aux_confidence"),
                "geometry_confidence": topology_result.get("geometry_confidence"),
                "transform_mode": topology_result.get("transform_mode"),
                "transform_fit_error": topology_result.get("transform_fit_error"),
                "transform_pair_count": topology_result.get("transform_pair_count"),
                "projection_mode": topology_result.get("projection_mode"),
                "projection_guard_reason": topology_result.get("projection_guard_reason"),
                "projection_affine_enabled": topology_result.get("projection_affine_enabled"),
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

    mobile_executor = mobile_executor or MobileDeviceExecutor(
        adb_path=str(adb_path or "adb"),
        execution_mode=str(mobile_execution_mode or "auto"),
        default_wait_ms=int(max(0, mobile_wait_ms)),
        screenshot_log_dir=screenshot_log_dir,
        capture_action_screenshot=bool(capture_action_screenshot),
    )
    pipeline = StepPipeline(hooks=hooks, mobile_executor=mobile_executor)
    registry = build_default_action_registry(pipeline=pipeline, web_skill=web_skill)

    dispatch_name = "web_skill_agent_browser" if route_info.get("channel") == "web_skill" else "mobile_native"
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
                replan_strategy = ""
                replanned_steps: list[WebPlanStep] = []
                if bool(model_settings.enable_web_replan) and str(model_settings.web_replan_model).strip():
                    try:
                        model_replan = build_replan_after_failure_with_model(
                            instruction=instruction,
                            failed_reason=failed_reason,
                            failed_task=dict(plan_step.task),
                            route_context=route_context,
                            remaining_steps=remaining_steps,
                            revision=replan_attempt,
                            model=str(model_settings.web_replan_model),
                            model_type=str(model_settings.api_type or "").strip() or None,
                            api_url=str(model_settings.api_url or "").strip() or None,
                            api_key=str(model_settings.api_key or "").strip() or None,
                            extra_body=model_settings.extra_body,
                            temperature=float(model_settings.temperature),
                        )
                        if model_replan.get("ok", False):
                            replan_strategy = str(model_replan.get("strategy", "model_replan"))
                            replanned_steps = list(model_replan.get("steps", []))
                            _emit(
                                {
                                    "run_id": run_id,
                                    "task_id": task_id,
                                    "step_id": step_id,
                                    "chain_mode": chain_mode,
                                    "event_type": "model_web_replan",
                                    "status": "SUCCESS",
                                    "intent_key": request.intent_key,
                                    "web_plan_id": web_plan_id,
                                    "model_name": str(model_settings.web_replan_model),
                                    "web_replan_attempt": replan_attempt,
                                    "model_replan_strategy": replan_strategy,
                                    "model_replanned_steps_count": len(replanned_steps),
                                    **route_info,
                                }
                            )
                        else:
                            _emit(
                                {
                                    "run_id": run_id,
                                    "task_id": task_id,
                                    "step_id": step_id,
                                    "chain_mode": chain_mode,
                                    "event_type": "model_web_replan",
                                    "status": "FAILED",
                                    "intent_key": request.intent_key,
                                    "web_plan_id": web_plan_id,
                                    "model_name": str(model_settings.web_replan_model),
                                    "web_replan_attempt": replan_attempt,
                                    "reason_code": str(model_replan.get("error", "MODEL_WEB_REPLAN_FAILED")),
                                    **route_info,
                                }
                            )
                    except Exception as exc:
                        _emit(
                            {
                                "run_id": run_id,
                                "task_id": task_id,
                                "step_id": step_id,
                                "chain_mode": chain_mode,
                                "event_type": "model_web_replan",
                                "status": "FAILED",
                                "intent_key": request.intent_key,
                                "web_plan_id": web_plan_id,
                                "model_name": str(model_settings.web_replan_model),
                                "web_replan_attempt": replan_attempt,
                                "reason_code": "MODEL_WEB_REPLAN_EXCEPTION",
                                "error": str(exc),
                                **route_info,
                            }
                        )
                if not replanned_steps:
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
                "mobile_native",
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
        adapter_call = dict(exec_result.get("adapter_call", {}) or {})
        execution_mode = str(adapter_call.get("execution_mode", mobile_execution_mode or "unknown")).lower()
        _emit(
            {
                "run_id": run_id,
                "task_id": task_id,
                "step_id": step_id,
                "chain_mode": chain_mode,
                "event_type": "adapter_call",
                "status": "SUCCESS" if bool(adapter_call.get("success", False)) else "FAILED",
                "intent_key": request.intent_key,
                "adapter_backend": "mobile-device" if execution_mode == "device" else "mobile-shadow",
                "adapter_execution_mode": execution_mode,
                "adapter_device_executed": bool(adapter_call.get("device_executed", False)),
                "adapter_action_name": adapter_call.get("action_name"),
                "screenshot_path": adapter_call.get("screenshot_path"),
                "screenshot_error": adapter_call.get("screenshot_error"),
                "error": adapter_call.get("error"),
                **final_route_info,
            }
        )

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
                        "mobile_native",
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

    if bool(model_settings.enable_assertion_repair) and str(model_settings.assertion_repair_model).strip():
        current_reason = str(assertion_result.get("reason_code", "")).strip().upper()
        complex_reasons = {
            "SKELETON_ASSERTION_FAILED",
            "STRUCTURAL_ASSERTION_FAILED",
            "ASSERTION_MISMATCH",
            "POST_EXPECTATION_MISMATCH",
        }
        if not bool(assertion_result.get("passed", False)) and current_reason in complex_reasons:
            try:
                repair = repair_assertion_with_model(
                    instruction=instruction,
                    action_name=str(action_obj.get("name", "")),
                    assertion_result=assertion_result,
                    post_check=post_check,
                    step_context=step_context,
                    model=str(model_settings.assertion_repair_model),
                    model_type=str(model_settings.api_type or "").strip() or None,
                    api_url=str(model_settings.api_url or "").strip() or None,
                    api_key=str(model_settings.api_key or "").strip() or None,
                    extra_body=model_settings.extra_body,
                    temperature=float(model_settings.temperature),
                )
                decision = str(repair.get("decision", "keep")).lower()
                _emit(
                    {
                        "run_id": run_id,
                        "task_id": task_id,
                        "step_id": step_id,
                        "chain_mode": chain_mode,
                        "event_type": "assertion_repair",
                        "status": "SUCCESS" if repair.get("ok", False) else "FAILED",
                        "intent_key": request.intent_key,
                        "model_name": str(model_settings.assertion_repair_model),
                        "assertion_repair_decision": decision,
                        "assertion_repair_reason": repair.get("reason_code"),
                        "assertion_repair_note": repair.get("note"),
                        **final_route_info,
                    }
                )
                if repair.get("ok", False) and decision == "accept":
                    assertion_result = dict(assertion_result)
                    assertion_result["passed"] = True
                    assertion_result["reason_code"] = str(repair.get("reason_code", "ASSERTION_REPAIRED_ACCEPT"))
                    if bool(post_check.get("passed", False)):
                        status = "SUCCESS"
                        recovery_level = "NONE"
                        exec_result["status"] = "SUCCESS"
                        exec_result["recovery_level"] = "NONE"
                    exec_result["assertion_result"] = assertion_result
            except Exception as exc:
                _emit(
                    {
                        "run_id": run_id,
                        "task_id": task_id,
                        "step_id": step_id,
                        "chain_mode": chain_mode,
                        "event_type": "assertion_repair",
                        "status": "FAILED",
                        "intent_key": request.intent_key,
                        "model_name": str(model_settings.assertion_repair_model),
                        "assertion_repair_decision": "keep",
                        "reason_code": "MODEL_ASSERTION_REPAIR_EXCEPTION",
                        "error": str(exc),
                        **final_route_info,
                    }
                )
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
            **({"fast_match_hint": fast_match_hint} if fast_match_hint else {}),
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
            **({"fast_match_hint": fast_match_hint} if fast_match_hint else {}),
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
                **({"fast_match_hint": fast_match_hint} if fast_match_hint else {}),
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

    effective_context = dict(step_context or {})
    adapter_call_payload = exec_result.get("adapter_call", {})
    if isinstance(adapter_call_payload, dict):
        context_after = adapter_call_payload.get("context")
        if isinstance(context_after, dict):
            effective_context.update(context_after)

    if blueprint_repo is not None and str(final_route_info.get("channel", "")) == "mobile_native":
        replay_gate = dict(replay_gate_config or {})
        replay_gate_enabled = bool(replay_gate.get("enabled", True))
        replay_gate_min_score = _clip01(replay_gate.get("min_score", 0.45))
        replay_gate_min_stable_ratio = _clip01(replay_gate.get("min_stable_ratio", 0.30))
        try:
            replay_gate_min_skeleton_nodes = max(1, int(replay_gate.get("min_skeleton_nodes", 2)))
        except Exception:
            replay_gate_min_skeleton_nodes = 2
        outcome_code = "A"
        if final_status != "SUCCESS":
            assertion_passed = bool(assertion_result.get("passed", False))
            post_check_passed = bool(post_check.get("passed", False))
            if assertion_passed and not post_check_passed:
                outcome_code = "B"
            elif not assertion_passed and post_check_passed:
                outcome_code = "C"
            else:
                outcome_code = "B"
        try:
            sync_payload = upsert_blueprint_from_observation_with_gate(
                repo=blueprint_repo,
                intent_key=request.intent_key,
                screen_width=int(effective_context.get("screen_width", screen_width)),
                screen_height=int(effective_context.get("screen_height", screen_height)),
                perception_infos_pre=list(effective_context.get("perception_infos_pre", [])),
                perception_infos_post=list(effective_context.get("perception_infos_post", [])),
                action_outcome=outcome_code,
                post_check_result=post_check,
                replay_gate_enabled=replay_gate_enabled,
                replay_gate_min_score=replay_gate_min_score,
                replay_gate_min_stable_ratio=replay_gate_min_stable_ratio,
                replay_gate_min_skeleton_nodes=replay_gate_min_skeleton_nodes,
                page_binding={
                    "page_hint": resolved_page_hint,
                    "page_fingerprint_id": expected_page_fingerprint_id,
                    "runtime_page_fingerprint_id": runtime_page_fingerprint_id,
                    "match_threshold": page_hint_threshold,
                    "page_fingerprint_score": (
                        page_fingerprint_score if "page_fingerprint_score" in locals() else 0.0
                    ),
                    "fingerprint_match_score": page_match_score if "page_match_score" in locals() else 0.0,
                    "fingerprint_id_matched": (
                        fingerprint_id_matched if "fingerprint_id_matched" in locals() else False
                    ),
                },
            )
            synced_blueprint = dict(sync_payload.get("blueprint", {}))
            sync_info = dict(sync_payload.get("sync", {}))
            _emit(
                {
                    "run_id": run_id,
                    "task_id": task_id,
                    "step_id": step_id,
                    "chain_mode": chain_mode,
                    "event_type": "blueprint_sync",
                    "status": "SUCCESS",
                    "intent_key": request.intent_key,
                    "blueprint_version": str(synced_blueprint.get("version", "")),
                    "blueprint_sync_mode": str(sync_info.get("sync_mode", "unknown")),
                    "replay_gate_passed": sync_info.get("replay_gate_passed"),
                    "replay_gate_reason": sync_info.get("replay_gate_reason"),
                    "replay_quality_score": sync_info.get("replay_quality_score"),
                    "replay_quality_level": sync_info.get("replay_quality_level"),
                    "replay_gate_enabled_cfg": replay_gate_enabled,
                    "replay_gate_min_score_cfg": replay_gate_min_score,
                    "replay_gate_min_stable_ratio_cfg": replay_gate_min_stable_ratio,
                    "replay_gate_min_skeleton_nodes_cfg": replay_gate_min_skeleton_nodes,
                    "blueprint_changed_fields": list(sync_info.get("changed_fields", [])),
                    "blueprint_suppressed_fields": list(sync_info.get("suppressed_fields", [])),
                    "page_hint": resolved_page_hint,
                    "page_fingerprint_id": expected_page_fingerprint_id,
                    "runtime_page_fingerprint_id": runtime_page_fingerprint_id,
                    **final_route_info,
                    **({"fast_match_hint": fast_match_hint} if fast_match_hint else {}),
                }
            )
        except Exception as exc:
            _emit(
                {
                    "run_id": run_id,
                    "task_id": task_id,
                    "step_id": step_id,
                    "chain_mode": chain_mode,
                    "event_type": "blueprint_sync",
                    "status": "FAILED",
                    "intent_key": request.intent_key,
                    "reason_code": "BLUEPRINT_SYNC_ERROR",
                    "error": str(exc),
                    **final_route_info,
                    **({"fast_match_hint": fast_match_hint} if fast_match_hint else {}),
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
            "screenshot_pre": effective_context.get("screenshot_pre"),
            "screenshot_post": effective_context.get("screenshot_post"),
            "action_screenshot": (
                adapter_call_payload.get("screenshot_path")
                if isinstance(adapter_call_payload, dict)
                else None
            ),
            **final_route_info,
            **({"fast_match_hint": fast_match_hint} if fast_match_hint else {}),
        }
    )

    return V2ProbeResult(
        status=final_status,
        intent_key=request.intent_key,
        channel=str(final_route_info.get("channel", "mobile_native")),
        route_reason=str(final_route_info.get("route_reason", "unknown")),
    )
