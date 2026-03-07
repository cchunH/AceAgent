from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .policy_loader import PolicyLoader
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
    policy_loader: PolicyLoader = field(default_factory=PolicyLoader)

    @classmethod
    def from_policy_file(
        cls,
        policy_path: str,
        reload_interval_sec: float = 1.0,
    ) -> "GuardPolicy":
        return cls(
            policy_loader=PolicyLoader(
                policy_path=policy_path,
                reload_interval_sec=reload_interval_sec,
            )
        )

    def reload_policy(self) -> dict[str, Any]:
        return self.policy_loader.load(force=True)

    def _get_policy(self) -> dict[str, Any]:
        policy = self.policy_loader.load()
        self.high_risk_tokens = {
            str(item).upper()
            for item in policy.get("high_risk_tokens", [])
            if str(item).strip()
        }
        return policy

    def decide(
        self,
        intent_key: str,
        action: dict[str, Any] | None,
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        action = action or {}
        context = context or {}
        policy = self._get_policy()

        action_name = str(action.get("name", "")).strip().lower()
        channel = str(context.get("channel", "mobile_native")).strip().lower()
        intent = str(intent_key or "").strip()
        intent_upper = intent.upper()
        source = self.policy_loader.source()

        if bool(context.get("force_deny", False)):
            return {
                "decision": "deny",
                "reason": "FORCE_DENY",
                "category": "policy_override",
                "policy_source": source,
                "policy_version": policy.get("version", "v1"),
            }

        deny_prefixes = [
            str(prefix).upper()
            for prefix in policy.get("deny_intent_prefixes", [])
            if str(prefix).strip()
        ]
        if deny_prefixes and any(intent_upper.startswith(prefix) for prefix in deny_prefixes):
            return {
                "decision": "deny",
                "reason": "INTENT_PREFIX_DENIED",
                "category": "policy_rules",
                "policy_source": source,
                "policy_version": policy.get("version", "v1"),
            }

        deny_actions_by_channel = policy.get("deny_actions_by_channel", {})
        denied_actions = {
            str(name).strip().lower()
            for name in deny_actions_by_channel.get(channel, [])
            if str(name).strip()
        }
        if action_name and action_name in denied_actions:
            return {
                "decision": "deny",
                "reason": "ACTION_DENIED_BY_POLICY",
                "category": "policy_rules",
                "policy_source": source,
                "policy_version": policy.get("version", "v1"),
            }

        allow_actions_by_channel = policy.get("allow_actions_by_channel", {})
        allowed_actions = {
            str(name).strip().lower()
            for name in allow_actions_by_channel.get(channel, [])
            if str(name).strip()
        }
        if allowed_actions and action_name and action_name not in allowed_actions:
            return {
                "decision": "deny",
                "reason": "ACTION_NOT_ALLOWED_BY_POLICY",
                "category": "policy_rules",
                "policy_source": source,
                "policy_version": policy.get("version", "v1"),
            }

        # Hard guard: never allow system mobile actions to be executed via web skill channel.
        if (
            bool(policy.get("blocked_mobile_actions_on_web_skill", True))
            and channel == "web_skill"
            and action_name in SYSTEM_MOBILE_ACTIONS
        ):
            return {
                "decision": "deny",
                "reason": "MOBILE_ACTION_BLOCKED_FOR_WEB_SKILL",
                "category": "route_guard",
                "policy_source": source,
                "policy_version": policy.get("version", "v1"),
            }

        confirm_prefixes = [
            str(prefix).upper()
            for prefix in policy.get("confirm_intent_prefixes", [])
            if str(prefix).strip()
        ]
        if confirm_prefixes and any(intent_upper.startswith(prefix) for prefix in confirm_prefixes):
            return {
                "decision": "confirm",
                "reason": "INTENT_PREFIX_CONFIRM",
                "category": "policy_rules",
                "policy_source": source,
                "policy_version": policy.get("version", "v1"),
            }

        if any(token in intent_upper for token in self.high_risk_tokens):
            return {
                "decision": "confirm",
                "reason": "HIGH_RISK_INTENT",
                "category": "risk_control",
                "policy_source": source,
                "policy_version": policy.get("version", "v1"),
            }

        return {
            "decision": "allow",
            "reason": "ALLOW_BY_DEFAULT",
            "category": "baseline",
            "policy_source": source,
            "policy_version": policy.get("version", "v1"),
        }
