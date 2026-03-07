from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


Handler = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


@dataclass
class ActionEntry:
    schema: dict[str, Any]
    handler: Handler


class ActionRegistry:
    """Unified action registration/validation/dispatch registry."""

    def __init__(self):
        self._entries: dict[str, ActionEntry] = {}

    def register(self, name: str, schema: dict[str, Any], handler: Handler) -> None:
        key = str(name or "").strip()
        if not key:
            raise ValueError("action name must not be empty")
        if not callable(handler):
            raise ValueError("handler must be callable")
        self._entries[key] = ActionEntry(schema=dict(schema or {}), handler=handler)

    def validate(self, name: str, payload: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        key = str(name or "").strip()
        entry = self._entries.get(key)
        if entry is None:
            return False, {"reason": "UNREGISTERED_ACTION", "action": key}

        payload = dict(payload or {})
        schema = entry.schema
        required = schema.get("required", [])
        if isinstance(required, list):
            for field in required:
                if field not in payload:
                    return False, {
                        "reason": "MISSING_FIELD",
                        "action": key,
                        "field": str(field),
                    }

        field_types = schema.get("field_types", {})
        if isinstance(field_types, dict):
            for field, expected_type in field_types.items():
                if field not in payload:
                    continue
                value = payload[field]
                if expected_type == "dict" and not isinstance(value, dict):
                    return False, {
                        "reason": "INVALID_FIELD_TYPE",
                        "action": key,
                        "field": str(field),
                        "expected": "dict",
                    }
                if expected_type == "str" and not isinstance(value, str):
                    return False, {
                        "reason": "INVALID_FIELD_TYPE",
                        "action": key,
                        "field": str(field),
                        "expected": "str",
                    }
                if expected_type == "int" and not isinstance(value, int):
                    return False, {
                        "reason": "INVALID_FIELD_TYPE",
                        "action": key,
                        "field": str(field),
                        "expected": "int",
                    }
        return True, {"reason": "OK", "action": key}

    def dispatch(
        self,
        name: str,
        payload: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        key = str(name or "").strip()
        entry = self._entries.get(key)
        if entry is None:
            raise ValueError(f"unregistered action: {key}")

        valid, detail = self.validate(key, payload)
        if not valid:
            raise ValueError(f"invalid payload for {key}: {detail}")

        return entry.handler(dict(payload or {}), dict(context or {}))

    def list_actions(self) -> list[str]:
        return sorted(self._entries.keys())
