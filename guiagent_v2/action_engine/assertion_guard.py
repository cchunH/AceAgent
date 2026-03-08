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
    action_name = str((request.action or {}).get("name", "")).strip().lower()
    mobile_execution_mode = str(context.get("mobile_execution_mode", "")).strip().lower()

    topo = None
    expected_anchors = context.get("expected_anchors")
    if expected_anchors:
        topo = match_topology(observed_anchors, expected_anchors)
        if topo.confidence < float(context.get("topology_threshold", 0.6)):
            return {
                "passed": False,
                "reason_code": "STRUCTURAL_ASSERTION_FAILED",
                "topology_confidence": topo.confidence,
                "core_anchor_confidence": topo.core_confidence,
                "aux_anchor_confidence": topo.aux_confidence,
                "geometry_confidence": topo.geometry_confidence,
                "matched_core": topo.matched_core,
                "matched_aux": topo.matched_aux,
                "total_core": topo.total_core,
                "total_aux": topo.total_aux,
                "matched": topo.matched,
                "total_expected": topo.total_expected,
                "denoise_stable_ratio": denoise.get("stable_ratio"),
                "transform_mode": topo.transform_mode,
                "affine_norm": topo.affine_norm,
                "transform_fit_error": topo.transform_fit_error,
                "transform_pair_count": topo.transform_pair_count,
            }

    expected_skeleton = context.get("expected_skeleton")
    skeleton_match = None
    if expected_skeleton:
        skeleton_match = match_static_skeleton(observed_skeleton, expected_skeleton)
        skeleton_threshold = float(context.get("skeleton_threshold", 0.55))
        if skeleton_match.confidence < skeleton_threshold:
            # Shadow baseline commonly uses synthetic/noisy snapshots around navigation actions.
            # Relax skeleton assertion for back/home in shadow mode to avoid false-positive handovers.
            allow_shadow_navigation_soften = bool(
                context.get("allow_navigation_shadow_soften", True)
            )
            if (
                allow_shadow_navigation_soften
                and mobile_execution_mode == "shadow"
                and action_name in {"back", "home", "wait"}
            ):
                pass
            else:
                return {
                    "passed": False,
                    "reason_code": "SKELETON_ASSERTION_FAILED",
                    "skeleton_confidence": skeleton_match.confidence,
                    "matched": skeleton_match.matched,
                    "total_expected": skeleton_match.total_expected,
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
        "core_anchor_confidence": topo.core_confidence if topo is not None else 1.0,
        "aux_anchor_confidence": topo.aux_confidence if topo is not None else 1.0,
        "geometry_confidence": topo.geometry_confidence if topo is not None else 1.0,
        "matched_core": topo.matched_core if topo is not None else 0,
        "matched_aux": topo.matched_aux if topo is not None else 0,
        "total_core": topo.total_core if topo is not None else 0,
        "total_aux": topo.total_aux if topo is not None else 0,
        "transform_mode": topo.transform_mode if topo is not None else "identity",
        "affine_norm": topo.affine_norm if topo is not None else {},
        "transform_fit_error": topo.transform_fit_error if topo is not None else 0.0,
        "transform_pair_count": topo.transform_pair_count if topo is not None else 0,
        "denoise_stable_ratio": denoise.get("stable_ratio"),
        "skeleton_confidence": (
            skeleton_match.confidence if skeleton_match is not None else 1.0
        ),
        "skeleton_matched": (
            skeleton_match.matched if skeleton_match is not None else 0
        ),
        "skeleton_total_expected": (
            skeleton_match.total_expected if skeleton_match is not None else 0
        ),
        "skeleton_signature": observed_skeleton.signature,
    }
