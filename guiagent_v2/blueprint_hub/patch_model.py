from dataclasses import asdict, dataclass, field
from typing import Any
import uuid


@dataclass
class Blueprint:
    intent_key: str
    app_state: str = "global:DEFAULT"
    version: str = "v0.1.0"
    reference_screen: dict[str, int] = field(
        default_factory=lambda: {"width": 1080, "height": 2340}
    )
    anchors: list[dict[str, Any]] = field(default_factory=list)
    post_expectations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BlueprintPatch:
    target_intent_key: str
    target_state: str
    version: str
    delta: dict[str, Any]
    rollback_to: str | None = None
    patch_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

