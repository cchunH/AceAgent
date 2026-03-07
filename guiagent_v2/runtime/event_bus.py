import json
import os
from datetime import datetime, timezone
from threading import Lock
from typing import Any


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
        normalized = {
            "ts": event.get("ts", _utc_now_iso()),
            "run_id": event.get("run_id", ""),
            "task_id": event.get("task_id", ""),
            "step_id": int(event.get("step_id", 0)),
            "chain_mode": event.get("chain_mode", self.default_chain_mode),
            "event_type": event.get("event_type", "unknown"),
            "status": event.get("status", "RUNNING"),
            "intent_key": event.get("intent_key", "global:UNKNOWN:UNSPECIFIED_TARGET"),
        }
        for key, value in event.items():
            if key not in normalized:
                normalized[key] = value

        with self._lock:
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(normalized, ensure_ascii=False) + "\n")
        return normalized

