from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class WebAutomationAdapter:
    """Abstract adapter for external web automation backends."""

    def start_session(self, session_id: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def snapshot(self, session_id: str, mode: str = "interactive") -> dict[str, Any]:
        raise NotImplementedError

    def diff(
        self,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
        mode: str = "text+image",
    ) -> dict[str, Any]:
        raise NotImplementedError

    def stop_session(self, session_id: str) -> dict[str, Any]:
        raise NotImplementedError


_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _default_agent_browser_project_dir() -> Path:
    preferred = _PROJECT_ROOT / "third_party" / "agent-browser"
    if preferred.exists():
        return preferred
    return _PROJECT_ROOT / "demo" / "agent-browser"


_DEFAULT_LOCAL_AGENT_BROWSER_DIR = _default_agent_browser_project_dir()
_DEFAULT_LOCAL_AGENT_BROWSER_BIN = _DEFAULT_LOCAL_AGENT_BROWSER_DIR / "bin" / "agent-browser.js"


@dataclass
class AgentBrowserCLIAdapter(WebAutomationAdapter):
    """Run agent-browser as an external process and normalize responses."""

    executable: str = field(default_factory=lambda: str(os.environ.get("AGENT_BROWSER_EXECUTABLE", "")).strip())
    project_dir: str = field(
        default_factory=lambda: str(
            os.environ.get("AGENT_BROWSER_PROJECT_DIR", str(_DEFAULT_LOCAL_AGENT_BROWSER_DIR))
        ).strip()
    )
    prefer_local: bool = field(
        default_factory=lambda: str(os.environ.get("AGENT_BROWSER_PREFER_LOCAL", "1")).strip().lower()
        in {"1", "true", "yes", "on"}
    )
    force_native: bool = field(
        default_factory=lambda: str(os.environ.get("AGENT_BROWSER_FORCE_NATIVE", "1")).strip().lower()
        in {"1", "true", "yes", "on"}
    )
    default_session: str = "default"
    timeout_sec: float = 20.0
    extra_env: dict[str, str] = field(default_factory=dict)

    def start_session(self, session_id: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        del options
        return self._run_cli(["session"], session_id=session_id)

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        request = dict(request or {})
        session_id = str(request.pop("session_id", self.default_session)).strip() or self.default_session

        command = request.get("command")
        if isinstance(command, str):
            command_tokens = shlex.split(command)
        elif isinstance(command, list):
            command_tokens = [str(token) for token in command if str(token).strip()]
        else:
            command_tokens = self._map_request_to_command(request)

        if not command_tokens:
            return {
                "success": False,
                "error": "UNSUPPORTED_REQUEST",
                "session_id": session_id,
                "request": request,
            }

        result = self._run_cli(command_tokens, session_id=session_id)
        result["request"] = request
        return result

    def snapshot(self, session_id: str, mode: str = "interactive") -> dict[str, Any]:
        args = ["snapshot"]
        if "interactive" in str(mode).lower():
            args.append("--interactive")
        return self._run_cli(args, session_id=session_id)

    def diff(
        self,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
        mode: str = "text+image",
    ) -> dict[str, Any]:
        before = before or {}
        after = after or {}
        session_id = str(after.get("session_id") or before.get("session_id") or self.default_session)
        args = ["diff", "snapshot"]
        baseline = str(before.get("baseline_path", "")).strip()
        selector = str(after.get("selector", "")).strip()
        max_depth = after.get("max_depth")

        if baseline:
            args.extend(["--baseline", baseline])
        if selector:
            args.extend(["--selector", selector])
        if "text" in str(mode).lower():
            args.append("--compact")
        if isinstance(max_depth, int) and max_depth > 0:
            args.extend(["--depth", str(max_depth)])

        return self._run_cli(args, session_id=session_id)

    def stop_session(self, session_id: str) -> dict[str, Any]:
        return {
            "success": True,
            "error": None,
            "data": {"session": session_id, "stopped": False, "mode": "daemon-managed"},
            "session_id": session_id,
        }

    def _resolve_command_candidates(self, args: list[str], session_id: str) -> list[tuple[list[str], str | None, str]]:
        prefix: list[str] = ["--native"] if bool(self.force_native) else []
        suffix = [*prefix, "--json", "--session", session_id, *args]
        candidates: list[tuple[list[str], str | None, str]] = []

        explicit = str(self.executable or "").strip()
        if explicit:
            explicit_tokens = shlex.split(explicit)
            candidates.append(([*explicit_tokens, *suffix], None, "explicit"))
            return candidates

        if self.prefer_local:
            local_project_dir = Path(self.project_dir).expanduser().resolve()
            local_bin = local_project_dir / "bin" / "agent-browser.js"
            if local_bin.exists():
                candidates.append((["node", str(local_bin), *suffix], str(local_project_dir), "local_node"))

        candidates.append((["agent-browser", *suffix], None, "global"))
        return candidates

    def _run_cli(self, args: list[str], session_id: str) -> dict[str, Any]:
        env = os.environ.copy()
        env.update(self.extra_env)
        candidates = self._resolve_command_candidates(args=args, session_id=session_id)
        first_missing: list[str] | None = None
        first_timeout: list[str] | None = None
        last_result: dict[str, Any] | None = None

        for command, cwd, source in candidates:
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_sec,
                    check=False,
                    env=env,
                    cwd=cwd,
                )
            except FileNotFoundError:
                if first_missing is None:
                    first_missing = list(command)
                continue
            except subprocess.TimeoutExpired:
                if first_timeout is None:
                    first_timeout = list(command)
                continue

            parsed = self._parse_stdout(completed.stdout)
            success = bool(parsed.get("success")) if parsed else completed.returncode == 0
            error = None
            data = None
            if parsed:
                error = parsed.get("error")
                data = parsed.get("data")
            if not success and not error:
                error = completed.stderr.strip() or f"CLI_EXIT_{completed.returncode}"

            result = {
                "success": success,
                "error": error,
                "data": data,
                "session_id": session_id,
                "command": command,
                "return_code": completed.returncode,
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
                "adapter_source": source,
            }
            last_result = result
            if success:
                return result
            if source == "local_node" and "No binary found for" in str(result.get("stderr", "")):
                continue
            return result

        if first_timeout is not None:
            return {
                "success": False,
                "error": "CLI_TIMEOUT",
                "data": None,
                "session_id": session_id,
                "command": first_timeout,
            }
        if first_missing is not None:
            return {
                "success": False,
                "error": "CLI_NOT_FOUND",
                "data": None,
                "session_id": session_id,
                "command": first_missing,
                "hint": "Run scripts/setup_agent_browser_local.sh to install local agent-browser runtime.",
            }
        return last_result or {
            "success": False,
            "error": "CLI_NOT_FOUND",
            "data": None,
            "session_id": session_id,
            "command": ["agent-browser"],
            "hint": "Run scripts/setup_agent_browser_local.sh to install local agent-browser runtime.",
        }

    @staticmethod
    def _parse_stdout(stdout: str) -> dict[str, Any] | None:
        lines = [line.strip() for line in (stdout or "").splitlines() if line.strip()]
        for line in reversed(lines):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and "success" in payload:
                return payload
        return None

    @staticmethod
    def _map_request_to_command(request: dict[str, Any]) -> list[str]:
        action = str(request.get("action", "")).strip().lower()
        params = dict(request.get("params", {})) if isinstance(request.get("params"), dict) else {}

        if action in {"open", "navigate", "goto"}:
            url = str(request.get("url") or params.get("url") or "").strip()
            return ["open", url] if url else []

        if action in {"click", "dblclick", "hover", "focus", "check", "uncheck"}:
            selector = str(request.get("selector") or params.get("selector") or "").strip()
            return [action, selector] if selector else []

        if action in {"type", "fill"}:
            selector = str(request.get("selector") or params.get("selector") or "").strip()
            text = str(request.get("text") or request.get("value") or params.get("text") or "").strip()
            return [action, selector, text] if selector and text else []

        if action == "wait":
            selector = str(request.get("selector") or params.get("selector") or "").strip()
            milliseconds = request.get("ms")
            if selector:
                return ["wait", selector]
            if isinstance(milliseconds, int) and milliseconds > 0:
                return ["wait", str(milliseconds)]
            return ["wait", "1000"]

        if action == "screenshot":
            selector = str(request.get("selector") or params.get("selector") or "").strip()
            path = str(request.get("path") or params.get("path") or "").strip()
            if selector and path:
                return ["screenshot", selector, path]
            if selector:
                return ["screenshot", selector]
            if path:
                return ["screenshot", path]
            return ["screenshot"]

        if action == "snapshot":
            args = ["snapshot"]
            if bool(request.get("interactive") or params.get("interactive")):
                args.append("--interactive")
            if bool(request.get("compact") or params.get("compact")):
                args.append("--compact")
            selector = str(request.get("selector") or params.get("selector") or "").strip()
            if selector:
                args.extend(["--selector", selector])
            max_depth = request.get("max_depth") or params.get("max_depth")
            if isinstance(max_depth, int) and max_depth > 0:
                args.extend(["--depth", str(max_depth)])
            return args

        if action == "eval":
            script = str(request.get("script") or params.get("script") or "").strip()
            return ["eval", script] if script else []

        if action == "diff_snapshot":
            args = ["diff", "snapshot"]
            baseline = str(request.get("baseline_path") or params.get("baseline_path") or "").strip()
            selector = str(request.get("selector") or params.get("selector") or "").strip()
            if baseline:
                args.extend(["--baseline", baseline])
            if selector:
                args.extend(["--selector", selector])
            if bool(request.get("compact") or params.get("compact")):
                args.append("--compact")
            max_depth = request.get("max_depth") or params.get("max_depth")
            if isinstance(max_depth, int) and max_depth > 0:
                args.extend(["--depth", str(max_depth)])
            return args

        return []


@dataclass
class AgentBrowserSkill:
    """Skill-style wrapper over the web automation adapter."""

    adapter: WebAutomationAdapter = field(default_factory=AgentBrowserCLIAdapter)
    skill_name: str = "AgentBrowserSkill"

    def invoke(
        self,
        task: dict[str, Any] | str,
        session: dict[str, Any] | str | None = None,
        constraints: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        constraints = constraints or {}

        if isinstance(session, dict):
            session_id = str(session.get("session_id") or session.get("id") or "default")
        elif isinstance(session, str):
            session_id = session
        else:
            session_id = "default"
        session_id = session_id.strip() or "default"

        if isinstance(task, str):
            task_request = {"action": "open", "url": task}
        elif isinstance(task, dict):
            task_request = dict(task)
        else:
            return {
                "success": False,
                "result": None,
                "trace": [],
                "error": "INVALID_TASK",
            }

        task_request.setdefault("session_id", session_id)

        if bool(constraints.get("ensure_session", False)):
            start_result = self.adapter.start_session(session_id, options=constraints)
            if not start_result.get("success", False):
                return {
                    "success": False,
                    "result": start_result.get("data"),
                    "trace": [{"phase": "start_session", "result": start_result}],
                    "error": start_result.get("error") or "SESSION_START_FAILED",
                }

        result = self.adapter.execute(task_request)
        trace = [
            {
                "phase": "execute",
                "request": task_request,
                "command": result.get("command"),
                "session_id": result.get("session_id"),
            }
        ]
        return {
            "success": bool(result.get("success", False)),
            "result": result.get("data"),
            "trace": trace,
            "error": result.get("error"),
            "raw": result,
        }
