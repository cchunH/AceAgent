from __future__ import annotations

from collections import defaultdict
from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _normalize_text(value: Any) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text or text == "icon: None":
        return ""
    return text.lower()


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


def _distance_ratio(
    p1: tuple[float, float],
    p2: tuple[float, float],
    width: float,
    height: float,
) -> float:
    if width <= 0 or height <= 0:
        return 0.0
    dx = (p1[0] - p2[0]) / width
    dy = (p1[1] - p2[1]) / height
    return (dx * dx + dy * dy) ** 0.5


def _cluster_key(info: dict[str, Any], width: float, height: float, x: float, y: float) -> str:
    area = _zone(y, height)
    text = _normalize_text(info.get("text"))
    if text:
        return f"T:{text}:{area}"
    qx = int(round(max(0.0, min(1.0, x / max(1.0, width))) * 8))
    qy = int(round(max(0.0, min(1.0, y / max(1.0, height))) * 8))
    return f"I:{area}:{qx}:{qy}"


def _feature_key(cluster_key: str, x: float, y: float, width: float, height: float) -> str:
    qx = int(round(max(0.0, min(1.0, x / max(1.0, width))) * 40))
    qy = int(round(max(0.0, min(1.0, y / max(1.0, height))) * 40))
    return f"{cluster_key}:{qx}:{qy}"


def _match_cluster(
    clusters: list[dict[str, Any]],
    xy: tuple[float, float] | None,
    key: str,
    width: float,
    height: float,
) -> dict[str, Any] | None:
    if not clusters or xy is None:
        return None
    x, y = xy
    best: tuple[float, dict[str, Any]] | None = None
    is_text = key.startswith("T:")
    threshold = 0.06 if is_text else 0.04
    for cluster in clusters:
        if str(cluster.get("cluster_key")) != key:
            continue
        cx, cy = cluster.get("center_xy", (x, y))
        dist = _distance_ratio((x, y), (float(cx), float(cy)), width, height)
        if dist <= threshold and (best is None or dist < best[0]):
            best = (dist, cluster)
    return best[1] if best else None


def denoise_perception_frames(
    frames: list[list[dict[str, Any]]],
    screen_size: tuple[int, int],
    min_presence_ratio: float = 0.6,
    max_items: int = 32,
) -> dict[str, Any]:
    """Extract stable items by cross-frame clustering and per-frame voting."""
    width = max(1.0, float(int(screen_size[0])))
    height = max(1.0, float(int(screen_size[1])))
    min_ratio = max(0.1, min(1.0, float(min_presence_ratio)))
    normalized_frames: list[list[dict[str, Any]]] = [list(frame or []) for frame in (frames or [])]
    frame_count = max(1, len(normalized_frames))

    clusters: list[dict[str, Any]] = []
    cluster_map: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for frame_idx, frame in enumerate(normalized_frames):
        seen_cluster_ids: set[str] = set()
        for item in frame:
            if not isinstance(item, dict):
                continue
            xy = _extract_xy(item)
            if xy is None:
                continue
            x, y = xy
            key = _cluster_key(item, width, height, x, y)
            same_key_clusters = cluster_map.get(key, [])
            matched = _match_cluster(same_key_clusters, (x, y), key, width, height)

            if matched is None:
                cluster_id = f"{key}#{len(same_key_clusters)}"
                matched = {
                    "cluster_id": cluster_id,
                    "cluster_key": key,
                    "sample_item": dict(item),
                    "text_samples": [],
                    "sum_x": 0.0,
                    "sum_y": 0.0,
                    "sample_count": 0,
                    "frame_hits": set(),
                    "center_xy": (x, y),
                }
                clusters.append(matched)
                cluster_map[key].append(matched)

            matched["sum_x"] = float(matched.get("sum_x", 0.0)) + float(x)
            matched["sum_y"] = float(matched.get("sum_y", 0.0)) + float(y)
            matched["sample_count"] = int(matched.get("sample_count", 0)) + 1
            count = max(1, int(matched["sample_count"]))
            matched["center_xy"] = (matched["sum_x"] / count, matched["sum_y"] / count)
            text = str(item.get("text", "")).strip()
            if text and text != "icon: None":
                matched.setdefault("text_samples", []).append(text)

            if matched["cluster_id"] not in seen_cluster_ids:
                matched.setdefault("frame_hits", set()).add(frame_idx)
                seen_cluster_ids.add(matched["cluster_id"])

    stable: list[dict[str, Any]] = []
    dynamic: list[dict[str, Any]] = []
    for cluster in sorted(
        clusters,
        key=lambda item: (len(item.get("frame_hits", set())), int(item.get("sample_count", 0))),
        reverse=True,
    ):
        frame_hits = set(cluster.get("frame_hits", set()))
        ratio = len(frame_hits) / frame_count
        item = dict(cluster.get("sample_item", {}))
        cx, cy = cluster.get("center_xy", (0.0, 0.0))
        item["coordinates"] = (round(float(cx), 2), round(float(cy), 2))

        text_samples = list(cluster.get("text_samples", []))
        if text_samples:
            counts: dict[str, int] = defaultdict(int)
            for text in text_samples:
                counts[text] += 1
            item["text"] = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[0][0]

        item["_stability"] = round(ratio, 4)
        item["_feature_key"] = _feature_key(
            str(cluster.get("cluster_key", "UNK")),
            float(cx),
            float(cy),
            width,
            height,
        )
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
