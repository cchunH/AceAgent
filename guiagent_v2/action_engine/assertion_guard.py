from typing import Any

from guiagent_v2.intent_contract import ExecutionRequest
from guiagent_v2.state_engine import (
    build_static_skeleton,
    denoise_perception_frames,
    extract_anchors,
    match_static_skeleton,
    match_topology,
)


def _normalize_text(value: str) -> str:
    return value.strip().lower()


def _join_texts(perception_infos: list[dict[str, Any]]) -> str:
    texts: list[str] = []
    for info in perception_infos:
        text = str(info.get("text", "")).strip()
        if text and text != "icon: None":
            texts.append(_normalize_text(text))
    return " ".join(texts)


def run_pre_assertion(
    request: ExecutionRequest,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = context or {}
    pre_infos = context.get("perception_infos_pre", [])
    width = int(context.get("screen_width", 1080))
    height = int(context.get("screen_height", 2340))
    denoise = denoise_perception_frames(
        frames=[pre_infos],
        screen_size=(width, height),
        min_presence_ratio=1.0,
        max_items=24,
    )
    stable_pre_infos = denoise.get("stable_infos", []) or pre_infos
    observed_anchors = extract_anchors(stable_pre_infos, (width, height))
    observed_skeleton = build_static_skeleton(
        frames=[stable_pre_infos],
        screen_size=(width, height),
        min_presence_ratio=1.0,
        max_nodes=8,
    )

    expected_anchors = context.get("expected_anchors")
    if expected_anchors:
        topo = match_topology(observed_anchors, expected_anchors)
        if topo.confidence < float(context.get("topology_threshold", 0.6)):
            return {
                "passed": False,
                "reason_code": "STRUCTURAL_ASSERTION_FAILED",
                "topology_confidence": topo.confidence,
                "matched": topo.matched,
                "total_expected": topo.total_expected,
                "denoise_stable_ratio": denoise.get("stable_ratio"),
            }

    expected_skeleton = context.get("expected_skeleton")
    if expected_skeleton:
        sk = match_static_skeleton(observed_skeleton, expected_skeleton)
        if sk.confidence < float(context.get("skeleton_threshold", 0.55)):
            return {
                "passed": False,
                "reason_code": "SKELETON_ASSERTION_FAILED",
                "skeleton_confidence": sk.confidence,
                "matched": sk.matched,
                "total_expected": sk.total_expected,
                "denoise_stable_ratio": denoise.get("stable_ratio"),
            }

    expected_semantics = request.assertion.expected_semantics or []
    if expected_semantics:
        blob = _join_texts(pre_infos)
        for semantic in expected_semantics:
            if _normalize_text(str(semantic)) in blob:
                break
        else:
            return {
                "passed": False,
                "reason_code": "ASSERTION_MISMATCH",
                "expected_semantics": expected_semantics,
            }

    return {
        "passed": True,
        "reason_code": "OK",
        "denoise_stable_ratio": denoise.get("stable_ratio"),
        "skeleton_signature": observed_skeleton.signature,
    }
