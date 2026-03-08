from __future__ import annotations

import hashlib
from typing import Any

from .anchor_extractor import extract_anchors
from .scene_denoise import denoise_perception_frames
from .types import SkeletonMatchResult, StaticSkeleton


def _node_key(node: dict[str, Any]) -> str:
    text = str(node.get("text", "")).strip().lower()
    zone = str(node.get("zone", "middle")).strip().lower() or "middle"
    bbox = node.get("norm_bbox", {}) or {}
    x = float(bbox.get("x", 0.0))
    y = float(bbox.get("y", 0.0))
    qx = int(round(x * 40))
    qy = int(round(y * 40))
    node_type = str(node.get("type", "TEXT")).strip().upper() or "TEXT"
    if text:
        return f"{node_type}:{text}:{zone}:{qx}:{qy}"
    return f"{node_type}:{zone}:{qx}:{qy}"


def _signature(keys: list[str]) -> str:
    payload = "|".join(sorted(keys))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def _dynamic_slots(dynamic_infos: list[dict[str, Any]], screen_size: tuple[int, int], max_slots: int = 6) -> list[dict[str, Any]]:
    width = max(1.0, float(int(screen_size[0])))
    height = max(1.0, float(int(screen_size[1])))
    slots: list[dict[str, Any]] = []
    for item in dynamic_infos or []:
        if not isinstance(item, dict):
            continue
        coords = item.get("coordinates")
        if not isinstance(coords, (list, tuple)) or len(coords) < 2:
            continue
        x = float(coords[0])
        y = float(coords[1])
        text = str(item.get("text", "")).strip()
        zone = "middle"
        ratio = y / height if height > 0 else 0.5
        if ratio <= 0.15:
            zone = "top"
        elif ratio >= 0.85:
            zone = "bottom"
        slot_key = f"{zone}:{text.lower()}" if text else f"{zone}:icon"
        slots.append(
            {
                "key": slot_key,
                "zone": zone,
                "text": text,
                "norm_pos": {
                    "x": round(max(0.0, min(1.0, x / width)), 4),
                    "y": round(max(0.0, min(1.0, y / height)), 4),
                },
                "stability": float(item.get("_stability", 0.0)),
            }
        )
    slots.sort(key=lambda item: item.get("stability", 0.0))
    return slots[: max(1, int(max_slots))]


def build_static_skeleton(
    frames: list[list[dict[str, Any]]],
    screen_size: tuple[int, int],
    min_presence_ratio: float = 0.6,
    max_nodes: int = 12,
) -> StaticSkeleton:
    denoised = denoise_perception_frames(
        frames=frames,
        screen_size=screen_size,
        min_presence_ratio=min_presence_ratio,
        max_items=max_nodes * 2,
    )
    stable_infos = denoised.get("stable_infos", [])
    dynamic_infos = denoised.get("dynamic_infos", [])
    anchors = extract_anchors(stable_infos, screen_size, max_anchors=max_nodes)
    nodes = [a.to_dict() for a in anchors]
    keys = [_node_key(node) for node in nodes]
    return StaticSkeleton(
        nodes=nodes,
        signature=_signature(keys),
        stable_ratio=float(denoised.get("stable_ratio", 0.0)),
        frame_count=int(denoised.get("frame_count", 1)),
        sample_count=len(stable_infos),
        dynamic_slots=_dynamic_slots(dynamic_infos, screen_size=screen_size, max_slots=min(6, max_nodes)),
    )


def extract_skeleton_node_keys(skeleton: dict[str, Any] | StaticSkeleton | None) -> list[str]:
    if skeleton is None:
        return []
    if isinstance(skeleton, StaticSkeleton):
        nodes = skeleton.nodes
    else:
        nodes = list((skeleton or {}).get("nodes", []))
    keys = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        keys.append(_node_key(node))
    return keys


def match_static_skeleton(
    observed: dict[str, Any] | StaticSkeleton | None,
    expected: dict[str, Any] | StaticSkeleton | None,
) -> SkeletonMatchResult:
    observed_keys = set(extract_skeleton_node_keys(observed))
    expected_keys = set(extract_skeleton_node_keys(expected))
    if not expected_keys:
        return SkeletonMatchResult(
            matched=0,
            total_expected=0,
            confidence=1.0,
            reason_code="NO_EXPECTED_SKELETON",
            matched_node_keys=[],
        )
    matched = sorted(observed_keys.intersection(expected_keys))
    confidence = len(matched) / max(1, len(expected_keys))
    reason = "SKELETON_MATCH_OK" if confidence >= 0.6 else "SKELETON_MISMATCH"
    return SkeletonMatchResult(
        matched=len(matched),
        total_expected=len(expected_keys),
        confidence=confidence,
        reason_code=reason,
        matched_node_keys=matched,
    )
