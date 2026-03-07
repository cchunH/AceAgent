from __future__ import annotations

from typing import Any


class CrashWatchdog:
    name = "crash_watchdog"

    def on_event(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        event_type = str(event.get("event_type", ""))
        status = str(event.get("status", "")).upper()
        if event_type not in {"step_end", "task_end", "handover"}:
            return []
        if status not in {"FAILED", "HANDOVER"}:
            return []

        reason_code = str(event.get("reason_code", "")).strip() or "RUNTIME_FAILURE"
        severity = "HIGH" if event_type == "task_end" or status == "FAILED" else "MEDIUM"
        return [
            {
                "event_type": "watchdog_alert",
                "status": status,
                "watchdog_name": self.name,
                "watchdog_severity": severity,
                "source_event_type": event_type,
                "reason_code": reason_code,
                "alert_category": "runtime_failure",
            }
        ]
