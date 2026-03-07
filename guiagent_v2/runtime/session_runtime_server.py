from __future__ import annotations

import argparse
import errno
import json
import os
import secrets
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .event_bus import JSONLEventBus
from .session_runtime import SessionRuntime, get_global_session_runtime
from .status_api import get_global_status_store


def _as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except Exception:
        return default

def _as_int(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except Exception:
        return default


def _first_query(params: dict[str, list[str]], name: str) -> str | None:
    values = params.get(name)
    if not values:
        return None
    value = str(values[0]).strip()
    return value or None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _sanitize_for_filename(value: str) -> str:
    normalized = str(value).strip().lower()
    if not normalized:
        return "unknown"
    return "".join(ch if ch.isalnum() else "_" for ch in normalized)


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return True
    return True


def _is_addr_in_use(exc: OSError) -> bool:
    if getattr(exc, "errno", None) == errno.EADDRINUSE:
        return True
    return "address already in use" in str(exc).lower()


def _default_lockfile_path(host: str, port: int, persistence_path: str | None) -> str:
    raw_persistence = str(persistence_path or "").strip()
    if raw_persistence:
        state_dir = os.path.dirname(raw_persistence) or "."
        return os.path.join(state_dir, "session_runtime_server.lock")
    safe_host = _sanitize_for_filename(host)
    safe_port = str(int(port)) if int(port) > 0 else "auto"
    return os.path.join(
        tempfile.gettempdir(),
        f"guiagent_session_runtime_{safe_host}_{safe_port}.lock",
    )


class SessionRuntimeAPIServer:
    """Lightweight HTTP API server for SessionRuntime IPC control plane."""

    def __init__(
        self,
        runtime: SessionRuntime | None = None,
        host: str = "127.0.0.1",
        port: int = 0,
        api_token: str | None = None,
        require_auth_on_read: bool = False,
        lockfile_path: str | None = None,
        allow_port_fallback: bool = False,
        audit_log_path: str | None = None,
    ):
        self.runtime = runtime or get_global_session_runtime()
        self.host = str(host).strip() or "127.0.0.1"
        self.port = int(port)
        self.api_token = str(api_token).strip() if api_token else None
        self.require_auth_on_read = bool(require_auth_on_read)
        self.allow_port_fallback = bool(allow_port_fallback)
        self.instance_id = "rt-" + uuid.uuid4().hex[:12]
        self.audit_log_path = str(audit_log_path).strip() if audit_log_path else None
        self._audit_bus = (
            JSONLEventBus(
                file_path=self.audit_log_path,
                default_chain_mode="guiagent_v2",
            )
            if self.audit_log_path
            else None
        )
        self._lockfile_path_input = str(lockfile_path).strip() if lockfile_path else None
        self._active_lockfile_path: str | None = None
        self._active_lock_owner_pid: int | None = None
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def address(self) -> tuple[str, int]:
        with self._lock:
            if self._server is None:
                return self.host, self.port
            return self._server.server_address

    @property
    def base_url(self) -> str:
        host, port = self.address
        return f"http://{host}:{port}"

    def _runtime_persistence_path(self) -> str | None:
        raw = getattr(self.runtime, "_persistence_path", None)
        value = str(raw).strip() if raw else ""
        return value or None

    def _resolve_lockfile_path(self) -> str:
        raw = self._lockfile_path_input
        if raw:
            if raw.endswith(os.sep) or os.path.isdir(raw):
                return os.path.join(raw, "session_runtime_server.lock")
            return raw
        return _default_lockfile_path(
            host=self.host,
            port=self.port,
            persistence_path=self._runtime_persistence_path(),
        )

    def _read_lockfile(self, path: str) -> dict[str, Any] | None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def _acquire_lockfile(self) -> None:
        lockfile_path = self._resolve_lockfile_path()
        directory = os.path.dirname(lockfile_path) or "."
        os.makedirs(directory, exist_ok=True)

        payload: dict[str, Any] = {
            "instance_id": self.instance_id,
            "pid": os.getpid(),
            "host": self.host,
            "port": int(self.port),
            "created_at": time.time(),
        }
        while True:
            try:
                fd = os.open(
                    lockfile_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
            except FileExistsError:
                existing = self._read_lockfile(lockfile_path) or {}
                existing_pid = int(existing.get("pid", 0) or 0)
                existing_instance_id = str(existing.get("instance_id", "")).strip()
                if existing_pid > 0 and not _pid_exists(existing_pid):
                    try:
                        os.remove(lockfile_path)
                        continue
                    except OSError:
                        pass
                if existing_instance_id and existing_instance_id == self.instance_id:
                    self._active_lockfile_path = lockfile_path
                    self._active_lock_owner_pid = os.getpid()
                    return
                raise RuntimeError(
                    "session runtime server lock is held by another instance: "
                    f"path={lockfile_path}, instance_id={existing.get('instance_id')}, pid={existing.get('pid')}, "
                    f"host={existing.get('host')}, port={existing.get('port')}"
                )
            else:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                self._active_lockfile_path = lockfile_path
                self._active_lock_owner_pid = os.getpid()
                return

    def _refresh_lockfile(self, *, host: str, port: int) -> None:
        path = self._active_lockfile_path
        if not path:
            return
        payload = self._read_lockfile(path) or {}
        if str(payload.get("instance_id", "")).strip() != self.instance_id:
            return
        payload["host"] = str(host)
        payload["port"] = int(port)
        payload["updated_at"] = time.time()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception:
            return

    def _release_lockfile(self) -> None:
        path = self._active_lockfile_path
        self._active_lockfile_path = None
        self._active_lock_owner_pid = None
        if not path:
            return
        payload = self._read_lockfile(path) or {}
        owner_pid = int(payload.get("pid", 0) or 0)
        instance_id = str(payload.get("instance_id", "")).strip()
        if owner_pid > 0 and owner_pid != os.getpid():
            return
        if instance_id and instance_id != self.instance_id:
            return
        try:
            os.remove(path)
        except OSError:
            return

    def _emit_control_plane_audit(
        self,
        *,
        action: str,
        method: str,
        path: str,
        status: str,
        actor: str | None,
        source: str | None,
        session_id: str | None = None,
        request_id: str | None = None,
        run_id: str | None = None,
        task_id: str | None = None,
        trace_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        resolved_request_id = str(request_id or "").strip()
        resolved_session_id = str(session_id or "").strip() or None
        resolved_run_id = str(run_id or "").strip() or "session-runtime-control-plane"
        resolved_task_id = str(task_id or "").strip()
        if not resolved_task_id:
            resolved_task_id = resolved_request_id or "control"
        payload: dict[str, Any] = {
            "run_id": resolved_run_id,
            "task_id": resolved_task_id,
            "step_id": 0,
            "chain_mode": "guiagent_v2",
            "event_type": "control_plane_audit",
            "status": str(status).upper(),
            "intent_key": "control:session-runtime:write",
            "session_id": resolved_session_id,
            "instance_id": self.instance_id,
            "control_action": str(action),
            "http_method": str(method).upper(),
            "http_path": str(path),
            "actor": str(actor or "anonymous"),
            "source": str(source or "unknown"),
        }
        if resolved_request_id:
            payload["request_id"] = resolved_request_id
        if trace_id:
            payload["trace_id"] = str(trace_id).strip()
        if detail:
            for key, value in detail.items():
                if key not in payload:
                    payload[key] = value
        if self._audit_bus is not None:
            emitted = self._audit_bus.emit(payload)
        else:
            emitted = dict(payload)
            emitted["ts"] = _utc_now_iso()
        get_global_status_store().update(emitted)

    def start(self) -> tuple[str, int]:
        with self._lock:
            if self._server is not None:
                return self._server.server_address
            self._acquire_lockfile()
            bind_port = int(self.port)
            server: ThreadingHTTPServer | None = None
            try:
                try:
                    server = ThreadingHTTPServer((self.host, bind_port), self._build_handler())
                except OSError as exc:
                    if self.allow_port_fallback and bind_port > 0 and _is_addr_in_use(exc):
                        server = ThreadingHTTPServer((self.host, 0), self._build_handler())
                    else:
                        raise
                thread = threading.Thread(
                    target=server.serve_forever,
                    name="guiagent-session-runtime-api",
                    daemon=True,
                )
                thread.start()
                self._server = server
                self._thread = thread
                bound_host, bound_port = server.server_address
                self.host = str(bound_host).strip() or self.host
                self.port = int(bound_port)
                self._refresh_lockfile(host=self.host, port=self.port)
                return server.server_address
            except Exception:
                if server is not None:
                    try:
                        server.server_close()
                    except Exception:
                        pass
                self._release_lockfile()
                raise

    def stop(self) -> None:
        with self._lock:
            server = self._server
            thread = self._thread
            self._server = None
            self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2.0)
        self._release_lockfile()

    def _build_handler(self):
        runtime = self.runtime
        api_token = self.api_token
        require_auth_on_read = self.require_auth_on_read
        server_instance = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):  # noqa: A003
                del format, args

            def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("X-Session-Runtime-Instance-Id", server_instance.instance_id)
                self.end_headers()
                self.wfile.write(body)

            def _ok(self, data: Any, status_code: int = 200) -> None:
                self._send_json(status_code, {"ok": True, "data": data})

            def _error(self, code: str, message: str, status_code: int = 400) -> None:
                self._send_json(
                    status_code,
                    {
                        "ok": False,
                        "error": {
                            "code": code,
                            "message": message,
                        },
                    },
                )

            def _extract_api_token(self) -> str | None:
                auth_header = str(self.headers.get("Authorization", "")).strip()
                if auth_header.lower().startswith("bearer "):
                    token = auth_header[7:].strip()
                    return token or None

                token_header = str(self.headers.get("X-API-Token", "")).strip()
                if token_header:
                    return token_header
                return None

            def _actor(self, payload: dict[str, Any] | None = None) -> str:
                actor = str(self.headers.get("X-Actor", "")).strip()
                if actor:
                    return actor
                if isinstance(payload, dict):
                    actor = str(payload.get("actor", "")).strip()
                    if actor:
                        return actor
                return "anonymous"

            def _source(self, payload: dict[str, Any] | None = None) -> str:
                source = str(self.headers.get("X-Source", "")).strip()
                if source:
                    return source
                if isinstance(payload, dict):
                    source = str(payload.get("source", "")).strip()
                    if source:
                        return source
                return str(self.client_address[0] if self.client_address else "unknown")

            def _trace_id(self, payload: dict[str, Any] | None = None) -> str | None:
                trace_id = str(self.headers.get("X-Trace-Id", "")).strip()
                if trace_id:
                    return trace_id
                request_id = str(self.headers.get("X-Request-Id", "")).strip()
                if request_id:
                    return request_id
                if isinstance(payload, dict):
                    trace_id = str(payload.get("trace_id", "")).strip()
                    if trace_id:
                        return trace_id
                return None

            def _audit_write(
                self,
                *,
                action: str,
                method: str,
                path: str,
                status: str,
                payload: dict[str, Any] | None = None,
                session_id: str | None = None,
                request_id: str | None = None,
                run_id: str | None = None,
                task_id: str | None = None,
                detail: dict[str, Any] | None = None,
            ) -> None:
                server_instance._emit_control_plane_audit(
                    action=action,
                    method=method,
                    path=path,
                    status=status,
                    actor=self._actor(payload),
                    source=self._source(payload),
                    session_id=session_id,
                    request_id=request_id,
                    run_id=run_id,
                    task_id=task_id,
                    trace_id=self._trace_id(payload),
                    detail=detail,
                )

            def _check_auth(self, write: bool, method: str, path: str) -> bool:
                if not api_token:
                    return True
                if not write and not require_auth_on_read:
                    return True

                provided = self._extract_api_token()
                if provided and secrets.compare_digest(str(provided), str(api_token)):
                    return True
                self._error("UNAUTHORIZED", "missing or invalid api token", status_code=401)
                if write:
                    self._audit_write(
                        action="auth_rejected",
                        method=method,
                        path=path,
                        status="FAILED",
                        detail={"reason_code": "UNAUTHORIZED"},
                    )
                return False

            def _read_json_body(self) -> dict[str, Any]:
                raw_length = self.headers.get("Content-Length", "0")
                try:
                    length = max(0, int(raw_length))
                except Exception:
                    length = 0
                if length <= 0:
                    return {}
                raw = self.rfile.read(length)
                if not raw:
                    return {}
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except Exception as exc:
                    raise ValueError(f"invalid json body: {exc}") from exc
                if not isinstance(payload, dict):
                    raise ValueError("json body must be an object")
                return payload

            def do_GET(self):  # noqa: N802
                parsed = urlparse(self.path)
                path = parsed.path or "/"
                params = parse_qs(parsed.query, keep_blank_values=False)

                if path == "/health":
                    self._ok(
                        {
                            "status": "ok",
                            "instance_id": server_instance.instance_id,
                            "pid": os.getpid(),
                        }
                    )
                    return

                if not self._check_auth(write=False, method="GET", path=path):
                    return

                if path == "/sessions":
                    self._ok({"sessions": runtime.list_sessions()})
                    return

                if path.startswith("/sessions/"):
                    session_id = path.split("/", 2)[2].strip()
                    session = runtime.get_session(session_id)
                    if session is None:
                        self._error("SESSION_NOT_FOUND", f"session not found: {session_id}", status_code=404)
                        return
                    self._ok(session)
                    return

                if path == "/tasks":
                    self._ok(
                        {
                            "tasks": runtime.list_tasks(
                                session_id=_first_query(params, "session_id"),
                                status=_first_query(params, "status"),
                            )
                        }
                    )
                    return

                if path.startswith("/tasks/"):
                    request_id = path.split("/", 2)[2].strip()
                    task = runtime.get_task(request_id)
                    if task is None:
                        self._error("TASK_NOT_FOUND", f"task not found: {request_id}", status_code=404)
                        return
                    self._ok(task)
                    return

                if path == "/runtime/status":
                    self._ok(
                        {
                            "items": runtime.list_runtime_status(
                                run_id=_first_query(params, "run_id"),
                                status=_first_query(params, "status"),
                                session_id=_first_query(params, "session_id"),
                            )
                        }
                    )
                    return

                if path == "/runtime/audit":
                    event_type = _first_query(params, "event_type")
                    if event_type is None:
                        event_type = "control_plane_audit"
                    limit = _as_int(_first_query(params, "limit"), default=100)
                    cursor = _as_int(_first_query(params, "cursor"), default=0)
                    self._ok(
                        runtime.query_runtime_events(
                            run_id=_first_query(params, "run_id"),
                            task_id=_first_query(params, "task_id"),
                            session_id=_first_query(params, "session_id"),
                            event_type=event_type,
                            actor=_first_query(params, "actor"),
                            source=_first_query(params, "source"),
                            control_action=_first_query(params, "control_action"),
                            status=_first_query(params, "status"),
                            limit=limit,
                            cursor=cursor,
                            since_ts=_first_query(params, "since_ts"),
                            until_ts=_first_query(params, "until_ts"),
                        )
                    )
                    return

                if path.startswith("/runtime/status/"):
                    tail = path[len("/runtime/status/") :]
                    if "/" not in tail:
                        self._error(
                            "INVALID_PATH",
                            "expect /runtime/status/{run_id}/{task_id}",
                            status_code=404,
                        )
                        return
                    run_id, task_id = tail.split("/", 1)
                    item = runtime.status(run_id=run_id, task_id=task_id)
                    if item is None:
                        self._error(
                            "RUNTIME_STATUS_NOT_FOUND",
                            f"status not found: run_id={run_id} task_id={task_id}",
                            status_code=404,
                        )
                        return
                    self._ok(item)
                    return

                if path.startswith("/runtime/timeline/"):
                    tail = path[len("/runtime/timeline/") :]
                    if "/" not in tail:
                        self._error(
                            "INVALID_PATH",
                            "expect /runtime/timeline/{run_id}/{task_id}",
                            status_code=404,
                        )
                        return
                    run_id, task_id = tail.split("/", 1)
                    self._ok({"timeline": runtime.timeline(run_id=run_id, task_id=task_id)})
                    return

                self._error("NOT_FOUND", f"path not found: {path}", status_code=404)

            def do_POST(self):  # noqa: N802
                parsed = urlparse(self.path)
                path = parsed.path or "/"
                if not self._check_auth(write=True, method="POST", path=path):
                    return
                try:
                    payload = self._read_json_body()
                except ValueError as exc:
                    self._error("INVALID_BODY", str(exc), status_code=400)
                    self._audit_write(
                        action="invalid_body",
                        method="POST",
                        path=path,
                        status="FAILED",
                        detail={"reason_code": "INVALID_BODY"},
                    )
                    return

                if path == "/sessions":
                    session = runtime.ensure_session(
                        session_id=payload.get("session_id"),
                        metadata=payload.get("metadata"),
                    )
                    self._audit_write(
                        action="ensure_session",
                        method="POST",
                        path=path,
                        status="SUCCESS",
                        payload=payload,
                        session_id=session.get("session_id"),
                    )
                    self._ok(session, status_code=201)
                    return

                if path == "/tasks":
                    instruction = str(payload.get("instruction", "")).strip()
                    if not instruction:
                        self._error("INVALID_INSTRUCTION", "instruction must not be empty", status_code=400)
                        self._audit_write(
                            action="submit_task",
                            method="POST",
                            path=path,
                            status="FAILED",
                            payload=payload,
                            session_id=str(payload.get("session_id", "")).strip() or None,
                            detail={"reason_code": "INVALID_INSTRUCTION"},
                        )
                        return
                    try:
                        item = runtime.submit_task(
                            instruction=instruction,
                            session_id=payload.get("session_id"),
                            runtime_mode=str(payload.get("runtime_mode", "legacy")),
                            run_name=str(payload.get("run_name", "api")),
                            task_id=payload.get("task_id"),
                            run_options=payload.get("run_options"),
                        )
                    except Exception as exc:
                        self._error("TASK_SUBMIT_FAILED", str(exc), status_code=500)
                        self._audit_write(
                            action="submit_task",
                            method="POST",
                            path=path,
                            status="FAILED",
                            payload=payload,
                            session_id=str(payload.get("session_id", "")).strip() or None,
                            detail={"reason_code": "TASK_SUBMIT_FAILED"},
                        )
                        return
                    self._audit_write(
                        action="submit_task",
                        method="POST",
                        path=path,
                        status="SUCCESS",
                        payload=payload,
                        session_id=item.get("session_id"),
                        request_id=item.get("request_id"),
                        run_id=item.get("run_id"),
                        task_id=item.get("task_id"),
                    )
                    self._ok(item, status_code=201)
                    return

                if path.startswith("/tasks/") and path.endswith("/wait"):
                    request_id = path[len("/tasks/") : -len("/wait")].strip("/")
                    timeout = _as_float(payload.get("timeout"), default=None)
                    item = runtime.wait(request_id=request_id, timeout=timeout)
                    if item is None:
                        self._error("TASK_NOT_FOUND", f"task not found: {request_id}", status_code=404)
                        self._audit_write(
                            action="wait_task",
                            method="POST",
                            path=path,
                            status="FAILED",
                            payload=payload,
                            request_id=request_id,
                            detail={"reason_code": "TASK_NOT_FOUND"},
                        )
                        return
                    self._audit_write(
                        action="wait_task",
                        method="POST",
                        path=path,
                        status="SUCCESS",
                        payload=payload,
                        session_id=item.get("session_id"),
                        request_id=request_id,
                        run_id=item.get("run_id"),
                        task_id=item.get("task_id"),
                    )
                    self._ok(item)
                    return

                self._error("NOT_FOUND", f"path not found: {path}", status_code=404)
                self._audit_write(
                    action="unknown_write_path",
                    method="POST",
                    path=path,
                    status="FAILED",
                    payload=payload,
                    detail={"reason_code": "NOT_FOUND"},
                )

            def do_DELETE(self):  # noqa: N802
                parsed = urlparse(self.path)
                path = parsed.path or "/"
                if not self._check_auth(write=True, method="DELETE", path=path):
                    return
                if path.startswith("/sessions/"):
                    session_id = path.split("/", 2)[2].strip()
                    removed = runtime.shutdown_session(session_id=session_id, wait=True)
                    if not removed:
                        self._error("SESSION_NOT_FOUND", f"session not found: {session_id}", status_code=404)
                        self._audit_write(
                            action="delete_session",
                            method="DELETE",
                            path=path,
                            status="FAILED",
                            session_id=session_id,
                            detail={"reason_code": "SESSION_NOT_FOUND"},
                        )
                        return
                    self._audit_write(
                        action="delete_session",
                        method="DELETE",
                        path=path,
                        status="SUCCESS",
                        session_id=session_id,
                    )
                    self._ok({"session_id": session_id, "removed": True})
                    return
                self._error("NOT_FOUND", f"path not found: {path}", status_code=404)
                self._audit_write(
                    action="unknown_write_path",
                    method="DELETE",
                    path=path,
                    status="FAILED",
                    detail={"reason_code": "NOT_FOUND"},
                )

        return Handler


_GLOBAL_API_SERVER: SessionRuntimeAPIServer | None = None
_GLOBAL_API_SERVER_LOCK = threading.Lock()


def get_global_session_runtime_server(
    persistence_path: str | None = None,
    api_token: str | None = None,
    require_auth_on_read: bool = False,
    lockfile_path: str | None = None,
    allow_port_fallback: bool = False,
    audit_log_path: str | None = None,
) -> SessionRuntimeAPIServer:
    global _GLOBAL_API_SERVER
    if _GLOBAL_API_SERVER is not None:
        return _GLOBAL_API_SERVER
    with _GLOBAL_API_SERVER_LOCK:
        if _GLOBAL_API_SERVER is None:
            _GLOBAL_API_SERVER = SessionRuntimeAPIServer(
                runtime=get_global_session_runtime(persistence_path=persistence_path),
                api_token=api_token,
                require_auth_on_read=require_auth_on_read,
                lockfile_path=lockfile_path,
                allow_port_fallback=allow_port_fallback,
                audit_log_path=audit_log_path,
            )
    return _GLOBAL_API_SERVER


def start_global_session_runtime_server(
    host: str = "127.0.0.1",
    port: int = 8787,
    persistence_path: str | None = None,
    api_token: str | None = None,
    require_auth_on_read: bool = False,
    lockfile_path: str | None = None,
    allow_port_fallback: bool = False,
    audit_log_path: str | None = None,
) -> tuple[str, int]:
    server = get_global_session_runtime_server(
        persistence_path=persistence_path,
        api_token=api_token,
        require_auth_on_read=require_auth_on_read,
        lockfile_path=lockfile_path,
        allow_port_fallback=allow_port_fallback,
        audit_log_path=audit_log_path,
    )
    server.host = host
    server.port = int(port)
    return server.start()


def stop_global_session_runtime_server() -> None:
    global _GLOBAL_API_SERVER
    with _GLOBAL_API_SERVER_LOCK:
        server = _GLOBAL_API_SERVER
        _GLOBAL_API_SERVER = None
    if server is not None:
        server.stop()


def _main() -> None:
    parser = argparse.ArgumentParser(description="SessionRuntime HTTP API server")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--persistence_path", type=str, default=None)
    parser.add_argument("--api_token", type=str, default=None)
    parser.add_argument("--require_auth_on_read", action="store_true", default=False)
    parser.add_argument("--lockfile_path", type=str, default=None)
    parser.add_argument("--allow_port_fallback", action="store_true", default=False)
    parser.add_argument("--audit_log_path", type=str, default=None)
    args = parser.parse_args()

    api_token = args.api_token or os.getenv("GUIAGENT_SESSION_RUNTIME_API_TOKEN")

    server = SessionRuntimeAPIServer(
        runtime=SessionRuntime(persistence_path=args.persistence_path),
        host=args.host,
        port=args.port,
        api_token=api_token,
        require_auth_on_read=args.require_auth_on_read,
        lockfile_path=args.lockfile_path,
        allow_port_fallback=args.allow_port_fallback,
        audit_log_path=args.audit_log_path,
    )
    host, port = server.start()
    print(f"SessionRuntime API server started at http://{host}:{port}")
    try:
        while True:
            threading.Event().wait(3600)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()


if __name__ == "__main__":
    _main()
