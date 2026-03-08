from __future__ import annotations

import json
import os
import time
from copy import deepcopy
from typing import Any


DEFAULT_GUARD_POLICY: dict[str, Any] = {
    "version": "v1",
    "high_risk_tokens": ["PAY", "TRANSFER", "DELETE", "PURCHASE", "SEND", "SUBMIT"],
    "deny_intent_prefixes": [],
    "confirm_intent_prefixes": [],
    "deny_actions_by_channel": {},
    "allow_actions_by_channel": {},
    "web_domain_allowlist": [],
    "web_domain_denylist": [],
    "blocked_mobile_actions_on_web_skill": True,
}


def _normalize_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def _normalize_channel_actions(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, list[str]] = {}
    for channel, actions in value.items():
        channel_key = str(channel or "").strip().lower()
        if not channel_key:
            continue
        normalized[channel_key] = [item.lower() for item in _normalize_str_list(actions)]
    return normalized


def _normalize_domain_rules(value: Any) -> list[str]:
    rules = _normalize_str_list(value)
    normalized: list[str] = []
    for item in rules:
        text = item.strip().lower()
        if text:
            normalized.append(text)
    return normalized


def normalize_guard_policy(raw: dict[str, Any] | None) -> dict[str, Any]:
    policy = deepcopy(DEFAULT_GUARD_POLICY)
    if not isinstance(raw, dict):
        return policy

    version = str(raw.get("version", policy["version"]) or policy["version"]).strip()
    policy["version"] = version or policy["version"]
    if "high_risk_tokens" in raw:
        policy["high_risk_tokens"] = [item.upper() for item in _normalize_str_list(raw.get("high_risk_tokens"))]
    policy["deny_intent_prefixes"] = _normalize_str_list(raw.get("deny_intent_prefixes"))
    policy["confirm_intent_prefixes"] = _normalize_str_list(raw.get("confirm_intent_prefixes"))
    policy["deny_actions_by_channel"] = _normalize_channel_actions(raw.get("deny_actions_by_channel"))
    policy["allow_actions_by_channel"] = _normalize_channel_actions(raw.get("allow_actions_by_channel"))
    policy["web_domain_allowlist"] = _normalize_domain_rules(raw.get("web_domain_allowlist"))
    policy["web_domain_denylist"] = _normalize_domain_rules(raw.get("web_domain_denylist"))
    policy["blocked_mobile_actions_on_web_skill"] = bool(
        raw.get("blocked_mobile_actions_on_web_skill", policy["blocked_mobile_actions_on_web_skill"])
    )
    return policy


class PolicyLoader:
    """Load and cache guard policy from local JSON file."""

    def __init__(
        self,
        policy_path: str | None = None,
        reload_interval_sec: float = 1.0,
    ):
        self.policy_path = str(policy_path).strip() if policy_path else None
        self.reload_interval_sec = max(0.0, float(reload_interval_sec))
        self._cached_policy = normalize_guard_policy(None)
        self._cached_mtime: float | None = None
        self._last_checked = 0.0

    def load(self, force: bool = False) -> dict[str, Any]:
        now = time.monotonic()
        if not force and self.reload_interval_sec > 0 and (now - self._last_checked) < self.reload_interval_sec:
            return deepcopy(self._cached_policy)

        self._last_checked = now
        if not self.policy_path:
            return deepcopy(self._cached_policy)

        try:
            mtime = os.path.getmtime(self.policy_path)
        except OSError:
            return deepcopy(self._cached_policy)

        if not force and self._cached_mtime is not None and mtime == self._cached_mtime:
            return deepcopy(self._cached_policy)

        try:
            with open(self.policy_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            return deepcopy(self._cached_policy)

        self._cached_policy = normalize_guard_policy(raw)
        self._cached_mtime = mtime
        return deepcopy(self._cached_policy)

    def source(self) -> str:
        return self.policy_path or "default"
