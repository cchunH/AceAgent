from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from guiagent_v2.blueprint_hub import Blueprint, BlueprintPatch, BlueprintRepository
from guiagent_v2.state_engine import (
    build_static_skeleton,
    denoise_perception_frames,
    extract_anchors,
)
from .blueprint_delta import plan_blueprint_delta
from .replay_quality import score_replay_sample


_REPLAY_GATE_DEFAULT_MIN_SCORE = 0.45
_REPLAY_GATE_DEFAULT_MIN_STABLE_RATIO = 0.30
_REPLAY_GATE_DEFAULT_MIN_SKELETON_NODES = 2


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _collect_post_expectations(
    perception_infos_post: list[dict[str, Any]],
    max_items: int = 3,
) -> list[str]:
    values: list[str] = []
    for info in perception_infos_post:
        text = str(info.get("text", "")).strip()
        if not text or text == "icon: None":
            continue
        if text not in values:
            values.append(text)
        if len(values) >= max_items:
            break
    return values


def upsert_blueprint_from_observation(
    repo: BlueprintRepository,
    intent_key: str,
    screen_width: int,
    screen_height: int,
    perception_infos_pre: list[dict[str, Any]] | None = None,
    perception_infos_post: list[dict[str, Any]] | None = None,
    action_outcome: str = "UNKNOWN",
    post_check_result: dict[str, Any] | None = None,
    app_state: str = "global:DEFAULT",
) -> dict[str, Any]:
    result = upsert_blueprint_from_observation_with_gate(
        repo=repo,
        intent_key=intent_key,
        screen_width=screen_width,
        screen_height=screen_height,
        perception_infos_pre=perception_infos_pre,
        perception_infos_post=perception_infos_post,
        action_outcome=action_outcome,
        post_check_result=post_check_result,
        app_state=app_state,
    )
    return dict(result.get("blueprint", {}))


def _resolve_replay_gate_reason(
    quality: dict[str, Any],
    *,
    min_score: float,
    min_stable_ratio: float,
    min_skeleton_nodes: int,
) -> str:
    if bool(quality.get("accepted", False)):
        return "REPLAY_GATE_PASS"
    score = float(quality.get("score", 0.0) or 0.0)
    stable_ratio = float(quality.get("stable_ratio", 0.0) or 0.0)
    skeleton_nodes = int(quality.get("skeleton_nodes", 0) or 0)
    if score < float(min_score):
        return "REPLAY_SCORE_LOW"
    if stable_ratio < float(min_stable_ratio):
        return "REPLAY_STABLE_RATIO_LOW"
    if skeleton_nodes < int(min_skeleton_nodes):
        return "REPLAY_SKELETON_LOW"
    return "REPLAY_GATE_REJECTED"


