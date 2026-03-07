from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SYSTEM_MOBILE_ACTIONS = {
    "open_app",
    "tap",
    "swipe",
    "type",
    "enter",
    "switch_app",
    "back",
    "home",
    "wait",
    "long_press",
}


@dataclass
class RouteDecision:
    channel: str
    route_reason: str
    skill_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "channel": self.channel,
            "route_reason": self.route_reason,
        }
        if self.skill_name:
            data["skill_name"] = self.skill_name
        return data


@dataclass
class WebSkillRouter:
    """Route execution channel between mobile-native chain and web-skill sidecar."""

    web_intent_prefix: str = "web:"
    web_skill_names: set[str] = field(default_factory=set)

    def route(
        self,
        intent_key: str,
        action: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> RouteDecision:
        action = action or {}
        context = context or {}
        forced = str(context.get("force_channel", "")).strip()
        if forced in {"mobile_native", "web_skill"}:
            return RouteDecision(
                channel=forced,
                route_reason="forced_channel",
            )

        action_name = str(action.get("name", "")).strip().lower()
        if action_name in SYSTEM_MOBILE_ACTIONS:
            return RouteDecision(
                channel="mobile_native",
                route_reason="system_mobile_action",
            )

        intent = str(intent_key or "").strip().lower()
        if intent.startswith(self.web_intent_prefix):
            return RouteDecision(
                channel="web_skill",
                route_reason="web_intent_prefix",
                skill_name="AgentBrowserSkill",
            )

        if action_name.startswith("web_"):
            return RouteDecision(
                channel="web_skill",
                route_reason="web_action_prefix",
                skill_name="AgentBrowserSkill",
            )

        if action_name and action_name in self.web_skill_names:
            return RouteDecision(
                channel="web_skill",
                route_reason="web_skill_name_match",
                skill_name="AgentBrowserSkill",
            )

        is_web_subtask = bool(context.get("is_web_subtask", False))
        task_type = str(context.get("task_type", "")).strip().lower()
        if is_web_subtask or task_type == "web":
            return RouteDecision(
                channel="web_skill",
                route_reason="web_context",
                skill_name="AgentBrowserSkill",
            )

        return RouteDecision(
            channel="mobile_native",
            route_reason="default_mobile_native",
        )
