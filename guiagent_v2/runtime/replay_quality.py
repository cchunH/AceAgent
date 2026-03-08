from __future__ import annotations

from typing import Any

from guiagent_v2.state_engine import build_static_skeleton, denoise_perception_frames, extract_anchors


def score_replay_sample(
    *,
    perception_infos_pre: list[dict[str, Any]] | None,
    perception_infos_post: list[dict[str, Any]] | None,
    screen_width: int,
    screen_height: int,
    action_outcome: str,
    post_check_result: dict[str, Any] | None,
    min_score: float = 0.45,
    min_stable_ratio: float = 0.30,
    min_skeleton_nodes: int = 2,
) -> dict[str, Any]:
    pre = list(perception_infos_pre or [])
    post = list(perception_infos_post or [])
    post_check = dict(post_check_result or {})
    screen_size = (int(screen_width), int(screen_height))

    denoise = denoise_perception_frames(
        frames=[pre, post],
        screen_size=screen_size,
        min_presence_ratio=0.5,
        max_items=16,
    )
    stable_ratio = float(denoise.get("stable_ratio", 0.0))

    skeleton = build_static_skeleton(
        frames=[pre, post],
        screen_size=screen_size,
        min_presence_ratio=0.5,
        max_nodes=10,
    )
    node_count = len(list(skeleton.nodes))

    anchors = extract_anchors(pre, screen_size=screen_size, max_anchors=5)
    anchor_count = len(list(anchors))

    outcome = str(action_outcome or "").upper().strip()
    if "A" in outcome:
        outcome_score = 1.0
    elif "B" in outcome:
        outcome_score = 0.5
    elif "C" in outcome:
        outcome_score = 0.2
    else:
        outcome_score = 0.0
    post_passed = bool(post_check.get("passed", False))

    score = (
        0.45 * stable_ratio
        + 0.20 * min(node_count / 6.0, 1.0)
        + 0.15 * min(anchor_count / 4.0, 1.0)
        + 0.10 * outcome_score
        + (0.10 if post_passed else 0.0)
    )
    score = max(0.0, min(float(score), 1.0))

    accepted = (
        score >= float(min_score)
        and stable_ratio >= float(min_stable_ratio)
        and node_count >= int(min_skeleton_nodes)
    )
    if score >= 0.70:
        quality_level = "HIGH"
    elif score >= 0.45:
        quality_level = "MEDIUM"
    else:
        quality_level = "LOW"

    return {
        "accepted": bool(accepted),
        "score": round(score, 4),
        "quality_level": quality_level,
        "stable_ratio": round(stable_ratio, 4),
        "skeleton_nodes": int(node_count),
        "anchor_count": int(anchor_count),
        "post_check_passed": post_passed,
        "outcome": outcome,
    }

