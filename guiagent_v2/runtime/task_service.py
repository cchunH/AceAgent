from __future__ import annotations

import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from copy import deepcopy
from threading import Lock
from typing import Any, Callable

from .status_api import get_task_status


RunnerCallable = Callable[..., dict[str, Any]]


class RuntimeTaskService:
    """In-process task queue for future chat-task assignment and status tracking."""

    def __init__(
        self,
        runner: RunnerCallable | None = None,
        max_workers: int = 1,
    ):
        self._runner = runner
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="guiagent-task",
        )
        self._lock = Lock()
        self._tasks: dict[str, dict[str, Any]] = {}
        self._futures: dict[str, Future] = {}

    def _resolve_runner(self) -> RunnerCallable:
        if self._runner is not None:
            return self._runner

        from .orchestrator_v2 import run_single_task_with_runtime

        self._runner = run_single_task_with_runtime
        return self._runner

    def submit_task(
        self,
        instruction: str,
        runtime_mode: str = "legacy",
        run_name: str = "test",
        task_id: str | None = None,
        run_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        instruction = str(instruction or "").strip()
        if not instruction:
            raise ValueError("instruction must not be empty")

        run_options = dict(run_options or {})
        if task_id is None:
            task_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        run_id = f"{run_name}:{task_id}"
        request_id = "req-" + uuid.uuid4().hex
        now = time.time()

        record = {
            "request_id": request_id,
            "instruction": instruction,
            "runtime_mode": runtime_mode,
            "run_name": run_name,
            "run_id": run_id,
            "task_id": task_id,
            "status": "QUEUED",
            "submitted_at": now,
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
        }
        with self._lock:
            self._tasks[request_id] = record

        future = self._executor.submit(
            self._run_task,
            request_id=request_id,
            instruction=instruction,
            runtime_mode=runtime_mode,
            run_name=run_name,
            task_id=task_id,
            run_options=run_options,
        )
        with self._lock:
            self._futures[request_id] = future

        return self.get_task(request_id) or deepcopy(record)

    def _run_task(
        self,
        request_id: str,
        instruction: str,
        runtime_mode: str,
        run_name: str,
        task_id: str,
        run_options: dict[str, Any],
    ) -> None:
        with self._lock:
            task = self._tasks.get(request_id)
            if task is None:
                return
            task["status"] = "RUNNING"
            task["started_at"] = time.time()

        try:
            runner = self._resolve_runner()
            result = runner(
                instruction=instruction,
                run_name=run_name,
                task_id=task_id,
                runtime_mode=runtime_mode,
                **run_options,
            )
            final_status = "SUCCESS"
            if isinstance(result, dict):
                final_status = str(result.get("status", final_status)).upper()
                if final_status not in {"SUCCESS", "FAILED", "HANDOVER"}:
                    final_status = "SUCCESS"

            with self._lock:
                task = self._tasks.get(request_id)
                if task is not None:
                    task["status"] = final_status
                    task["result"] = result
                    task["completed_at"] = time.time()
                    task["error"] = None
        except Exception as exc:
            with self._lock:
                task = self._tasks.get(request_id)
                if task is not None:
                    task["status"] = "FAILED"
                    task["error"] = str(exc)
                    task["completed_at"] = time.time()

    def get_task(self, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._tasks.get(request_id)
            if record is None:
                return None
            snapshot = deepcopy(record)

        runtime_status = get_task_status(snapshot["run_id"], snapshot["task_id"])
        if runtime_status is not None:
            snapshot["runtime_status"] = runtime_status
        return snapshot

    def list_tasks(self, status: str | None = None) -> list[dict[str, Any]]:
        status = str(status).upper() if status else None
        with self._lock:
            ids = list(self._tasks.keys())

        items: list[dict[str, Any]] = []
        for request_id in ids:
            item = self.get_task(request_id)
            if item is None:
                continue
            if status is not None and str(item.get("status", "")).upper() != status:
                continue
            items.append(item)
        items.sort(key=lambda x: x.get("submitted_at") or 0.0, reverse=True)
        return items

    def wait(self, request_id: str, timeout: float | None = None) -> dict[str, Any] | None:
        with self._lock:
            future = self._futures.get(request_id)
        if future is None:
            return self.get_task(request_id)

        try:
            future.result(timeout=timeout)
        except TimeoutError:
            return self.get_task(request_id)
        return self.get_task(request_id)

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)


_GLOBAL_TASK_SERVICE: RuntimeTaskService | None = None
_GLOBAL_TASK_SERVICE_LOCK = Lock()


def get_global_task_service() -> RuntimeTaskService:
    global _GLOBAL_TASK_SERVICE
    if _GLOBAL_TASK_SERVICE is not None:
        return _GLOBAL_TASK_SERVICE

    with _GLOBAL_TASK_SERVICE_LOCK:
        if _GLOBAL_TASK_SERVICE is None:
            _GLOBAL_TASK_SERVICE = RuntimeTaskService()
    return _GLOBAL_TASK_SERVICE


def submit_task(
    instruction: str,
    runtime_mode: str = "legacy",
    run_name: str = "test",
    task_id: str | None = None,
    run_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return get_global_task_service().submit_task(
        instruction=instruction,
        runtime_mode=runtime_mode,
        run_name=run_name,
        task_id=task_id,
        run_options=run_options,
    )


def get_submitted_task(request_id: str) -> dict[str, Any] | None:
    return get_global_task_service().get_task(request_id)


def list_submitted_tasks(status: str | None = None) -> list[dict[str, Any]]:
    return get_global_task_service().list_tasks(status=status)
