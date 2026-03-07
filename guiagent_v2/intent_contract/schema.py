from dataclasses import asdict, dataclass, field
from typing import Any
import uuid


def build_intent_key(domain: str, verb: str, obj: str) -> str:
    return f"{domain}:{verb}:{obj}"


@dataclass
class IntentMetadata:
    key: str
    description: str = ""
    aliases: list[str] = field(default_factory=list)
    risk_level: str = "LOW"
    pre_conditions: list[str] = field(default_factory=list)
    post_expectations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionAssertion:
    expected_semantics: list[str] = field(default_factory=list)
    check_region: dict[str, Any] | None = None
    fail_policy: str = "HANDOVER_S2"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionRequest:
    intent_key: str
    action: dict[str, Any]
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    assertion: ExecutionAssertion = field(default_factory=ExecutionAssertion)
    timeout_ms: int = 3000
    retry_policy: dict[str, Any] = field(
        default_factory=lambda: {"max_retries": 0, "backoff_ms": 0}
    )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["assertion"] = self.assertion.to_dict()
        return payload


@dataclass
class ExecutionResult:
    request_id: str
    status: str
    assertion_result: dict[str, Any] = field(
        default_factory=lambda: {"passed": True, "reason_code": "OK"}
    )
    post_check: dict[str, Any] = field(
        default_factory=lambda: {"passed": True, "reason_code": "STATE_TRANSITION_OK"}
    )
    recovery_level: str = "NONE"
    latency_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

