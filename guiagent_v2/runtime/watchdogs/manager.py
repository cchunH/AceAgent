from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import Any

from .base import WatchdogPlugin
from .crash_watchdog import CrashWatchdog
from .security_watchdog import SecurityWatchdog
from ..watchdog_policy import WatchdogPolicyLoader


_SEVERITY_RANK = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


class WatchdogManager:
    """Dispatches runtime events to watchdog plugins and emits alerts."""

    def __init__(
        self,
        plugins: list[WatchdogPlugin] | None = None,
        policy_loader: WatchdogPolicyLoader | None = None,
    ):
        self._plugins = list(plugins or [])
        self._policy_loader = policy_loader or WatchdogPolicyLoader()
        self._lock = Lock()
        self._last_emit_at: dict[str, float] = {}
        self._window_emit_at: dict[str, list[float]] = defaultdict(list)

    def process(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        if str(event.get("event_type", "")) == "watchdog_alert":
            return []
        policy = self._policy_loader.load()
        enabled_watchdogs = {
            str(item).strip()
            for item in policy.get("enabled_watchdogs", [])
            if str(item).strip()
        }
        min_severity = str(policy.get("min_severity", "LOW")).upper()
        min_severity_rank = _SEVERITY_RANK.get(min_severity, _SEVERITY_RANK["LOW"])

        alerts: list[dict[str, Any]] = []
        for plugin in self._plugins:
            plugin_name = str(getattr(plugin, "name", "")).strip()
            if enabled_watchdogs and plugin_name not in enabled_watchdogs:
                continue
            try:
                generated = plugin.on_event(event)
            except Exception as exc:
                generated = [
                    {
                        "event_type": "watchdog_alert",
                        "status": "FAILED",
                        "watchdog_name": getattr(plugin, "name", "watchdog"),
                        "watchdog_severity": "HIGH",
                        "source_event_type": str(event.get("event_type", "unknown")),
                        "reason_code": "WATCHDOG_PLUGIN_ERROR",
                        "watchdog_error": str(exc),
                        "alert_category": "watchdog_internal",
                    }
                ]
            for alert in generated:
                hydrated = self._hydrate_alert(event, alert, policy_version=str(policy.get("version", "v1")))
                severity = str(hydrated.get("watchdog_severity", "LOW")).upper()
                severity_rank = _SEVERITY_RANK.get(severity, _SEVERITY_RANK["LOW"])
                if severity_rank < min_severity_rank:
                    continue
                if not self._allow_alert(hydrated, policy):
                    continue
                alerts.append(hydrated)
        return alerts

    def _hydrate_alert(
        self,
        source_event: dict[str, Any],
        alert: dict[str, Any],
        policy_version: str,
    ) -> dict[str, Any]:
        payload = dict(alert or {})
        payload.setdefault("run_id", source_event.get("run_id", ""))
        payload.setdefault("task_id", source_event.get("task_id", ""))
        payload.setdefault("step_id", int(source_event.get("step_id", 0)))
        payload.setdefault("chain_mode", source_event.get("chain_mode", "legacy"))
        payload.setdefault("intent_key", source_event.get("intent_key", "global:UNKNOWN:UNSPECIFIED_TARGET"))
        payload.setdefault("watchdog_policy_version", policy_version)
        payload.setdefault("watchdog_policy_source", self._policy_loader.source())

        source_session_id = source_event.get("session_id")
        if "session_id" not in payload and source_session_id is not None:
            payload["session_id"] = source_session_id
        return payload

    def _build_dedup_key(self, alert: dict[str, Any], policy: dict[str, Any]) -> str:
        fields = policy.get("dedup_key_fields", []) or ["watchdog_name", "task_id", "reason_code"]
        parts: list[str] = []
        for field in fields:
            key = str(field).strip()
            if not key:
                continue
            parts.append(f"{key}={alert.get(key)}")
        if not parts:
            parts.append(f"watchdog_name={alert.get('watchdog_name')}")
        return "|".join(parts)

    def _allow_alert(self, alert: dict[str, Any], policy: dict[str, Any]) -> bool:
        dedup_key = self._build_dedup_key(alert, policy)
        dedup_window = float(policy.get("dedup_window_sec", 0.0) or 0.0)
        throttle_window = float(policy.get("throttle_window_sec", 0.0) or 0.0)
        max_alerts = int(policy.get("max_alerts_per_key", 1) or 1)
        now = time.monotonic()

        with self._lock:
            last_emit = self._last_emit_at.get(dedup_key)
            if dedup_window > 0 and last_emit is not None and (now - last_emit) < dedup_window:
                return False

            history = self._window_emit_at[dedup_key]
            if throttle_window > 0:
                history = [ts for ts in history if (now - ts) <= throttle_window]
                self._window_emit_at[dedup_key] = history
            if throttle_window > 0 and len(history) >= max_alerts:
                return False

            self._last_emit_at[dedup_key] = now
            history.append(now)
            self._window_emit_at[dedup_key] = history
        return True


def build_default_watchdog_manager(
    policy_path: str | None = None,
    reload_interval_sec: float = 1.0,
) -> WatchdogManager:
    return WatchdogManager(
        plugins=[CrashWatchdog(), SecurityWatchdog()],
        policy_loader=WatchdogPolicyLoader(
            policy_path=policy_path,
            reload_interval_sec=reload_interval_sec,
        ),
    )
