from __future__ import annotations

import json
import os
import time
from copy import deepcopy
from typing import Any


DEFAULT_WATCHDOG_POLICY: dict[str, Any] = {
    "version": "v1",
    "enabled_watchdogs": ["crash_watchdog", "security_watchdog"],
    "min_severity": "LOW",
    "dedup_window_sec": 30.0,
    "max_alerts_per_key": 3,
    "throttle_window_sec": 60.0,
    "dedup_key_fields": ["watchdog_name", "task_id", "reason_code"],
}


_SEVERITY = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def _as_non_negative_float(value: Any, default: float) -> float:
    try:
        return max(0.0, float(value))
    except Exception:
        return default


def _as_positive_int(value: Any, default: int) -> int:
    try:
        return max(1, int(value))
    except Exception:
        return default


def _normalize_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def normalize_watchdog_policy(raw: dict[str, Any] | None) -> dict[str, Any]:
    policy = deepcopy(DEFAULT_WATCHDOG_POLICY)
    if not isinstance(raw, dict):
        return policy

    version = str(raw.get("version", policy["version"]) or policy["version"]).strip()
    policy["version"] = version or policy["version"]

    enabled = [item.strip() for item in _normalize_str_list(raw.get("enabled_watchdogs"))]
    if enabled:
        policy["enabled_watchdogs"] = enabled

    min_severity = str(raw.get("min_severity", policy["min_severity"]) or policy["min_severity"]).upper()
    policy["min_severity"] = min_severity if min_severity in _SEVERITY else policy["min_severity"]

    policy["dedup_window_sec"] = _as_non_negative_float(raw.get("dedup_window_sec"), policy["dedup_window_sec"])
    policy["max_alerts_per_key"] = _as_positive_int(raw.get("max_alerts_per_key"), policy["max_alerts_per_key"])
    policy["throttle_window_sec"] = _as_non_negative_float(
        raw.get("throttle_window_sec"),
        policy["throttle_window_sec"],
    )

    dedup_fields = [item.strip() for item in _normalize_str_list(raw.get("dedup_key_fields"))]
    if dedup_fields:
        policy["dedup_key_fields"] = dedup_fields
    return policy


class WatchdogPolicyLoader:
    """Load and cache watchdog policy from local JSON file."""

    def __init__(
        self,
        policy_path: str | None = None,
        reload_interval_sec: float = 1.0,
    ):
        self.policy_path = str(policy_path).strip() if policy_path else None
        self.reload_interval_sec = max(0.0, float(reload_interval_sec))
        self._cached_policy = normalize_watchdog_policy(None)
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

        self._cached_policy = normalize_watchdog_policy(raw)
        self._cached_mtime = mtime
        return deepcopy(self._cached_policy)

    def source(self) -> str:
        return self.policy_path or "default"
