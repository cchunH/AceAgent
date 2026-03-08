from __future__ import annotations

from collections import defaultdict
from typing import Any

from .static_skeleton import extract_skeleton_node_keys


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a.intersection(b))
    union = len(a.union(b))
    if union <= 0:
        return 0.0
    return inter / union


def _relaxed_key(node_key: str) -> str:
    parts = str(node_key or "").split(":")
    if len(parts) >= 5:
        return ":".join(parts[:-2])
    return str(node_key or "")


def build_blueprint_match_index(
    blueprints: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for bp in blueprints or []:
        if not isinstance(bp, dict):
            continue
        app_state = str(bp.get("app_state", "global:DEFAULT")).strip() or "global:DEFAULT"
        intent_key = str(bp.get("intent_key", "")).strip()
        if not intent_key:
            continue
        skeleton = bp.get("static_skeleton")
        node_keys = extract_skeleton_node_keys(skeleton)
        item = {
            "intent_key": intent_key,
            "app_state": app_state,
            "version": str(bp.get("version", "v0.1.0")),
            "skeleton_signature": (
                str((skeleton or {}).get("signature", "")).strip() if isinstance(skeleton, dict) else ""
            ),
            "node_keys": node_keys,
            "node_key_set": set(node_keys),
            "relaxed_key_set": {_relaxed_key(key) for key in node_keys},
            "anchor_count": len(list(bp.get("anchors", []))),
        }
        index[app_state].append(item)
    return dict(index)


def match_blueprint_fast(
    observed_skeleton: dict[str, Any] | None,
    index: dict[str, list[dict[str, Any]]],
    app_state: str = "global:DEFAULT",
    top_k: int = 3,
) -> list[dict[str, Any]]:
    app = str(app_state or "global:DEFAULT").strip() or "global:DEFAULT"
    candidates = list(index.get(app, []))
    if not candidates and app != "global:DEFAULT":
        candidates = list(index.get("global:DEFAULT", []))

    observed_sig = str((observed_skeleton or {}).get("signature", "")).strip()
    observed_keys = set(extract_skeleton_node_keys(observed_skeleton))
    observed_relaxed = {_relaxed_key(key) for key in observed_keys}

    scored: list[dict[str, Any]] = []
    for item in candidates:
        exact_score = _jaccard(observed_keys, set(item.get("node_key_set", set())))
        relaxed_score = _jaccard(observed_relaxed, set(item.get("relaxed_key_set", set())))
        node_score = (exact_score * 0.7) + (relaxed_score * 0.3)
        sig_bonus = 0.2 if observed_sig and observed_sig == str(item.get("skeleton_signature", "")) else 0.0
        score = min(1.0, node_score + sig_bonus)
        scored.append(
            {
                "intent_key": item.get("intent_key"),
                "app_state": item.get("app_state"),
                "version": item.get("version"),
                "score": round(score, 6),
                "node_overlap_score": round(node_score, 6),
                "node_overlap_exact": round(exact_score, 6),
                "node_overlap_relaxed": round(relaxed_score, 6),
                "signature_hit": bool(sig_bonus > 0),
            }
        )
    scored.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    return scored[: max(1, int(top_k))]
