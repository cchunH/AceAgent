from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from copy import deepcopy
from threading import Lock
from typing import Any

from .status_api import (
    get_task_status,
    get_task_timeline,
    list_events as list_runtime_events_api,
    query_events as query_runtime_events_api,
    list_tasks as list_runtime_tasks,
)
from .task_service import RuntimeTaskService, RunnerCallable


TERMINAL_STATUSES = {"SUCCESS", "FAILED", "HANDOVER", "BLOCKED"}


class SessionRuntime:
    """Session-scoped runtime task manager with per-session isolation."""

    def __init__(
        self,
        runner: RunnerCallable | None = None,
        per_session_max_workers: int = 1,
        persistence_path: str | None = None,
    ):
        self._runner = runner
        self._per_session_max_workers = max(1, int(per_session_max_workers))
        self._lock = Lock()
        self._sessions: dict[str, dict[str, Any]] = {}
        self._request_index: dict[str, str] = {}
        self._task_snapshots: dict[str, dict[str, Any]] = {}
        self._persistence_path = self._normalize_persistence_path(persistence_path)
        self._load_state()

    def _normalize_persistence_path(self, persistence_path: str | None) -> str | None:
        if persistence_path is None:
            return None
        raw = str(persistence_path).strip()
        if not raw:
            return None
        if raw.endswith(os.sep) or os.path.isdir(raw):
            return os.path.join(raw, "session_runtime_state.json")
        return raw

    def _generate_session_id(self) -> str:
        return "sess-" + uuid.uuid4().hex[:8]

    def _new_task_service(self) -> RuntimeTaskService:
        return RuntimeTaskService(
            runner=self._runner,
            max_workers=self._per_session_max_workers,
        )

    def _get_or_create_service(self, session_id: str) -> RuntimeTaskService:
        record = self._sessions.get(session_id)
        if record is None:
            raise KeyError(f"unknown session_id: {session_id}")
        return record["service"]

    def _is_terminal(self, status: Any) -> bool:
        return str(status or "").upper() in TERMINAL_STATUSES

    def _state_snapshot_locked(self) -> dict[str, Any]:
        sessions: dict[str, dict[str, Any]] = {}
        for sid, record in self._sessions.items():
            sessions[sid] = {
                "session_id": sid,
                "created_at": record.get("created_at"),
                "updated_at": record.get("updated_at"),
                "metadata": deepcopy(record.get("metadata", {})),
                "request_ids": list(record.get("request_ids", [])),
            }
        return {
            "version": "v1",
            "saved_at": time.time(),
            "sessions": sessions,
            "request_index": dict(self._request_index),
            "task_snapshots": deepcopy(self._task_snapshots),
        }

    def _persist_state(self) -> None:
        if not self._persistence_path:
            return
        with self._lock:
            payload = self._state_snapshot_locked()
            path = self._persistence_path

        directory = os.path.dirname(path) or "."
        os.makedirs(directory, exist_ok=True)
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(
                prefix=".session-runtime-",
                suffix=".tmp",
                dir=directory,
            )
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
            tmp_path = None
        except Exception:
            pass
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _load_state(self) -> None:
        path = self._persistence_path
        if not path or not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            return
        if not isinstance(raw, dict):
            return

        sessions_raw = raw.get("sessions", {})
        request_index_raw = raw.get("request_index", {})
        task_snapshots_raw = raw.get("task_snapshots", {})

        sessions: dict[str, dict[str, Any]] = {}
        request_index: dict[str, str] = {}
        task_snapshots: dict[str, dict[str, Any]] = {}

        if isinstance(sessions_raw, dict):
            for sid_raw, data in sessions_raw.items():
                sid = str(sid_raw or "").strip()
                if not sid or not isinstance(data, dict):
                    continue
                request_ids = [
                    str(item).strip()
                    for item in data.get("request_ids", [])
                    if str(item).strip()
                ]
                created_at = float(data.get("created_at", time.time()))
                updated_at = float(data.get("updated_at", created_at))
                metadata = data.get("metadata")
                if not isinstance(metadata, dict):
                    metadata = {}
                sessions[sid] = {
                    "session_id": sid,
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "metadata": metadata,
                    "service": self._new_task_service(),
                    "request_ids": request_ids,
                }
                for rid in request_ids:
                    request_index[rid] = sid

        if isinstance(request_index_raw, dict):
            for rid_raw, sid_raw in request_index_raw.items():
                rid = str(rid_raw or "").strip()
                sid = str(sid_raw or "").strip()
                if not rid or not sid or sid not in sessions:
                    continue
                request_index[rid] = sid
                if rid not in sessions[sid]["request_ids"]:
                    sessions[sid]["request_ids"].append(rid)

        if isinstance(task_snapshots_raw, dict):
            for rid_raw, snapshot in task_snapshots_raw.items():
                rid = str(rid_raw or "").strip()
                if not rid or not isinstance(snapshot, dict):
                    continue
                payload = dict(snapshot)
                payload["request_id"] = rid
                sid = str(payload.get("session_id", "")).strip()
                if not sid:
                    sid = request_index.get(rid, "")
                    if sid:
                        payload["session_id"] = sid
                task_snapshots[rid] = payload

        with self._lock:
            self._sessions = sessions
            self._request_index = request_index
            self._task_snapshots = task_snapshots

    def _record_task_snapshot(self, item: dict[str, Any], persist: bool = False) -> None:
        request_id = str(item.get("request_id", "")).strip()
        if not request_id:
            return
        payload = dict(item)
        sid = str(payload.get("session_id", "")).strip()
        with self._lock:
            if not sid:
                sid = self._request_index.get(request_id, "")
                if sid:
                    payload["session_id"] = sid
            if sid and request_id not in self._request_index:
                self._request_index[request_id] = sid
            self._task_snapshots[request_id] = payload
        if persist:
            self._persist_state()

    def _get_task_snapshot(self, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._task_snapshots.get(request_id)
            if item is None:
                return None
            return deepcopy(item)

    def ensure_session(
        self,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata = dict(metadata or {})
        changed = False
        with self._lock:
            sid = str(session_id or "").strip() or self._generate_session_id()
            existing = self._sessions.get(sid)
            if existing is None:
                changed = True
                now = time.time()
                self._sessions[sid] = {
                    "session_id": sid,
                    "created_at": now,
                    "updated_at": now,
                    "metadata": metadata,
                    "service": self._new_task_service(),
                    "request_ids": [],
                }
            else:
                if metadata:
                    changed = True
                    existing["metadata"].update(metadata)
                existing["updated_at"] = time.time()
        if changed:
            self._persist_state()
        return self.get_session(sid) or {"session_id": sid}

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        sid = str(session_id or "").strip()
        with self._lock:
            record = self._sessions.get(sid)
            if record is None:
                return None
            request_ids = list(record.get("request_ids", []))
            return {
                "session_id": sid,
                "created_at": record["created_at"],
                "updated_at": record["updated_at"],
                "metadata": deepcopy(record.get("metadata", {})),
                "task_count": len(request_ids),
                "last_request_id": request_ids[-1] if request_ids else None,
            }

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._lock:
            session_ids = list(self._sessions.keys())
        items: list[dict[str, Any]] = []
        for sid in session_ids:
            item = self.get_session(sid)
            if item is not None:
                items.append(item)
        items.sort(key=lambda x: x.get("updated_at") or 0.0, reverse=True)
        return items

    def submit_task(
        self,
        instruction: str,
        session_id: str | None = None,
        runtime_mode: str = "legacy",
        run_name: str = "test",
        task_id: str | None = None,
        run_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session = self.ensure_session(session_id=session_id)
        sid = session["session_id"]
        run_options = dict(run_options or {})
        run_options.setdefault("session_id", sid)

        with self._lock:
            service = self._get_or_create_service(sid)

        submitted = service.submit_task(
            instruction=instruction,
            runtime_mode=runtime_mode,
            run_name=run_name,
            task_id=task_id,
            run_options=run_options,
        )

        request_id = str(submitted.get("request_id", ""))
        with self._lock:
            record = self._sessions.get(sid)
            if record is not None:
                record["updated_at"] = time.time()
                if request_id:
                    if request_id not in record["request_ids"]:
                        record["request_ids"].append(request_id)
                    self._request_index[request_id] = sid

        payload = dict(submitted)
        payload["session_id"] = sid
        self._record_task_snapshot(payload, persist=True)
        return payload

    def get_task(self, request_id: str) -> dict[str, Any] | None:
        rid = str(request_id or "").strip()
        if not rid:
            return None

        with self._lock:
            sid = self._request_index.get(rid)
            service = self._sessions.get(sid, {}).get("service") if sid else None

        if service is not None:
            item = service.get_task(rid)
            if item is not None:
                payload = dict(item)
                payload["session_id"] = sid
                self._record_task_snapshot(payload, persist=self._is_terminal(payload.get("status")))
                return payload
        return self._get_task_snapshot(rid)

    def wait(self, request_id: str, timeout: float | None = None) -> dict[str, Any] | None:
        rid = str(request_id or "").strip()
        if not rid:
            return None

        with self._lock:
            sid = self._request_index.get(rid)
            service = self._sessions.get(sid, {}).get("service") if sid else None

        if service is None:
            return self._get_task_snapshot(rid)

        item = service.wait(rid, timeout=timeout)
        if item is None:
            return self._get_task_snapshot(rid)

        payload = dict(item)
        payload["session_id"] = sid
        self._record_task_snapshot(payload, persist=self._is_terminal(payload.get("status")))
        return payload

    def list_tasks(
        self,
        session_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        sid = str(session_id or "").strip() if session_id else None
        status_filter = str(status or "").upper().strip() if status else None

        with self._lock:
            if sid:
                record = self._sessions.get(sid)
                if record is None:
                    return []
                services = [(sid, record["service"])]
            else:
                services = [(key, value["service"]) for key, value in self._sessions.items()]
            snapshots = deepcopy(self._task_snapshots)

        items: list[dict[str, Any]] = []
        seen_request_ids: set[str] = set()
        for current_sid, service in services:
            for item in service.list_tasks(status=status):
                payload = dict(item)
                payload["session_id"] = current_sid
                request_id = str(payload.get("request_id", "")).strip()
                if request_id:
                    seen_request_ids.add(request_id)
                    self._record_task_snapshot(payload, persist=self._is_terminal(payload.get("status")))
                if status_filter and str(payload.get("status", "")).upper() != status_filter:
                    continue
                items.append(payload)

        for request_id, item in snapshots.items():
            if request_id in seen_request_ids:
                continue
            payload = dict(item)
            current_sid = str(payload.get("session_id", "")).strip()
            if sid and current_sid != sid:
                continue
            if status_filter and str(payload.get("status", "")).upper() != status_filter:
                continue
            items.append(payload)

        items.sort(key=lambda x: x.get("submitted_at") or 0.0, reverse=True)
        return items

    def status(self, run_id: str, task_id: str) -> dict[str, Any] | None:
        return get_task_status(run_id, task_id)

    def timeline(self, run_id: str, task_id: str) -> list[dict[str, Any]]:
        return get_task_timeline(run_id, task_id)

    def list_runtime_status(
        self,
        run_id: str | None = None,
        status: str | None = None,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return list_runtime_tasks(
            run_id=run_id,
            status=status,
            session_id=session_id,
        )

    def list_runtime_events(
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
        return list_runtime_events_api(
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

    def query_runtime_events(
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
        return query_runtime_events_api(
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

    def shutdown_session(self, session_id: str, wait: bool = True) -> bool:
        sid = str(session_id or "").strip()
        if not sid:
            return False

        with self._lock:
            record = self._sessions.pop(sid, None)
        if record is None:
            return False

        record["service"].shutdown(wait=wait)
        for request_id in record.get("request_ids", []):
            with self._lock:
                self._request_index.pop(request_id, None)
                self._task_snapshots.pop(request_id, None)
        self._persist_state()
        return True

    def shutdown(self, wait: bool = True, drop_sessions: bool = False) -> None:
        if drop_sessions:
            with self._lock:
                session_ids = list(self._sessions.keys())
            for sid in session_ids:
                self.shutdown_session(sid, wait=wait)
            return

        with self._lock:
            records = [
                (sid, record.get("service"))
                for sid, record in self._sessions.items()
            ]
        for _, service in records:
            if service is None:
                continue
            service.shutdown(wait=wait)

        with self._lock:
            for sid in list(self._sessions.keys()):
                record = self._sessions.get(sid)
                if record is None:
                    continue
                record["service"] = self._new_task_service()
        self._persist_state()

    def flush_state(self) -> None:
        self._persist_state()


_GLOBAL_SESSION_RUNTIME: SessionRuntime | None = None
_GLOBAL_SESSION_RUNTIME_LOCK = Lock()


def get_global_session_runtime(persistence_path: str | None = None) -> SessionRuntime:
    global _GLOBAL_SESSION_RUNTIME
    if _GLOBAL_SESSION_RUNTIME is not None:
        return _GLOBAL_SESSION_RUNTIME

    with _GLOBAL_SESSION_RUNTIME_LOCK:
        if _GLOBAL_SESSION_RUNTIME is None:
            _GLOBAL_SESSION_RUNTIME = SessionRuntime(persistence_path=persistence_path)
    return _GLOBAL_SESSION_RUNTIME


def submit_session_task(
    instruction: str,
    session_id: str | None = None,
    runtime_mode: str = "legacy",
    run_name: str = "test",
    task_id: str | None = None,
    run_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return get_global_session_runtime().submit_task(
        instruction=instruction,
        session_id=session_id,
        runtime_mode=runtime_mode,
        run_name=run_name,
        task_id=task_id,
        run_options=run_options,
    )


def get_session_task(request_id: str) -> dict[str, Any] | None:
    return get_global_session_runtime().get_task(request_id)


def list_session_tasks(
    session_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    return get_global_session_runtime().list_tasks(
        session_id=session_id,
        status=status,
    )


def list_sessions() -> list[dict[str, Any]]:
    return get_global_session_runtime().list_sessions()
