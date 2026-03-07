from datetime import datetime, timezone
import os
from threading import Lock
from typing import Any


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_limit(limit: int | None, default: int | None = None) -> int | None:
    if limit is None:
        return default
    value = int(limit)
    if value <= 0:
        return 0
    return min(value, 500)


def _env_positive_int(name: str) -> int | None:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except Exception:
        return None
    if value <= 0:
        return None
    return value


class TaskStatusStore:
    """In-process task status and timeline store for future frontend control plane."""

    def __init__(self, max_timeline_events_per_task: int | None = None):
        if max_timeline_events_per_task is None:
            max_timeline_events_per_task = _env_positive_int(
                "GUIAGENT_STATUS_TIMELINE_MAX_EVENTS_PER_TASK"
            )
        if max_timeline_events_per_task is not None:
            try:
                max_timeline_events_per_task = int(max_timeline_events_per_task)
            except Exception:
                max_timeline_events_per_task = None
            if max_timeline_events_per_task is not None and max_timeline_events_per_task <= 0:
                max_timeline_events_per_task = None
        self._lock = Lock()
        self._items: dict[tuple[str, str], dict[str, Any]] = {}
        self._max_timeline_events_per_task = max_timeline_events_per_task

    def configure_limits(self, *, max_timeline_events_per_task: int | None = None) -> None:
        normalized = max_timeline_events_per_task
        if normalized is not None:
            normalized = int(normalized)
            if normalized <= 0:
                normalized = None
        with self._lock:
            self._max_timeline_events_per_task = normalized

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
                    "timeline_dropped": 0,
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
            max_events = self._max_timeline_events_per_task
            if max_events is not None and len(item["timeline"]) > max_events:
                overflow = len(item["timeline"]) - max_events
                if overflow > 0:
                    del item["timeline"][:overflow]
                    item["timeline_dropped"] = int(item.get("timeline_dropped", 0)) + overflow

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
                "timeline_dropped": int(item.get("timeline_dropped", 0)),
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
                        "timeline_dropped": int(item.get("timeline_dropped", 0)),
                    }
                )
        items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        return items

    def list_run_ids(self) -> list[str]:
        with self._lock:
            run_ids = {item["run_id"] for item in self._items.values()}
        return sorted(run_ids)

    def list_events(
        self,
        run_id: str | None = None,
        task_id: str | None = None,
        session_id: str | None = None,
        event_type: str | None = None,
        actor: str | None = None,
        source: str | None = None,
        control_action: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        page = self.query_events(
            run_id=run_id,
            task_id=task_id,
            session_id=session_id,
            event_type=event_type,
            actor=actor,
            source=source,
            control_action=control_action,
            status=status,
            limit=limit,
        )
        return page["events"]

    def query_events(
        self,
        run_id: str | None = None,
        task_id: str | None = None,
        session_id: str | None = None,
        event_type: str | None = None,
        actor: str | None = None,
        source: str | None = None,
        control_action: str | None = None,
        status: str | None = None,
        limit: int | None = None,
        cursor: int | None = None,
        since_ts: str | None = None,
        until_ts: str | None = None,
    ) -> dict[str, Any]:
        run_id = str(run_id).strip() if run_id is not None else None
        task_id = str(task_id).strip() if task_id is not None else None
        session_id = str(session_id).strip() if session_id is not None else None
        event_type = str(event_type).strip() if event_type is not None else None
        actor = str(actor).strip() if actor is not None else None
        source = str(source).strip() if source is not None else None
        control_action = str(control_action).strip() if control_action is not None else None
        status = str(status).upper().strip() if status is not None else None
        cap = _normalize_limit(limit, default=None)
        if cap == 0:
            return {
                "events": [],
                "next_cursor": None,
                "has_more": False,
                "cursor": 0,
                "total": 0,
            }
        offset = max(0, int(cursor or 0))
        since_dt = _parse_ts(since_ts)
        until_dt = _parse_ts(until_ts)

        with self._lock:
            events: list[dict[str, Any]] = []
            for item in self._items.values():
                if run_id is not None and item["run_id"] != run_id:
                    continue
                if task_id is not None and item["task_id"] != task_id:
                    continue
                item_session_id = str(item.get("session_id", "")).strip()
                if session_id is not None and item_session_id != session_id:
                    continue

                for event in item.get("timeline", []):
                    if not isinstance(event, dict):
                        continue
                    if event_type is not None and str(event.get("event_type", "")).strip() != event_type:
                        continue
                    if actor is not None and str(event.get("actor", "")).strip() != actor:
                        continue
                    if source is not None and str(event.get("source", "")).strip() != source:
                        continue
                    if control_action is not None and str(event.get("control_action", "")).strip() != control_action:
                        continue
                    if status is not None and str(event.get("status", "")).upper().strip() != status:
                        continue
                    event_dt = _parse_ts(event.get("ts"))
                    if since_dt is not None:
                        if event_dt is None or event_dt < since_dt:
                            continue
                    if until_dt is not None:
                        if event_dt is None or event_dt > until_dt:
                            continue
                    events.append(dict(event))

            events.sort(
                key=lambda x: (
                    _parse_ts(x.get("ts")) or datetime.min.replace(tzinfo=timezone.utc),
                    str(x.get("ts", "")),
                ),
                reverse=True,
            )
            total = len(events)
            if cap is None:
                page_events = events[offset:]
                return {
                    "events": page_events,
                    "next_cursor": None,
                    "has_more": False,
                    "cursor": offset,
                    "total": total,
                }

            start = min(offset, total)
            end = min(start + cap, total)
            page_events = events[start:end]
            has_more = end < total
            return {
                "events": page_events,
                "next_cursor": end if has_more else None,
                "has_more": has_more,
                "cursor": start,
                "total": total,
            }


_GLOBAL_STATUS_STORE = TaskStatusStore()


def get_global_status_store() -> TaskStatusStore:
    return _GLOBAL_STATUS_STORE


def configure_global_status_store(*, max_timeline_events_per_task: int | None = None) -> None:
    _GLOBAL_STATUS_STORE.configure_limits(
        max_timeline_events_per_task=max_timeline_events_per_task,
    )


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


def list_events(
    run_id: str | None = None,
    task_id: str | None = None,
    session_id: str | None = None,
    event_type: str | None = None,
    actor: str | None = None,
    source: str | None = None,
    control_action: str | None = None,
    status: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    return _GLOBAL_STATUS_STORE.list_events(
        run_id=run_id,
        task_id=task_id,
        session_id=session_id,
        event_type=event_type,
        actor=actor,
        source=source,
        control_action=control_action,
        status=status,
        limit=limit,
    )


def query_events(
    run_id: str | None = None,
    task_id: str | None = None,
    session_id: str | None = None,
    event_type: str | None = None,
    actor: str | None = None,
    source: str | None = None,
    control_action: str | None = None,
    status: str | None = None,
    limit: int | None = None,
    cursor: int | None = None,
    since_ts: str | None = None,
    until_ts: str | None = None,
) -> dict[str, Any]:
    return _GLOBAL_STATUS_STORE.query_events(
        run_id=run_id,
        task_id=task_id,
        session_id=session_id,
        event_type=event_type,
        actor=actor,
        source=source,
        control_action=control_action,
        status=status,
        limit=limit,
        cursor=cursor,
        since_ts=since_ts,
        until_ts=until_ts,
    )