def upsert_blueprint_from_observation_with_gate(
    repo: BlueprintRepository,
    intent_key: str,
    screen_width: int,
    screen_height: int,
    perception_infos_pre: list[dict[str, Any]] | None = None,
    perception_infos_post: list[dict[str, Any]] | None = None,
    action_outcome: str = "UNKNOWN",
    post_check_result: dict[str, Any] | None = None,
    app_state: str = "global:DEFAULT",
    replay_gate_enabled: bool = True,
    replay_gate_min_score: float = _REPLAY_GATE_DEFAULT_MIN_SCORE,
    replay_gate_min_stable_ratio: float = _REPLAY_GATE_DEFAULT_MIN_STABLE_RATIO,
    replay_gate_min_skeleton_nodes: int = _REPLAY_GATE_DEFAULT_MIN_SKELETON_NODES,
) -> dict[str, Any]:
    perception_infos_pre = perception_infos_pre or []
    perception_infos_post = perception_infos_post or []
    post_check_result = post_check_result or {}

    existing = repo.get_blueprint(intent_key, app_state=app_state)
    anchors = extract_anchors(
        perception_infos_pre,
        (int(screen_width), int(screen_height)),
        max_anchors=5,
    )
    anchor_dicts = [a.to_dict() for a in anchors]
    denoise = denoise_perception_frames(
        frames=[perception_infos_pre, perception_infos_post],
        screen_size=(int(screen_width), int(screen_height)),
        min_presence_ratio=0.5,
        max_items=12,
    )
    skeleton = build_static_skeleton(
        frames=[perception_infos_pre, perception_infos_post],
        screen_size=(int(screen_width), int(screen_height)),
        min_presence_ratio=0.5,
        max_nodes=8,
    )
    skeleton_dict = skeleton.to_dict()
    replay_quality = score_replay_sample(
        perception_infos_pre=perception_infos_pre,
        perception_infos_post=perception_infos_post,
        screen_width=int(screen_width),
        screen_height=int(screen_height),
        action_outcome=action_outcome,
        post_check_result=post_check_result,
        min_score=float(replay_gate_min_score),
        min_stable_ratio=float(replay_gate_min_stable_ratio),
        min_skeleton_nodes=int(replay_gate_min_skeleton_nodes),
    )
    replay_gate_passed = bool(replay_quality.get("accepted", False)) if replay_gate_enabled else True
    replay_gate_reason = (
        _resolve_replay_gate_reason(
            replay_quality,
            min_score=float(replay_gate_min_score),
            min_stable_ratio=float(replay_gate_min_stable_ratio),
            min_skeleton_nodes=int(replay_gate_min_skeleton_nodes),
        )
        if replay_gate_enabled
        else "REPLAY_GATE_DISABLED"
    )
    metadata_update = {
        "last_outcome": action_outcome,
        "last_post_check_reason": post_check_result.get("reason_code", "UNKNOWN"),
        "denoise_stable_ratio": round(float(denoise.get("stable_ratio", 0.0)), 4),
        "denoise_frame_count": int(denoise.get("frame_count", 1)),
        "dynamic_noise_count": len(list(denoise.get("dynamic_infos", []))),
        "replay_quality_score": float(replay_quality.get("score", 0.0) or 0.0),
        "replay_quality_level": str(replay_quality.get("quality_level", "LOW")),
        "replay_gate_passed": bool(replay_gate_passed),
        "replay_gate_reason": replay_gate_reason,
        "replay_gate_enabled": bool(replay_gate_enabled),
        "replay_gate_min_score": float(replay_gate_min_score),
        "replay_gate_min_stable_ratio": float(replay_gate_min_stable_ratio),
        "replay_gate_min_skeleton_nodes": int(replay_gate_min_skeleton_nodes),
        "updated_at": _utc_now_iso(),
    }
    structural_candidate = bool(
        action_outcome == "A"
        and post_check_result.get("passed", False)
        and float(denoise.get("stable_ratio", 0.0)) >= 0.35
    )
    allow_structural_update = bool(structural_candidate and replay_gate_passed)
    discovered = (
        _collect_post_expectations(perception_infos_post, max_items=2)
        if allow_structural_update
        else []
    )

    if existing is None:
        blueprint = Blueprint(
            intent_key=intent_key,
            app_state=app_state,
            reference_screen={"width": int(screen_width), "height": int(screen_height)},
        ).to_dict()
        if allow_structural_update:
            blueprint["anchors"] = anchor_dicts
            blueprint["static_skeleton"] = skeleton_dict
        metadata = dict(blueprint.get("metadata", {}))
        metadata.update(metadata_update)
        if allow_structural_update:
            metadata["last_patch_mode"] = "full_create"
            metadata["last_patch_changed_fields"] = ["reference_screen", "anchors", "static_skeleton"]
            metadata["last_patch_suppressed_fields"] = []
            metadata["last_patch_structural_update"] = True
            sync_mode = "full_create"
            changed_fields = ["reference_screen", "anchors", "static_skeleton"]
            suppressed_fields: list[str] = []
        else:
            metadata["last_patch_mode"] = "metadata_only_create"
            metadata["last_patch_changed_fields"] = ["metadata"]
            metadata["last_patch_suppressed_fields"] = ["reference_screen", "anchors", "static_skeleton"]
            metadata["last_patch_structural_update"] = False
            sync_mode = "metadata_only_create"
            changed_fields = ["metadata"]
            suppressed_fields = ["reference_screen", "anchors", "static_skeleton"]
        blueprint["metadata"] = metadata
        if discovered:
            existing_expectations = list(blueprint.get("post_expectations", []))
            for item in discovered:
                if item not in existing_expectations:
                    existing_expectations.append(item)
            blueprint["post_expectations"] = existing_expectations[:5]
        repo.save_blueprint(blueprint)
        return {
            "blueprint": blueprint,
            "sync": {
                "status": "SUCCESS",
                "sync_mode": sync_mode,
                "candidate_structural_update": bool(structural_candidate),
                "allow_structural_update": bool(allow_structural_update),
                "changed_fields": changed_fields,
                "suppressed_fields": suppressed_fields,
                "replay_gate_passed": bool(replay_gate_passed),
                "replay_gate_reason": replay_gate_reason,
                "replay_quality_score": float(replay_quality.get("score", 0.0) or 0.0),
                "replay_quality_level": str(replay_quality.get("quality_level", "LOW")),
                "replay_quality": dict(replay_quality),
            },
        }

    plan = plan_blueprint_delta(
        existing=dict(existing),
        observed_anchors=anchor_dicts,
        observed_skeleton=skeleton_dict,
        discovered_expectations=discovered,
        reference_screen={"width": int(screen_width), "height": int(screen_height)},
        metadata_update=metadata_update,
        allow_structural_update=allow_structural_update,
    )
    if not plan.delta:
        return {
            "blueprint": dict(existing),
            "sync": {
                "status": "NOOP",
                "sync_mode": "no_change",
                "candidate_structural_update": bool(structural_candidate),
                "allow_structural_update": bool(allow_structural_update),
                "changed_fields": [],
                "suppressed_fields": list(plan.suppressed_fields),
                "replay_gate_passed": bool(replay_gate_passed),
                "replay_gate_reason": replay_gate_reason,
                "replay_quality_score": float(replay_quality.get("score", 0.0) or 0.0),
                "replay_quality_level": str(replay_quality.get("quality_level", "LOW")),
                "replay_quality": dict(replay_quality),
            },
        }

    patch = BlueprintPatch(
        target_intent_key=intent_key,
        target_state=app_state,
        version=plan.next_version,
        delta=plan.delta,
        rollback_to=plan.rollback_to,
    )
    patch_result = repo.apply_patch(patch)
    if str(patch_result.get("status")) != "SUCCESS":
        fallback = dict(existing)
        fallback.update(plan.delta)
        fallback["version"] = plan.next_version
        repo.save_blueprint(fallback)
        return {
            "blueprint": fallback,
            "sync": {
                "status": "SUCCESS",
                "sync_mode": "fallback_save",
                "candidate_structural_update": bool(structural_candidate),
                "allow_structural_update": bool(allow_structural_update),
                "changed_fields": list(plan.changed_fields),
                "suppressed_fields": list(plan.suppressed_fields),
                "replay_gate_passed": bool(replay_gate_passed),
                "replay_gate_reason": replay_gate_reason,
                "replay_quality_score": float(replay_quality.get("score", 0.0) or 0.0),
                "replay_quality_level": str(replay_quality.get("quality_level", "LOW")),
                "replay_quality": dict(replay_quality),
            },
        }
    updated = repo.get_blueprint(intent_key, app_state=app_state) or dict(existing)
    sync_mode = "delta" if bool(plan.structural_changed) else "metadata_only_delta"
    return {
        "blueprint": updated,
        "sync": {
            "status": "SUCCESS",
            "sync_mode": sync_mode,
            "candidate_structural_update": bool(structural_candidate),
            "allow_structural_update": bool(allow_structural_update),
            "changed_fields": list(plan.changed_fields),
            "suppressed_fields": list(plan.suppressed_fields),
            "replay_gate_passed": bool(replay_gate_passed),
            "replay_gate_reason": replay_gate_reason,
            "replay_quality_score": float(replay_quality.get("score", 0.0) or 0.0),
            "replay_quality_level": str(replay_quality.get("quality_level", "LOW")),
            "replay_quality": dict(replay_quality),
        },
    }
