from typing import Any

from guiagent_v2.intent_contract import ExecutionRequest
from guiagent_v2.state_engine import compare_anchor_sets, extract_anchors


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

    pre_anchors = extract_anchors(pre_infos, (width, height))
    post_anchors = extract_anchors(post_infos, (width, height))
    topo = compare_anchor_sets(pre_anchors, post_anchors)

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
                }

    if topo.confidence >= float(context.get("no_change_confidence", 0.9)):
        return {
            "passed": False,
            "reason_code": "NO_STATE_CHANGE",
            "topology_confidence": topo.confidence,
        }

    return {
        "passed": True,
        "reason_code": "STATE_TRANSITION_OK",
        "topology_confidence": topo.confidence,
    }

