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
        raw_session_id = event.get("session_id")
        session_id = str(raw_session_id).strip() if raw_session_id is not None else ""
        session_id = session_id or None
        key = (run_id, task_id)

        with self._lock:
            item = self._items.setdefault(
                key,
                {
                    "run_id": run_id,
                    "task_id": task_id,
                    "session_id": session_id,
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
            if session_id is not None:
                item["session_id"] = session_id

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
                "session_id": item.get("session_id"),
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

    def list_tasks(
        self,
        run_id: str | None = None,
        status: str | None = None,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        run_id = str(run_id) if run_id is not None else None
        status = str(status).upper() if status is not None else None
        session_id = str(session_id).strip() if session_id is not None else None
        with self._lock:
            items = []
            for item in self._items.values():
                if run_id is not None and item["run_id"] != run_id:
                    continue
                item_session_id = str(item.get("session_id", "")).strip()
                if session_id is not None and item_session_id != session_id:
                    continue
                item_status = str(item.get("status", "")).upper()
                if status is not None and item_status != status:
                    continue
                items.append(
                    {
                        "run_id": item["run_id"],
                        "task_id": item["task_id"],
                        "session_id": item.get("session_id"),
                        "status": item["status"],
                        "last_event_type": item["last_event_type"],
                        "updated_at": item["updated_at"],
                        "event_count": item["event_count"],
                    }
                )
        items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        return items

    def list_run_ids(self) -> list[str]:
        with self._lock:
            run_ids = {item["run_id"] for item in self._items.values()}
        return sorted(run_ids)


_GLOBAL_STATUS_STORE = TaskStatusStore()


def get_global_status_store() -> TaskStatusStore:
    return _GLOBAL_STATUS_STORE


def get_task_status(run_id: str, task_id: str) -> dict[str, Any] | None:
    return _GLOBAL_STATUS_STORE.get_task_status(run_id, task_id)


def get_task_timeline(run_id: str, task_id: str) -> list[dict[str, Any]]:
    return _GLOBAL_STATUS_STORE.get_task_timeline(run_id, task_id)


def list_tasks(
    run_id: str | None = None,
    status: str | None = None,
    session_id: str | None = None,
) -> list[dict[str, Any]]:
    return _GLOBAL_STATUS_STORE.list_tasks(
        run_id=run_id,
        status=status,
        session_id=session_id,
    )


def list_run_ids() -> list[str]:
    return _GLOBAL_STATUS_STORE.list_run_ids()
