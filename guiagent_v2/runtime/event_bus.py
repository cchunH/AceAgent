import json
import os
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from .event_schema import normalize_event, validate_event


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class JSONLEventBus:
    """Append-only JSONL event writer for runtime observability."""

    def __init__(self, file_path: str, default_chain_mode: str):
        self.file_path = file_path
        self.default_chain_mode = default_chain_mode
        self._lock = Lock()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

    def emit(self, event: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_event(event, default_chain_mode=self.default_chain_mode)
        if not normalized.get("ts"):
            normalized["ts"] = _utc_now_iso()

        valid, detail = validate_event(normalized)
        normalized["schema_valid"] = valid
        if not valid:
            normalized["schema_error"] = detail

        with self._lock:
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(normalized, ensure_ascii=False) + "\n")
        return normalized
