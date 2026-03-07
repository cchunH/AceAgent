from collections import Counter
from typing import Any

from .types import AnchorNode


def _zone_of_y(y: float, height: float) -> str:
    if height <= 0:
        return "middle"
    if y <= 0.15 * height:
        return "top"
    if y >= 0.85 * height:
        return "bottom"
    return "middle"


def _normalize_bbox(
    x: float,
    y: float,
    width: float,
    height: float,
) -> dict[str, float]:
    if width <= 0 or height <= 0:
        return {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0}
    return {
        "x": x / width,
        "y": y / height,
        "w": 0.0,
        "h": 0.0,
    }


def _stability_score(
    text: str,
    zone: str,
    text_freq: Counter,
) -> float:
    score = 0.0
    if text and text != "icon: None":
        score += 0.6
        if text_freq[text] == 1:
            score += 0.2
    else:
        score += 0.2
    if zone in ("top", "bottom"):
        score += 0.2
    return min(score, 1.0)


def extract_anchors(
    perception_infos: list[dict[str, Any]],
    screen_size: tuple[int, int],
    max_anchors: int = 8,
) -> list[AnchorNode]:
    width, height = screen_size
    texts = [str(i.get("text", "")).strip() for i in perception_infos if i.get("text")]
    text_freq = Counter(texts)
    anchors: list[AnchorNode] = []

    for idx, info in enumerate(perception_infos):
        coords = info.get("coordinates", (0, 0))
        if not isinstance(coords, (tuple, list)) or len(coords) < 2:
            continue
        x, y = float(coords[0]), float(coords[1])
        if x <= 0 and y <= 0:
            continue

        text = str(info.get("text", "")).strip()
        zone = _zone_of_y(y, float(height))
        score = _stability_score(text, zone, text_freq)
        role = "CORE" if zone in ("top", "bottom") and score >= 0.6 else "AUXILIARY"
        anchor_type = "TEXT" if text and text != "icon: None" else "ICON"

        anchors.append(
            AnchorNode(
                id=f"a{idx}",
                type=anchor_type,
                text=text,
                norm_bbox=_normalize_bbox(x, y, float(width), float(height)),
                role=role,
                stability_score=score,
                zone=zone,
            )
        )

    anchors.sort(key=lambda a: a.stability_score, reverse=True)
    return anchors[:max_anchors]

