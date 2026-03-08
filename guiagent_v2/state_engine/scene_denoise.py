from __future__ import annotations

from collections import defaultdict
from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text == "icon: None":
        return ""
    return text


def _extract_xy(info: dict[str, Any]) -> tuple[float, float] | None:
    coords = info.get("coordinates")
    if isinstance(coords, (tuple, list)) and len(coords) >= 2:
        return _safe_float(coords[0]), _safe_float(coords[1])
    if isinstance(coords, dict):
        return _safe_float(coords.get("x")), _safe_float(coords.get("y"))
    return None


def _zone(y: float, height: float) -> str:
    if height <= 0:
        return "middle"
    ratio = y / height
    if ratio <= 0.15:
        return "top"
    if ratio >= 0.85:
        return "bottom"
    return "middle"


def _quantize_norm(value: float, max_value: float, bins: int = 40) -> int:
    if max_value <= 0:
        return 0
    ratio = max(0.0, min(1.0, value / max_value))
    return int(round(ratio * bins))


def _feature_key(info: dict[str, Any], width: float, height: float) -> str | None:
    xy = _extract_xy(info)
    if xy is None:
        return None
    x, y = xy
    text = _normalize_text(info.get("text"))
    qx = _quantize_norm(x, width)
    qy = _quantize_norm(y, height)
    area = _zone(y, height)
    if text:
        return f"T:{text.lower()}:{area}:{qx}:{qy}"
    return f"I:{area}:{qx}:{qy}"


def denoise_perception_frames(
    frames: list[list[dict[str, Any]]],
    screen_size: tuple[int, int],
    min_presence_ratio: float = 0.6,
    max_items: int = 32,
) -> dict[str, Any]:
    """Extract stable items by voting over adjacent frames."""
    width = max(1.0, float(int(screen_size[0])))
    height = max(1.0, float(int(screen_size[1])))
    min_ratio = max(0.1, min(1.0, float(min_presence_ratio)))
    normalized_frames: list[list[dict[str, Any]]] = [list(frame or []) for frame in (frames or [])]
    frame_count = max(1, len(normalized_frames))

    freq: dict[str, int] = defaultdict(int)
    sample: dict[str, dict[str, Any]] = {}

    for frame in normalized_frames:
        seen_in_frame: set[str] = set()
        for item in frame:
            if not isinstance(item, dict):
                continue
            key = _feature_key(item, width, height)
            if not key or key in seen_in_frame:
                continue
            seen_in_frame.add(key)
            freq[key] += 1
            sample.setdefault(key, dict(item))

    stable: list[dict[str, Any]] = []
    dynamic: list[dict[str, Any]] = []
    for key, count in sorted(freq.items(), key=lambda x: x[1], reverse=True):
        ratio = count / frame_count
        item = dict(sample.get(key, {}))
        item["_stability"] = round(ratio, 4)
        item["_feature_key"] = key
        if ratio >= min_ratio:
            stable.append(item)
        else:
            dynamic.append(item)

    stable = stable[: max(1, int(max_items))]
    dynamic = dynamic[: max(1, int(max_items))]
    return {
        "stable_infos": stable,
        "dynamic_infos": dynamic,
        "frame_count": frame_count,
        "stable_ratio": (len(stable) / max(1, len(stable) + len(dynamic))),
    }
