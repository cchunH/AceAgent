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
    "escalation_rules": [],
    "cross_task_aggregation": {
        "enabled": False,
        "window_sec": 300.0,
        "min_distinct_tasks": 3,
        "emit_throttle_sec": 120.0,
        "severity": "HIGH",
        "group_by_fields": ["watchdog_name", "reason_code", "alert_category"],
    },
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


def _normalize_escalation_rules(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rules: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip() or f"rule_{index}"
        threshold = _as_positive_int(item.get("threshold"), default=3)
        window_sec = _as_non_negative_float(item.get("window_sec"), default=120.0)
        target = str(item.get("target_severity", "CRITICAL") or "CRITICAL").upper()
        if target not in _SEVERITY:
            target = "CRITICAL"
        rule: dict[str, Any] = {
            "name": name,
            "threshold": threshold,
            "window_sec": window_sec,
            "target_severity": target,
        }
        for key in (
            "watchdog_name",
            "reason_code",
            "source_event_type",
            "alert_category",
            "policy_decision",
        ):
            raw = item.get(key)
            if raw is None:
                continue
            text = str(raw).strip()
            if text:
                rule[key] = text
        rules.append(rule)
    return rules


def _normalize_cross_task_aggregation(value: Any, default: dict[str, Any]) -> dict[str, Any]:
    cfg = dict(default)
    if not isinstance(value, dict):
        return cfg
    cfg["enabled"] = bool(value.get("enabled", cfg["enabled"]))
    cfg["window_sec"] = _as_non_negative_float(value.get("window_sec"), cfg["window_sec"])
    cfg["min_distinct_tasks"] = _as_positive_int(
        value.get("min_distinct_tasks"),
        cfg["min_distinct_tasks"],
    )
    cfg["emit_throttle_sec"] = _as_non_negative_float(
        value.get("emit_throttle_sec"),
        cfg["emit_throttle_sec"],
    )
    severity = str(value.get("severity", cfg["severity"]) or cfg["severity"]).upper()
    cfg["severity"] = severity if severity in _SEVERITY else cfg["severity"]
    fields = _normalize_str_list(value.get("group_by_fields"))
    if fields:
        cfg["group_by_fields"] = fields
    return cfg


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

    policy["escalation_rules"] = _normalize_escalation_rules(raw.get("escalation_rules"))
    policy["cross_task_aggregation"] = _normalize_cross_task_aggregation(
        raw.get("cross_task_aggregation"),
        policy["cross_task_aggregation"],
    )
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
