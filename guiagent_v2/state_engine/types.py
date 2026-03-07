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

