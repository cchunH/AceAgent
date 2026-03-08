from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from guiagent_v2.state_engine.static_skeleton import extract_skeleton_node_keys


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _normalize_anchor(anchor: dict[str, Any]) -> tuple[str, str, int, int]:
    text = str(anchor.get("text", "")).strip().lower()
    zone = str(anchor.get("zone", "middle")).strip().lower() or "middle"
    bbox = dict(anchor.get("norm_bbox", {}) or {})
    x = int(round(_safe_float(bbox.get("x", 0.0), 0.0) * 40))
    y = int(round(_safe_float(bbox.get("y", 0.0), 0.0) * 40))
    return (text, zone, x, y)


def _anchors_changed(existing: list[dict[str, Any]], observed: list[dict[str, Any]]) -> bool:
    left = sorted(_normalize_anchor(item) for item in list(existing or []) if isinstance(item, dict))
    right = sorted(_normalize_anchor(item) for item in list(observed or []) if isinstance(item, dict))
    return left != right


def _skeleton_changed(existing: dict[str, Any] | None, observed: dict[str, Any] | None) -> bool:
    old = dict(existing or {})
    new = dict(observed or {})
    old_sig = str(old.get("signature", "")).strip()
    new_sig = str(new.get("signature", "")).strip()
    if old_sig and new_sig:
        return old_sig != new_sig
    old_keys = sorted(extract_skeleton_node_keys(old))
    new_keys = sorted(extract_skeleton_node_keys(new))
    return old_keys != new_keys


def _merge_expectations(
    existing: list[str] | None,
    discovered: list[str] | None,
    max_items: int = 5,
) -> list[str]:
    values: list[str] = []
    for item in list(existing or []):
        text = str(item).strip()
        if text and text not in values:
            values.append(text)
    for item in list(discovered or []):
        text = str(item).strip()
        if text and text not in values:
            values.append(text)
    return values[: max(1, int(max_items))]


def bump_blueprint_version(version: str | None) -> str:
    raw = str(version or "").strip() or "v0.1.0"
    payload = raw[1:] if raw.startswith("v") else raw
    parts = payload.split(".")
    while len(parts) < 3:
        parts.append("0")
    try:
        major = int(parts[0])
        minor = int(parts[1])
        patch = int(parts[2])
    except Exception:
        return "v0.1.0"
    patch += 1
    return f"v{major}.{minor}.{patch}"


@dataclass
class BlueprintDeltaPlan:
    delta: dict[str, Any]
    changed_fields: list[str]
    suppressed_fields: list[str]
    structural_changed: bool
    next_version: str
    rollback_to: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "delta": dict(self.delta),
            "changed_fields": list(self.changed_fields),
            "suppressed_fields": list(self.suppressed_fields),
            "structural_changed": bool(self.structural_changed),
            "next_version": self.next_version,
            "rollback_to": self.rollback_to,
        }


def plan_blueprint_delta(
    *,
    existing: dict[str, Any],
    observed_anchors: list[dict[str, Any]],
    observed_skeleton: dict[str, Any],
    discovered_expectations: list[str],
    reference_screen: dict[str, int],
    metadata_update: dict[str, Any],
    allow_structural_update: bool,
) -> BlueprintDeltaPlan:
    current_version = str(existing.get("version", "v0.1.0"))
    delta: dict[str, Any] = {}
    changed_fields: list[str] = []
    suppressed_fields: list[str] = []

    prev_reference = dict(existing.get("reference_screen", {}) or {})
    next_reference = {
        "width": int(reference_screen.get("width", prev_reference.get("width", 1080))),
        "height": int(reference_screen.get("height", prev_reference.get("height", 2340))),
    }
    if prev_reference != next_reference:
        if allow_structural_update:
            delta["reference_screen"] = next_reference
            changed_fields.append("reference_screen")
        else:
            suppressed_fields.append("reference_screen")

    prev_anchors = list(existing.get("anchors", []) or [])
    anchors_changed = _anchors_changed(prev_anchors, observed_anchors)
    if anchors_changed:
        if allow_structural_update:
            delta["anchors"] = list(observed_anchors)
            changed_fields.append("anchors")
        else:
            suppressed_fields.append("anchors")

    prev_skeleton = dict(existing.get("static_skeleton", {}) or {})
    skeleton_changed = _skeleton_changed(prev_skeleton, observed_skeleton)
    if skeleton_changed:
        if allow_structural_update:
            delta["static_skeleton"] = dict(observed_skeleton)
            changed_fields.append("static_skeleton")
        else:
            suppressed_fields.append("static_skeleton")

    prev_expect = list(existing.get("post_expectations", []) or [])
    next_expect = _merge_expectations(prev_expect, discovered_expectations, max_items=5)
    if next_expect != prev_expect:
        delta["post_expectations"] = next_expect
        changed_fields.append("post_expectations")

    metadata = dict(existing.get("metadata", {}) or {})
    metadata.update(dict(metadata_update or {}))
    metadata["last_patch_mode"] = "delta"
    metadata["last_patch_changed_fields"] = list(changed_fields)
    metadata["last_patch_suppressed_fields"] = list(suppressed_fields)
    metadata["last_patch_structural_update"] = bool(
        {"anchors", "static_skeleton", "reference_screen"} & set(changed_fields)
    )
    if metadata != dict(existing.get("metadata", {}) or {}):
        delta["metadata"] = metadata

    structural_changed = bool({"anchors", "static_skeleton", "reference_screen"} & set(changed_fields))
    should_bump_version = structural_changed or ("post_expectations" in changed_fields)
    next_version = bump_blueprint_version(current_version) if should_bump_version else current_version
    rollback_to = current_version if should_bump_version else None

    return BlueprintDeltaPlan(
        delta=delta,
        changed_fields=changed_fields,
        suppressed_fields=suppressed_fields,
        structural_changed=structural_changed,
        next_version=next_version,
        rollback_to=rollback_to,
    )

