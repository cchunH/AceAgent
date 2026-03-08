from typing import Any

from guiagent_v2.intent_contract import ExecutionRequest
from guiagent_v2.state_engine import (
    build_static_skeleton,
    compare_anchor_sets,
    denoise_perception_frames,
    extract_anchors,
    match_static_skeleton,
)


def _normalize_text(value: str) -> str:
    return value.strip().lower()


def run_post_check(
    request: ExecutionRequest,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = context or {}
    pre_infos = context.get("perception_infos_pre", [])
    post_infos = context.get("perception_infos_post", [])
    width = int(context.get("screen_width", 1080))
    height = int(context.get("screen_height", 2340))
    denoise = denoise_perception_frames(
        frames=[pre_infos, post_infos],
        screen_size=(width, height),
        min_presence_ratio=0.5,
        max_items=24,
    )
    pre_denoise = denoise_perception_frames(
        frames=[pre_infos],
        screen_size=(width, height),
        min_presence_ratio=1.0,
        max_items=24,
    )
    post_denoise = denoise_perception_frames(
        frames=[post_infos],
        screen_size=(width, height),
        min_presence_ratio=1.0,
        max_items=24,
    )
    pre_for_anchor = pre_denoise.get("stable_infos", []) or pre_infos
    post_for_anchor = post_denoise.get("stable_infos", []) or post_infos

    pre_anchors = extract_anchors(pre_for_anchor, (width, height))
    post_anchors = extract_anchors(post_for_anchor, (width, height))
    topo = compare_anchor_sets(pre_anchors, post_anchors)
    pre_skeleton = build_static_skeleton(
        frames=[pre_infos],
        screen_size=(width, height),
        min_presence_ratio=1.0,
        max_nodes=8,
    )
    post_skeleton = build_static_skeleton(
        frames=[post_infos],
        screen_size=(width, height),
        min_presence_ratio=1.0,
        max_nodes=8,
    )
    skeleton_topo = match_static_skeleton(post_skeleton, pre_skeleton)

    post_expectations = context.get("post_expectations", [])
    if post_expectations:
        post_blob = " ".join(
            _normalize_text(str(i.get("text", "")))
            for i in post_infos
            if str(i.get("text", "")).strip() and str(i.get("text", "")).strip() != "icon: None"
        )
        for expected in post_expectations:
            if _normalize_text(str(expected)) not in post_blob:
                return {
                    "passed": False,
                    "reason_code": "POST_EXPECTATION_MISMATCH",
                    "expected": post_expectations,
                    "topology_confidence": topo.confidence,
                    "core_anchor_confidence": topo.core_confidence,
                    "aux_anchor_confidence": topo.aux_confidence,
                    "geometry_confidence": topo.geometry_confidence,
                    "skeleton_confidence": skeleton_topo.confidence,
                }

    effective_no_change = max(
        float(topo.confidence),
        float(skeleton_topo.confidence),
    )
    if effective_no_change >= float(context.get("no_change_confidence", 0.9)):
        return {
            "passed": False,
            "reason_code": "NO_STATE_CHANGE",
            "topology_confidence": topo.confidence,
            "core_anchor_confidence": topo.core_confidence,
            "aux_anchor_confidence": topo.aux_confidence,
            "geometry_confidence": topo.geometry_confidence,
            "skeleton_confidence": skeleton_topo.confidence,
            "denoise_stable_ratio": denoise.get("stable_ratio"),
        }

    return {
        "passed": True,
        "reason_code": "STATE_TRANSITION_OK",
        "topology_confidence": topo.confidence,
        "core_anchor_confidence": topo.core_confidence,
        "aux_anchor_confidence": topo.aux_confidence,
        "geometry_confidence": topo.geometry_confidence,
        "skeleton_confidence": skeleton_topo.confidence,
        "denoise_stable_ratio": denoise.get("stable_ratio"),
    }
