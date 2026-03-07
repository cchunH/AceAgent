from __future__ import annotations

from typing import Any


EVENT_SCHEMA_VERSION = "v1"
BASE_EVENT_FIELDS = (
    "ts",
    "run_id",
    "task_id",
    "step_id",
    "chain_mode",
    "event_type",
    "status",
    "intent_key",
)
STATUS_SET = {"QUEUED", "RUNNING", "SUCCESS", "FAILED", "HANDOVER", "BLOCKED"}
EVENT_REQUIRED_EXTRA_FIELDS: dict[str, tuple[str, ...]] = {
    "guard_decision": ("policy_decision",),
    "skill_route": ("channel", "route_reason"),
    "skill_fallback": ("fallback_to", "reason_code"),
    "adapter_call": ("adapter_backend",),
    "watchdog_alert": ("watchdog_name", "watchdog_severity", "source_event_type"),
    "control_plane_audit": ("control_action", "http_method", "http_path", "actor", "source"),
}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _as_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def normalize_event(event: dict[str, Any], default_chain_mode: str) -> dict[str, Any]:
    payload = dict(event or {})
    normalized = {
        "ts": _as_str(payload.get("ts")),
        "run_id": _as_str(payload.get("run_id")),
        "task_id": _as_str(payload.get("task_id")),
        "step_id": _as_int(payload.get("step_id"), default=0),
        "chain_mode": _as_str(payload.get("chain_mode"), default_chain_mode),
        "event_type": _as_str(payload.get("event_type"), "unknown"),
        "status": _as_str(payload.get("status"), "RUNNING").upper(),
        "intent_key": _as_str(payload.get("intent_key"), "global:UNKNOWN:UNSPECIFIED_TARGET"),
        "event_schema_version": EVENT_SCHEMA_VERSION,
    }
    for key, value in payload.items():
        if key not in normalized:
            normalized[key] = value

    session_id = payload.get("session_id")
    if session_id is not None:
        normalized["session_id"] = _as_str(session_id).strip() or None
    return normalized


def validate_event(event: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    errors: list[str] = []
    for field in BASE_EVENT_FIELDS:
        if field == "ts":
            # ts may be injected later by event bus.
            continue
        value = event.get(field)
        if value is None:
            errors.append(f"missing:{field}")
            continue
        if isinstance(value, str) and not value.strip():
            errors.append(f"empty:{field}")
    if not isinstance(event.get("step_id"), int):
        errors.append("invalid:step_id_type")

    status = str(event.get("status", "")).upper()
    if status and status not in STATUS_SET:
        errors.append("invalid:status")

    event_type = str(event.get("event_type", ""))
    required_extra = EVENT_REQUIRED_EXTRA_FIELDS.get(event_type, ())
    for field in required_extra:
        value = event.get(field)
        if value is None:
            errors.append(f"missing:{field}")
        elif isinstance(value, str) and not value.strip():
            errors.append(f"empty:{field}")

    if errors:
        return False, {"code": "EVENT_SCHEMA_INVALID", "errors": errors}
    return True, {"code": "OK"}
