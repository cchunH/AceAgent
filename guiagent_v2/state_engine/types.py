from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class AnchorNode:
    id: str
    type: str
    text: str
    norm_bbox: dict[str, float]
    role: str
    stability_score: float
    zone: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TopologyMatchResult:
    matched: int
    total_expected: int
    confidence: float
    matched_anchor_ids: list[str]
    reason_code: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StaticSkeleton:
    """Stable scene skeleton extracted from denoised observations."""

    nodes: list[dict[str, Any]]
    signature: str
    stable_ratio: float
    frame_count: int
    sample_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SkeletonMatchResult:
    matched: int
    total_expected: int
    confidence: float
    reason_code: str
    matched_node_keys: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
