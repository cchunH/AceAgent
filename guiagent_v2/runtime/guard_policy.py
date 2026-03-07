from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .web_skill_router import SYSTEM_MOBILE_ACTIONS


HIGH_RISK_TOKENS = {
    "PAY",
    "TRANSFER",
    "DELETE",
    "PURCHASE",
    "SEND",
    "SUBMIT",
}


@dataclass
class GuardPolicy:
    """Execution guard with allow/deny/confirm decisions."""

    high_risk_tokens: set[str] = field(default_factory=lambda: set(HIGH_RISK_TOKENS))

    def decide(
        self,
        intent_key: str,
        action: dict[str, Any] | None,
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        action = action or {}
        context = context or {}

        action_name = str(action.get("name", "")).strip().lower()
        channel = str(context.get("channel", "mobile_native")).strip().lower()

        if bool(context.get("force_deny", False)):
            return {
                "decision": "deny",
                "reason": "FORCE_DENY",
                "category": "policy_override",
            }

        # Hard guard: never allow system mobile actions to be executed via web skill channel.
        if channel == "web_skill" and action_name in SYSTEM_MOBILE_ACTIONS:
            return {
                "decision": "deny",
                "reason": "MOBILE_ACTION_BLOCKED_FOR_WEB_SKILL",
                "category": "route_guard",
            }

        intent_upper = str(intent_key or "").upper()
        if any(token in intent_upper for token in self.high_risk_tokens):
            return {
                "decision": "confirm",
                "reason": "HIGH_RISK_INTENT",
                "category": "risk_control",
            }

        return {
            "decision": "allow",
            "reason": "ALLOW_BY_DEFAULT",
            "category": "baseline",
        }
