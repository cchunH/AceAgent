from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from guiagent_v2.blueprint_hub import Blueprint, BlueprintRepository
from guiagent_v2.state_engine import (
    build_static_skeleton,
    denoise_perception_frames,
    extract_anchors,
)


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
    perception_infos_pre = perception_infos_pre or []
    perception_infos_post = perception_infos_post or []
    post_check_result = post_check_result or {}

    existing = repo.get_blueprint(intent_key, app_state=app_state)
    if existing is None:
        blueprint = Blueprint(
            intent_key=intent_key,
            app_state=app_state,
            reference_screen={"width": int(screen_width), "height": int(screen_height)},
        ).to_dict()
    else:
        blueprint = dict(existing)

    anchors = extract_anchors(
        perception_infos_pre,
        (int(screen_width), int(screen_height)),
        max_anchors=5,
    )
    blueprint["anchors"] = [a.to_dict() for a in anchors]
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
    blueprint["static_skeleton"] = skeleton.to_dict()

    metadata = dict(blueprint.get("metadata", {}))
    metadata["last_outcome"] = action_outcome
    metadata["last_post_check_reason"] = post_check_result.get("reason_code", "UNKNOWN")
    metadata["denoise_stable_ratio"] = round(float(denoise.get("stable_ratio", 0.0)), 4)
    metadata["denoise_frame_count"] = int(denoise.get("frame_count", 1))
    metadata["dynamic_noise_count"] = len(list(denoise.get("dynamic_infos", [])))
    metadata["updated_at"] = _utc_now_iso()
    blueprint["metadata"] = metadata

    if action_outcome == "A" and post_check_result.get("passed", False):
        existing_expectations = list(blueprint.get("post_expectations", []))
        discovered = _collect_post_expectations(perception_infos_post, max_items=2)
        for item in discovered:
            if item not in existing_expectations:
                existing_expectations.append(item)
        blueprint["post_expectations"] = existing_expectations[:5]

    repo.save_blueprint(blueprint)
    return blueprint
