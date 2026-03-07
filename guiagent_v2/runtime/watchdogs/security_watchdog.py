from __future__ import annotations

from typing import Any


class SecurityWatchdog:
    name = "security_watchdog"

    def on_event(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        event_type = str(event.get("event_type", ""))
        if event_type != "guard_decision":
            return []

        decision = str(event.get("policy_decision", "")).lower()
        if decision not in {"deny", "confirm"}:
            return []

        severity = "HIGH" if decision == "deny" else "MEDIUM"
        return [
            {
                "event_type": "watchdog_alert",
                "status": "HANDOVER" if decision == "deny" else "RUNNING",
                "watchdog_name": self.name,
                "watchdog_severity": severity,
                "source_event_type": event_type,
                "reason_code": str(event.get("policy_reason", "")).strip() or "GUARD_CONTROL",
                "alert_category": "policy_guard",
                "policy_decision": decision,
            }
        ]
