from __future__ import annotations

import time
import uuid
from copy import deepcopy
from threading import Lock
from typing import Any

from .status_api import get_task_status, get_task_timeline, list_tasks as list_runtime_tasks
from .task_service import RuntimeTaskService, RunnerCallable


class SessionRuntime:
    """Session-scoped runtime task manager with per-session isolation."""

    def __init__(
        self,
        runner: RunnerCallable | None = None,
        per_session_max_workers: int = 1,
    ):
        self._runner = runner
        self._per_session_max_workers = max(1, int(per_session_max_workers))
        self._lock = Lock()
        self._sessions: dict[str, dict[str, Any]] = {}
        self._request_index: dict[str, str] = {}

    def _generate_session_id(self) -> str:
        return "sess-" + uuid.uuid4().hex[:8]

    def _get_or_create_service(self, session_id: str) -> RuntimeTaskService:
        record = self._sessions.get(session_id)
        if record is None:
            raise KeyError(f"unknown session_id: {session_id}")
        return record["service"]

    def ensure_session(
        self,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata = dict(metadata or {})
        with self._lock:
            sid = str(session_id or "").strip() or self._generate_session_id()
            existing = self._sessions.get(sid)
            if existing is None:
                service = RuntimeTaskService(
                    runner=self._runner,
                    max_workers=self._per_session_max_workers,
                )
                now = time.time()
                self._sessions[sid] = {
                    "session_id": sid,
                    "created_at": now,
                    "updated_at": now,
                    "metadata": metadata,
                    "service": service,
                    "request_ids": [],
                }
            else:
                if metadata:
                    existing["metadata"].update(metadata)
                existing["updated_at"] = time.time()
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
                    record["request_ids"].append(request_id)
                    self._request_index[request_id] = sid

        payload = dict(submitted)
        payload["session_id"] = sid
        return payload

    def get_task(self, request_id: str) -> dict[str, Any] | None:
        rid = str(request_id or "").strip()
        if not rid:
            return None

        with self._lock:
            sid = self._request_index.get(rid)
            if sid is None:
                return None
            service = self._get_or_create_service(sid)

        item = service.get_task(rid)
        if item is None:
            return None
        payload = dict(item)
        payload["session_id"] = sid
        return payload

    def wait(self, request_id: str, timeout: float | None = None) -> dict[str, Any] | None:
        rid = str(request_id or "").strip()
        if not rid:
            return None

        with self._lock:
            sid = self._request_index.get(rid)
            if sid is None:
                return None
            service = self._get_or_create_service(sid)

        item = service.wait(rid, timeout=timeout)
        if item is None:
            return None
        payload = dict(item)
        payload["session_id"] = sid
        return payload

    def list_tasks(
        self,
        session_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        sid = str(session_id or "").strip() if session_id else None
        with self._lock:
            if sid:
                record = self._sessions.get(sid)
                if record is None:
                    return []
                services = [(sid, record["service"])]
            else:
                services = [(key, value["service"]) for key, value in self._sessions.items()]

        items: list[dict[str, Any]] = []
        for current_sid, service in services:
            for item in service.list_tasks(status=status):
                payload = dict(item)
                payload["session_id"] = current_sid
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

    def shutdown_session(self, session_id: str, wait: bool = True) -> bool:
        sid = str(session_id or "").strip()
        if not sid:
            return False

        with self._lock:
            record = self._sessions.pop(sid, None)
        if record is None:
            return False

        for request_id in record.get("request_ids", []):
            self._request_index.pop(request_id, None)
        record["service"].shutdown(wait=wait)
        return True

    def shutdown(self, wait: bool = True) -> None:
        with self._lock:
            session_ids = list(self._sessions.keys())
        for sid in session_ids:
            self.shutdown_session(sid, wait=wait)


_GLOBAL_SESSION_RUNTIME: SessionRuntime | None = None
_GLOBAL_SESSION_RUNTIME_LOCK = Lock()


def get_global_session_runtime() -> SessionRuntime:
    global _GLOBAL_SESSION_RUNTIME
    if _GLOBAL_SESSION_RUNTIME is not None:
        return _GLOBAL_SESSION_RUNTIME

    with _GLOBAL_SESSION_RUNTIME_LOCK:
        if _GLOBAL_SESSION_RUNTIME is None:
            _GLOBAL_SESSION_RUNTIME = SessionRuntime()
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
