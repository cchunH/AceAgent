from __future__ import annotations

from typing import Any

from .base import WatchdogPlugin
from .crash_watchdog import CrashWatchdog
from .security_watchdog import SecurityWatchdog


class WatchdogManager:
    """Dispatches runtime events to watchdog plugins and emits alerts."""

    def __init__(self, plugins: list[WatchdogPlugin] | None = None):
        self._plugins = list(plugins or [])

    def process(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        if str(event.get("event_type", "")) == "watchdog_alert":
            return []

        alerts: list[dict[str, Any]] = []
        for plugin in self._plugins:
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
                alerts.append(self._hydrate_alert(event, alert))
        return alerts

    def _hydrate_alert(self, source_event: dict[str, Any], alert: dict[str, Any]) -> dict[str, Any]:
        payload = dict(alert or {})
        payload.setdefault("run_id", source_event.get("run_id", ""))
        payload.setdefault("task_id", source_event.get("task_id", ""))
        payload.setdefault("step_id", int(source_event.get("step_id", 0)))
        payload.setdefault("chain_mode", source_event.get("chain_mode", "legacy"))
        payload.setdefault("intent_key", source_event.get("intent_key", "global:UNKNOWN:UNSPECIFIED_TARGET"))

        source_session_id = source_event.get("session_id")
        if "session_id" not in payload and source_session_id is not None:
            payload["session_id"] = source_session_id
        return payload


def build_default_watchdog_manager() -> WatchdogManager:
    return WatchdogManager(plugins=[CrashWatchdog(), SecurityWatchdog()])
