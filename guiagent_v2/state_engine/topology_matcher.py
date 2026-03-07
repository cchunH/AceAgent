from typing import Any

from .types import AnchorNode, TopologyMatchResult


def _norm_text(text: str) -> str:
    return text.strip().lower()


def _as_anchor_dict(anchor: AnchorNode | dict[str, Any]) -> dict[str, Any]:
    if isinstance(anchor, AnchorNode):
        return anchor.to_dict()
    return anchor


def _text_match(expected: str, observed: str) -> bool:
    e = _norm_text(expected)
    o = _norm_text(observed)
    if not e or not o:
        return False
    return e in o or o in e


def _distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    ax = float(a.get("norm_bbox", {}).get("x", 0.0))
    ay = float(a.get("norm_bbox", {}).get("y", 0.0))
    bx = float(b.get("norm_bbox", {}).get("x", 0.0))
    by = float(b.get("norm_bbox", {}).get("y", 0.0))
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def match_topology(
    observed_anchors: list[AnchorNode | dict[str, Any]],
    expected_anchors: list[AnchorNode | dict[str, Any]],
    distance_threshold: float = 0.15,
) -> TopologyMatchResult:
    if not expected_anchors:
        return TopologyMatchResult(
            matched=0,
            total_expected=0,
            confidence=1.0,
            matched_anchor_ids=[],
            reason_code="NO_EXPECTED_ANCHORS",
        )

    observed = [_as_anchor_dict(a) for a in observed_anchors]
    expected = [_as_anchor_dict(a) for a in expected_anchors]

    matched_ids: list[str] = []
    matched = 0
    for exp in expected:
        exp_text = str(exp.get("text", "")).strip()
        best = None
        for obs in observed:
            obs_text = str(obs.get("text", "")).strip()
            if exp_text and not _text_match(exp_text, obs_text):
                continue
            dist = _distance(exp, obs)
            if best is None or dist < best[0]:
                best = (dist, obs)

        if best and best[0] <= distance_threshold:
            matched += 1
            matched_ids.append(str(best[1].get("id", "")))

    confidence = matched / max(1, len(expected))
    reason_code = "TOPOLOGY_MATCH_OK" if confidence >= 0.6 else "TOPOLOGY_MISMATCH"
    return TopologyMatchResult(
        matched=matched,
        total_expected=len(expected),
        confidence=confidence,
        matched_anchor_ids=matched_ids,
        reason_code=reason_code,
    )


def compare_anchor_sets(
    pre_anchors: list[AnchorNode | dict[str, Any]],
    post_anchors: list[AnchorNode | dict[str, Any]],
) -> TopologyMatchResult:
    return match_topology(observed_anchors=post_anchors, expected_anchors=pre_anchors)

