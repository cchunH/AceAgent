from threading import Lock
from typing import Any


class TaskStatusStore:
    """In-process task status and timeline store for future frontend control plane."""

    def __init__(self):
        self._lock = Lock()
        self._items: dict[tuple[str, str], dict[str, Any]] = {}

    def update(self, event: dict[str, Any]) -> None:
        run_id = str(event.get("run_id", ""))
        task_id = str(event.get("task_id", ""))
        key = (run_id, task_id)

        with self._lock:
            item = self._items.setdefault(
                key,
                {
                    "run_id": run_id,
                    "task_id": task_id,
                    "status": "RUNNING",
                    "last_event_type": None,
                    "updated_at": event.get("ts"),
                    "event_count": 0,
                    "timeline": [],
                },
            )
            item["event_count"] += 1
            item["last_event_type"] = event.get("event_type")
            item["updated_at"] = event.get("ts")

            status = str(event.get("status", "")).upper()
            if status:
                item["status"] = status

            item["timeline"].append(event)

    def get_task_status(self, run_id: str, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._items.get((run_id, task_id))
            if item is None:
                return None
            return {
                "run_id": item["run_id"],
                "task_id": item["task_id"],
                "status": item["status"],
                "last_event_type": item["last_event_type"],
                "updated_at": item["updated_at"],
                "event_count": item["event_count"],
            }

    def get_task_timeline(self, run_id: str, task_id: str) -> list[dict[str, Any]]:
        with self._lock:
            item = self._items.get((run_id, task_id))
            if item is None:
                return []
            return list(item["timeline"])


_GLOBAL_STATUS_STORE = TaskStatusStore()


def get_global_status_store() -> TaskStatusStore:
    return _GLOBAL_STATUS_STORE


def get_task_status(run_id: str, task_id: str) -> dict[str, Any] | None:
    return _GLOBAL_STATUS_STORE.get_task_status(run_id, task_id)


def get_task_timeline(run_id: str, task_id: str) -> list[dict[str, Any]]:
    return _GLOBAL_STATUS_STORE.get_task_timeline(run_id, task_id)

