from typing import Any

from .types import AnchorNode, TopologyMatchResult


def _norm_text(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


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


def _text_score(expected: str, observed: str) -> float:
    e = _norm_text(expected)
    o = _norm_text(observed)
    if not e and not o:
        return 0.6
    if not e or not o:
        return 0.0
    if e == o:
        return 1.0
    if _text_match(e, o):
        return 0.9
    e_tokens = set(e.split())
    o_tokens = set(o.split())
    if not e_tokens or not o_tokens:
        return 0.0
    overlap = len(e_tokens.intersection(o_tokens))
    union = len(e_tokens.union(o_tokens))
    if union <= 0:
        return 0.0
    return max(0.0, min(1.0, overlap / union))


def _distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    ax = float(a.get("norm_bbox", {}).get("x", 0.0))
    ay = float(a.get("norm_bbox", {}).get("y", 0.0))
    bx = float(b.get("norm_bbox", {}).get("x", 0.0))
    by = float(b.get("norm_bbox", {}).get("y", 0.0))
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _distance_score(dist: float, threshold: float) -> float:
    t = max(1e-6, float(threshold))
    if dist <= t:
        return max(0.0, 1.0 - (dist / t))
    if dist <= t * 1.6:
        return max(0.0, 0.2 * (1.0 - ((dist - t) / (t * 0.6))))
    return 0.0


def _zone_score(expected_zone: str, observed_zone: str) -> float:
    e = str(expected_zone or "").strip().lower()
    o = str(observed_zone or "").strip().lower()
    if not e and not o:
        return 0.6
    if not e or not o:
        return 0.4
    return 1.0 if e == o else 0.0


def _role_score(expected_role: str, observed_role: str) -> float:
    e = str(expected_role or "").strip().upper()
    o = str(observed_role or "").strip().upper()
    if not e and not o:
        return 0.6
    if not e or not o:
        return 0.5
    return 1.0 if e == o else 0.0


def _expected_weight(expected_anchor: dict[str, Any]) -> float:
    role = str(expected_anchor.get("role", "")).strip().upper()
    zone = str(expected_anchor.get("zone", "")).strip().lower()
    text = _norm_text(str(expected_anchor.get("text", "")))
    weight = 0.8
    if role == "CORE":
        weight += 0.7
    elif role == "AUXILIARY":
        weight += 0.0
    if zone in {"top", "bottom"}:
        weight += 0.1
    if not text:
        weight *= 0.8
    return max(0.4, weight)


def _pair_score(
    expected_anchor: dict[str, Any],
    observed_anchor: dict[str, Any],
    distance_threshold: float,
) -> float:
    text_score = _text_score(
        str(expected_anchor.get("text", "")),
        str(observed_anchor.get("text", "")),
    )
    dist = _distance(expected_anchor, observed_anchor)
    dist_score = _distance_score(dist, distance_threshold)
    zone_score = _zone_score(
        str(expected_anchor.get("zone", "")),
        str(observed_anchor.get("zone", "")),
    )
    role_score = _role_score(
        str(expected_anchor.get("role", "")),
        str(observed_anchor.get("role", "")),
    )
    meta_score = (zone_score * 0.6) + (role_score * 0.4)
    score = (text_score * 0.55) + (dist_score * 0.35) + (meta_score * 0.10)
    return max(0.0, min(1.0, score))


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
    expected_weighted = sorted(
        [(_expected_weight(item), item) for item in expected],
        key=lambda x: x[0],
        reverse=True,
    )

    matched_ids: list[str] = []
    matched = 0
    weighted_sum = 0.0
    total_weight = max(1e-6, sum(weight for weight, _ in expected_weighted))
    used_observed_ids: set[str] = set()

    for weight, exp in expected_weighted:
        best: tuple[float, dict[str, Any]] | None = None
        for obs in observed:
            obs_id = str(obs.get("id", ""))
            if obs_id and obs_id in used_observed_ids:
                continue
            pair = _pair_score(exp, obs, distance_threshold=distance_threshold)
            if best is None or pair > best[0]:
                best = (pair, obs)

        if best and best[0] >= 0.45:
            matched += 1
            weighted_sum += weight * best[0]
            obs_id = str(best[1].get("id", ""))
            matched_ids.append(obs_id)
            if obs_id:
                used_observed_ids.add(obs_id)

    confidence = weighted_sum / total_weight
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
