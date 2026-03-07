from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .session_runtime import SessionRuntime, get_global_session_runtime


def _as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except Exception:
        return default


def _first_query(params: dict[str, list[str]], name: str) -> str | None:
    values = params.get(name)
    if not values:
        return None
    value = str(values[0]).strip()
    return value or None


class SessionRuntimeAPIServer:
    """Lightweight HTTP API server for SessionRuntime IPC control plane."""

    def __init__(
        self,
        runtime: SessionRuntime | None = None,
        host: str = "127.0.0.1",
        port: int = 0,
    ):
        self.runtime = runtime or get_global_session_runtime()
        self.host = str(host).strip() or "127.0.0.1"
        self.port = int(port)
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

    def start(self) -> tuple[str, int]:
        with self._lock:
            if self._server is not None:
                return self._server.server_address
            server = ThreadingHTTPServer((self.host, self.port), self._build_handler())
            thread = threading.Thread(
                target=server.serve_forever,
                name="guiagent-session-runtime-api",
                daemon=True,
            )
            thread.start()
            self._server = server
            self._thread = thread
            return server.server_address

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

    def _build_handler(self):
        runtime = self.runtime

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):  # noqa: A003
                del format, args

            def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
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
                    self._ok({"status": "ok"})
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
                try:
                    payload = self._read_json_body()
                except ValueError as exc:
                    self._error("INVALID_BODY", str(exc), status_code=400)
                    return

                if path == "/sessions":
                    session = runtime.ensure_session(
                        session_id=payload.get("session_id"),
                        metadata=payload.get("metadata"),
                    )
                    self._ok(session, status_code=201)
                    return

                if path == "/tasks":
                    instruction = str(payload.get("instruction", "")).strip()
                    if not instruction:
                        self._error("INVALID_INSTRUCTION", "instruction must not be empty", status_code=400)
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
                        return
                    self._ok(item, status_code=201)
                    return

                if path.startswith("/tasks/") and path.endswith("/wait"):
                    request_id = path[len("/tasks/") : -len("/wait")].strip("/")
                    timeout = _as_float(payload.get("timeout"), default=None)
                    item = runtime.wait(request_id=request_id, timeout=timeout)
                    if item is None:
                        self._error("TASK_NOT_FOUND", f"task not found: {request_id}", status_code=404)
                        return
                    self._ok(item)
                    return

                self._error("NOT_FOUND", f"path not found: {path}", status_code=404)

            def do_DELETE(self):  # noqa: N802
                parsed = urlparse(self.path)
                path = parsed.path or "/"
                if path.startswith("/sessions/"):
                    session_id = path.split("/", 2)[2].strip()
                    removed = runtime.shutdown_session(session_id=session_id, wait=True)
                    if not removed:
                        self._error("SESSION_NOT_FOUND", f"session not found: {session_id}", status_code=404)
                        return
                    self._ok({"session_id": session_id, "removed": True})
                    return
                self._error("NOT_FOUND", f"path not found: {path}", status_code=404)

        return Handler


_GLOBAL_API_SERVER: SessionRuntimeAPIServer | None = None
_GLOBAL_API_SERVER_LOCK = threading.Lock()


def get_global_session_runtime_server() -> SessionRuntimeAPIServer:
    global _GLOBAL_API_SERVER
    if _GLOBAL_API_SERVER is not None:
        return _GLOBAL_API_SERVER
    with _GLOBAL_API_SERVER_LOCK:
        if _GLOBAL_API_SERVER is None:
            _GLOBAL_API_SERVER = SessionRuntimeAPIServer()
    return _GLOBAL_API_SERVER


def start_global_session_runtime_server(host: str = "127.0.0.1", port: int = 8787) -> tuple[str, int]:
    server = get_global_session_runtime_server()
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
    args = parser.parse_args()

    server = SessionRuntimeAPIServer(host=args.host, port=args.port)
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
