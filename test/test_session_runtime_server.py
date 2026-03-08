import json
import unittest
import urllib.error
import urllib.request
import tempfile
import os

from guiagent_v2.runtime.session_runtime import SessionRuntime
from guiagent_v2.runtime.session_runtime_server import SessionRuntimeAPIServer
from guiagent_v2.runtime.status_api import get_global_status_store, register_pending_confirmation


def _http_json(
    base_url: str,
    method: str,
    path: str,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict]:
    data = None
    merged_headers = {"Content-Type": "application/json; charset=utf-8"}
    if headers:
        merged_headers.update(headers)
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url=base_url + path,
        method=method,
        data=data,
        headers=merged_headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=5.0) as resp:
            body = resp.read().decode("utf-8")
            return resp.getcode(), json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, json.loads(body)


class TestSessionRuntimeServer(unittest.TestCase):
    def setUp(self):
        def fake_runner(**kwargs):
            return {
                "status": "SUCCESS",
                "run_id": f'{kwargs["run_name"]}:{kwargs["task_id"]}',
                "task_id": kwargs["task_id"],
                "session_id": kwargs.get("session_id"),
            }

        self._td = tempfile.TemporaryDirectory()
        self._lockfile_path = os.path.join(self._td.name, "server-main.lock")
        self.runtime = SessionRuntime(runner=fake_runner, per_session_max_workers=1)
        self.server = SessionRuntimeAPIServer(
            runtime=self.runtime,
            host="127.0.0.1",
            port=0,
            lockfile_path=self._lockfile_path,
        )
        self.server.start()
        self.base_url = self.server.base_url

    def tearDown(self):
        self.server.stop()
        self.runtime.shutdown(wait=True)
        self._td.cleanup()

    def test_health_and_session_lifecycle(self):
        code, body = _http_json(self.base_url, "GET", "/health")
        self.assertEqual(code, 200)
        self.assertTrue(body["ok"])

        code, body = _http_json(
            self.base_url,
            "POST",
            "/sessions",
            {"session_id": "sess-http", "metadata": {"source": "ut"}},
        )
        self.assertEqual(code, 201)
        self.assertEqual(body["data"]["session_id"], "sess-http")

        code, body = _http_json(self.base_url, "GET", "/sessions")
        self.assertEqual(code, 200)
        sessions = body["data"]["sessions"]
        self.assertTrue(any(item["session_id"] == "sess-http" for item in sessions))

        code, body = _http_json(self.base_url, "DELETE", "/sessions/sess-http")
        self.assertEqual(code, 200)
        self.assertTrue(body["data"]["removed"])

    def test_submit_wait_and_query_task(self):
        code, body = _http_json(
            self.base_url,
            "POST",
            "/tasks",
            {
                "instruction": "open app",
                "session_id": "sess-submit",
                "runtime_mode": "guiagent_v2",
                "run_name": "api-ut",
            },
        )
        self.assertEqual(code, 201)
        request_id = body["data"]["request_id"]
        self.assertEqual(body["data"]["session_id"], "sess-submit")

        code, body = _http_json(self.base_url, "POST", f"/tasks/{request_id}/wait", {"timeout": 1.0})
        self.assertEqual(code, 200)
        self.assertEqual(body["data"]["status"], "SUCCESS")

        code, body = _http_json(self.base_url, "GET", f"/tasks/{request_id}")
        self.assertEqual(code, 200)
        self.assertEqual(body["data"]["request_id"], request_id)

        code, body = _http_json(self.base_url, "GET", "/tasks?session_id=sess-submit")
        self.assertEqual(code, 200)
        tasks = body["data"]["tasks"]
        self.assertTrue(any(item["request_id"] == request_id for item in tasks))

    def test_runtime_status_and_timeline_endpoint(self):
        store = get_global_status_store()
        store.update(
            {
                "run_id": "run-http",
                "task_id": "task-http",
                "session_id": "sess-http",
                "event_type": "task_start",
                "status": "RUNNING",
                "ts": "2026-03-08T10:00:00Z",
            }
        )
        store.update(
            {
                "run_id": "run-http",
                "task_id": "task-http",
                "session_id": "sess-http",
                "event_type": "task_end",
                "status": "SUCCESS",
                "ts": "2026-03-08T10:00:01Z",
            }
        )

        code, body = _http_json(self.base_url, "GET", "/runtime/status?session_id=sess-http")
        self.assertEqual(code, 200)
        items = body["data"]["items"]
        self.assertTrue(any(item["run_id"] == "run-http" for item in items))

        code, body = _http_json(self.base_url, "GET", "/runtime/status/run-http/task-http")
        self.assertEqual(code, 200)
        self.assertEqual(body["data"]["status"], "SUCCESS")

        code, body = _http_json(self.base_url, "GET", "/runtime/timeline/run-http/task-http")
        self.assertEqual(code, 200)
        self.assertEqual(len(body["data"]["timeline"]), 2)

    def test_runtime_metrics_endpoint(self):
        store = get_global_status_store()
        run_id = "run-metrics-http"
        task_id = "task-metrics-http"
        session_id = "sess-metrics-http"
        store.update(
            {
                "run_id": run_id,
                "task_id": task_id,
                "session_id": session_id,
                "event_type": "web_plan",
                "status": "SUCCESS",
                "intent_key": "web:OPEN:URL",
                "step_id": 1,
                "chain_mode": "guiagent_v2",
                "ts": "2026-03-08T12:00:00Z",
            }
        )
        store.update(
            {
                "run_id": run_id,
                "task_id": task_id,
                "session_id": session_id,
                "event_type": "web_replan",
                "status": "RUNNING",
                "intent_key": "web:OPEN:URL",
                "step_id": 1,
                "chain_mode": "guiagent_v2",
                "ts": "2026-03-08T12:00:01Z",
            }
        )
        store.update(
            {
                "run_id": run_id,
                "task_id": task_id,
                "session_id": session_id,
                "event_type": "web_step_end",
                "status": "SUCCESS",
                "intent_key": "web:OPEN:URL",
                "step_id": 1,
                "chain_mode": "guiagent_v2",
                "latency_ms": 120,
                "ts": "2026-03-08T12:00:02Z",
            }
        )
        store.update(
            {
                "run_id": run_id,
                "task_id": task_id,
                "session_id": session_id,
                "event_type": "task_end",
                "status": "SUCCESS",
                "intent_key": "global:TASK:END",
                "step_id": 999999,
                "chain_mode": "guiagent_v2",
                "ts": "2026-03-08T12:00:03Z",
            }
        )

        code, body = _http_json(
            self.base_url,
            "GET",
            f"/runtime/metrics?run_id={run_id}&task_id={task_id}",
        )
        self.assertEqual(code, 200)
        metrics = body["data"]
        self.assertEqual(metrics["web_plan_count"], 1)
        self.assertEqual(metrics["web_replan_count"], 1)
        self.assertAlmostEqual(metrics["web_step_success_rate"], 1.0)
        self.assertEqual(metrics["scope"]["run_id"], run_id)

    def test_runtime_metrics_timeseries_endpoint(self):
        store = get_global_status_store()
        run_id = "run-metrics-ts-http"
        task_id = "task-metrics-ts-http"
        session_id = "sess-metrics-ts-http"
        store.update(
            {
                "run_id": run_id,
                "task_id": task_id,
                "session_id": session_id,
                "event_type": "task_end",
                "status": "SUCCESS",
                "intent_key": "global:TASK:END",
                "step_id": 999999,
                "chain_mode": "guiagent_v2",
                "ts": "2026-03-08T12:20:00Z",
            }
        )
        store.update(
            {
                "run_id": run_id,
                "task_id": task_id,
                "session_id": session_id,
                "event_type": "task_end",
                "status": "FAILED",
                "intent_key": "global:TASK:END",
                "step_id": 999999,
                "chain_mode": "guiagent_v2",
                "ts": "2026-03-08T12:21:05Z",
            }
        )

        code, body = _http_json(
            self.base_url,
            "GET",
            (
                "/runtime/metrics/timeseries"
                f"?run_id={run_id}&session_id={session_id}&bucket_sec=60&max_buckets=10"
            ),
        )
        self.assertEqual(code, 200)
        payload = body["data"]
        self.assertEqual(payload["scope"]["run_id"], run_id)
        self.assertEqual(payload["scope"]["session_id"], session_id)
        self.assertGreaterEqual(len(payload["series"]), 2)

    def test_runtime_confirm_endpoints(self):
        confirm = register_pending_confirmation(
            {
                "run_id": "run-confirm-http",
                "task_id": "task-confirm-http",
                "step_id": 7,
                "session_id": "sess-confirm-http",
                "intent_key": "global:PAY:ORDER",
                "policy_decision": "confirm",
                "policy_reason": "HIGH_RISK_INTENT",
            }
        )
        confirm_id = confirm["confirm_id"]

        code, body = _http_json(
            self.base_url,
            "GET",
            f"/runtime/confirms?run_id=run-confirm-http&status=PENDING",
        )
        self.assertEqual(code, 200)
        items = body["data"]["items"]
        self.assertTrue(any(item["confirm_id"] == confirm_id for item in items))

        code, body = _http_json(
            self.base_url,
            "POST",
            "/runtime/confirm",
            {
                "confirm_id": confirm_id,
                "decision": "approve",
                "note": "approved via api",
            },
            headers={
                "X-Actor": "ops-user",
                "X-Source": "control-panel",
            },
        )
        self.assertEqual(code, 200)
        self.assertEqual(body["data"]["status"], "APPROVED")
        self.assertEqual(body["data"]["decision"], "approve")

        code, body = _http_json(self.base_url, "GET", f"/runtime/confirms/{confirm_id}")
        self.assertEqual(code, 200)
        self.assertEqual(body["data"]["status"], "APPROVED")

    def test_control_plane_audit_updates_timeline_without_audit_file(self):
        code, submit_body = _http_json(
            self.base_url,
            "POST",
            "/tasks",
            {
                "instruction": "status-audit-task",
                "session_id": "sess-status-audit",
                "runtime_mode": "guiagent_v2",
                "run_name": "api-status-audit",
            },
        )
        self.assertEqual(code, 201)
        run_id = submit_body["data"]["run_id"]
        task_id = submit_body["data"]["task_id"]
        request_id = submit_body["data"]["request_id"]

        code, _ = _http_json(self.base_url, "POST", f"/tasks/{request_id}/wait", {"timeout": 1.0})
        self.assertEqual(code, 200)

        code, timeline_body = _http_json(self.base_url, "GET", f"/runtime/timeline/{run_id}/{task_id}")
        self.assertEqual(code, 200)
        timeline = timeline_body["data"]["timeline"]
        self.assertTrue(
            any(
                evt.get("event_type") == "control_plane_audit"
                and evt.get("control_action") in {"submit_task", "wait_task"}
                for evt in timeline
            )
        )

    def test_runtime_audit_endpoint_with_filters(self):
        code, submit_body = _http_json(
            self.base_url,
            "POST",
            "/tasks",
            {
                "instruction": "audit-filter-task",
                "session_id": "sess-audit-filter",
                "runtime_mode": "guiagent_v2",
                "run_name": "api-audit-filter",
            },
            headers={
                "X-Actor": "ops-user",
                "X-Source": "control-panel",
                "X-Trace-Id": "trace-filter-1",
            },
        )
        self.assertEqual(code, 201)
        request_id = submit_body["data"]["request_id"]

        code, _ = _http_json(
            self.base_url,
            "POST",
            f"/tasks/{request_id}/wait",
            {"timeout": 1.0},
            headers={
                "X-Actor": "ops-user",
                "X-Source": "control-panel",
                "X-Trace-Id": "trace-filter-2",
            },
        )
        self.assertEqual(code, 200)

        code, body = _http_json(
            self.base_url,
            "GET",
            "/runtime/audit?session_id=sess-audit-filter&actor=ops-user&source=control-panel",
        )
        self.assertEqual(code, 200)
        events = body["data"]["events"]
        self.assertTrue(events)
        self.assertTrue(all(item.get("event_type") == "control_plane_audit" for item in events))

        code, body = _http_json(
            self.base_url,
            "GET",
            "/runtime/audit?session_id=sess-audit-filter&control_action=wait_task&limit=1",
        )
        self.assertEqual(code, 200)
        events = body["data"]["events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].get("control_action"), "wait_task")

    def test_runtime_audit_endpoint_supports_cursor_and_time_range(self):
        store = get_global_status_store()
        run_id = "run-audit-page"
        task_id = "task-audit-page"
        session_id = "sess-audit-page"
        events = [
            ("2026-03-08T10:00:00Z", "ensure_session"),
            ("2026-03-08T10:00:01Z", "submit_task"),
            ("2026-03-08T10:00:02Z", "wait_task"),
        ]
        for ts, action in events:
            store.update(
                {
                    "run_id": run_id,
                    "task_id": task_id,
                    "session_id": session_id,
                    "step_id": 0,
                    "chain_mode": "guiagent_v2",
                    "event_type": "control_plane_audit",
                    "status": "SUCCESS",
                    "intent_key": "control:session-runtime:write",
                    "control_action": action,
                    "http_method": "POST",
                    "http_path": "/tasks",
                    "actor": "audit-user",
                    "source": "audit-test",
                    "ts": ts,
                }
            )

        code, body = _http_json(
            self.base_url,
            "GET",
            f"/runtime/audit?run_id={run_id}&task_id={task_id}&limit=2",
        )
        self.assertEqual(code, 200)
        page1 = body["data"]
        self.assertEqual(len(page1["events"]), 2)
        self.assertTrue(page1["has_more"])
        self.assertEqual(page1["next_cursor"], 2)
        self.assertEqual(page1["events"][0]["control_action"], "wait_task")

        code, body = _http_json(
            self.base_url,
            "GET",
            f"/runtime/audit?run_id={run_id}&task_id={task_id}&limit=2&cursor={page1['next_cursor']}",
        )
        self.assertEqual(code, 200)
        page2 = body["data"]
        self.assertEqual(len(page2["events"]), 1)
        self.assertFalse(page2["has_more"])
        self.assertIsNone(page2["next_cursor"])
        self.assertEqual(page2["events"][0]["control_action"], "ensure_session")

        code, body = _http_json(
            self.base_url,
            "GET",
            (
                f"/runtime/audit?run_id={run_id}&task_id={task_id}"
                "&since_ts=2026-03-08T10:00:01Z&until_ts=2026-03-08T10:00:01Z"
            ),
        )
        self.assertEqual(code, 200)
        ranged = body["data"]["events"]
        self.assertEqual(len(ranged), 1)
        self.assertEqual(ranged[0]["control_action"], "submit_task")

    def test_submit_invalid_instruction(self):
        code, body = _http_json(
            self.base_url,
            "POST",
            "/tasks",
            {"instruction": "   "},
        )
        self.assertEqual(code, 400)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "INVALID_INSTRUCTION")

    def test_server_restart_recovers_persisted_task_index(self):
        def fake_runner(**kwargs):
            return {
                "status": "SUCCESS",
                "run_id": f'{kwargs["run_name"]}:{kwargs["task_id"]}',
                "task_id": kwargs["task_id"],
            }

        with tempfile.TemporaryDirectory() as td:
            state_path = os.path.join(td, "runtime-state.json")
            runtime_a = SessionRuntime(runner=fake_runner, persistence_path=state_path)
            server_a = SessionRuntimeAPIServer(runtime=runtime_a, host="127.0.0.1", port=0)
            server_a.start()
            base_a = server_a.base_url

            code, body = _http_json(
                base_a,
                "POST",
                "/tasks",
                {
                    "instruction": "recover-me",
                    "session_id": "sess-recover",
                    "runtime_mode": "guiagent_v2",
                    "run_name": "api-ut",
                },
            )
            self.assertEqual(code, 201)
            request_id = body["data"]["request_id"]
            code, _ = _http_json(base_a, "POST", f"/tasks/{request_id}/wait", {"timeout": 1.0})
            self.assertEqual(code, 200)

            server_a.stop()
            runtime_a.shutdown(wait=True)

            runtime_b = SessionRuntime(runner=fake_runner, persistence_path=state_path)
            server_b = SessionRuntimeAPIServer(runtime=runtime_b, host="127.0.0.1", port=0)
            server_b.start()
            base_b = server_b.base_url
            try:
                code, body = _http_json(base_b, "GET", f"/tasks/{request_id}")
                self.assertEqual(code, 200)
                self.assertEqual(body["data"]["status"], "SUCCESS")
                self.assertEqual(body["data"]["session_id"], "sess-recover")
            finally:
                server_b.stop()
                runtime_b.shutdown(wait=True)

    def test_auth_on_write_endpoints(self):
        secure_server = SessionRuntimeAPIServer(
            runtime=self.runtime,
            host="127.0.0.1",
            port=0,
            api_token="secret-123",
            require_auth_on_read=False,
            lockfile_path=os.path.join(self._td.name, "server-auth-write.lock"),
        )
        secure_server.start()
        secure_base = secure_server.base_url
        try:
            code, body = _http_json(
                secure_base,
                "POST",
                "/sessions",
                {"session_id": "s-auth"},
            )
            self.assertEqual(code, 401)
            self.assertFalse(body["ok"])

            code, body = _http_json(
                secure_base,
                "POST",
                "/sessions",
                {"session_id": "s-auth"},
                headers={"X-API-Token": "secret-123"},
            )
            self.assertEqual(code, 201)
            self.assertEqual(body["data"]["session_id"], "s-auth")
        finally:
            secure_server.stop()

    def test_auth_on_read_when_enabled(self):
        secure_server = SessionRuntimeAPIServer(
            runtime=self.runtime,
            host="127.0.0.1",
            port=0,
            api_token="secret-456",
            require_auth_on_read=True,
            lockfile_path=os.path.join(self._td.name, "server-auth-read.lock"),
        )
        secure_server.start()
        secure_base = secure_server.base_url
        try:
            code, _ = _http_json(secure_base, "GET", "/health")
            self.assertEqual(code, 200)

            code, body = _http_json(secure_base, "GET", "/sessions")
            self.assertEqual(code, 401)
            self.assertFalse(body["ok"])

            code, body = _http_json(
                secure_base,
                "GET",
                "/sessions",
                headers={"Authorization": "Bearer secret-456"},
            )
            self.assertEqual(code, 200)
            self.assertTrue(body["ok"])
        finally:
            secure_server.stop()

    def test_lockfile_conflict_between_instances(self):
        def fake_runner(**kwargs):
            return {"status": "SUCCESS", "task_id": kwargs.get("task_id")}

        with tempfile.TemporaryDirectory() as td:
            lockfile_path = os.path.join(td, "session_runtime.lock")
            runtime_a = SessionRuntime(runner=fake_runner)
            runtime_b = SessionRuntime(runner=fake_runner)
            server_a = SessionRuntimeAPIServer(
                runtime=runtime_a,
                host="127.0.0.1",
                port=0,
                lockfile_path=lockfile_path,
            )
            server_b = SessionRuntimeAPIServer(
                runtime=runtime_b,
                host="127.0.0.1",
                port=0,
                lockfile_path=lockfile_path,
            )
            try:
                server_a.start()
                with self.assertRaises(RuntimeError):
                    server_b.start()
            finally:
                server_b.stop()
                server_a.stop()
                runtime_a.shutdown(wait=True)
                runtime_b.shutdown(wait=True)

    def test_stale_lockfile_is_recovered(self):
        with tempfile.TemporaryDirectory() as td:
            lockfile_path = os.path.join(td, "session_runtime.lock")
            with open(lockfile_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "instance_id": "stale-old",
                        "pid": 999999,
                        "host": "127.0.0.1",
                        "port": 8787,
                    },
                    f,
                )

            runtime = SessionRuntime(runner=lambda **kwargs: {"status": "SUCCESS"})
            server = SessionRuntimeAPIServer(
                runtime=runtime,
                host="127.0.0.1",
                port=0,
                lockfile_path=lockfile_path,
            )
            try:
                server.start()
                with open(lockfile_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                self.assertEqual(payload["instance_id"], server.instance_id)
            finally:
                server.stop()
                runtime.shutdown(wait=True)

    def test_control_plane_audit_log_for_write_ops(self):
        with tempfile.TemporaryDirectory() as td:
            audit_path = os.path.join(td, "session_runtime_audit.jsonl")
            audit_server = SessionRuntimeAPIServer(
                runtime=self.runtime,
                host="127.0.0.1",
                port=0,
                audit_log_path=audit_path,
                lockfile_path=os.path.join(self._td.name, "server-audit.lock"),
            )
            audit_server.start()
            audit_base = audit_server.base_url
            try:
                code, _ = _http_json(
                    audit_base,
                    "POST",
                    "/sessions",
                    {"session_id": "sess-audit"},
                    headers={
                        "X-Actor": "qa-user",
                        "X-Source": "unit-test",
                        "X-Trace-Id": "trace-audit-1",
                    },
                )
                self.assertEqual(code, 201)

                code, submit_body = _http_json(
                    audit_base,
                    "POST",
                    "/tasks",
                    {
                        "instruction": "audit-task",
                        "session_id": "sess-audit",
                        "runtime_mode": "guiagent_v2",
                        "run_name": "api-audit",
                    },
                    headers={
                        "X-Actor": "qa-user",
                        "X-Source": "unit-test",
                        "X-Trace-Id": "trace-audit-3",
                    },
                )
                self.assertEqual(code, 201)
                request_id = submit_body["data"]["request_id"]
                run_id = submit_body["data"]["run_id"]
                task_id = submit_body["data"]["task_id"]

                code, _wait_body = _http_json(
                    audit_base,
                    "POST",
                    f"/tasks/{request_id}/wait",
                    {"timeout": 1.0},
                    headers={
                        "X-Actor": "qa-user",
                        "X-Source": "unit-test",
                        "X-Trace-Id": "trace-audit-4",
                    },
                )
                self.assertEqual(code, 200)

                code, timeline_body = _http_json(
                    audit_base,
                    "GET",
                    f"/runtime/timeline/{run_id}/{task_id}",
                )
                self.assertEqual(code, 200)
                timeline = timeline_body["data"]["timeline"]
                self.assertTrue(
                    any(
                        evt.get("event_type") == "control_plane_audit"
                        and evt.get("control_action") in {"submit_task", "wait_task"}
                        for evt in timeline
                    )
                )

                code, _ = _http_json(
                    audit_base,
                    "POST",
                    "/tasks",
                    {"instruction": "  ", "session_id": "sess-audit"},
                    headers={
                        "X-Actor": "qa-user",
                        "X-Source": "unit-test",
                        "X-Trace-Id": "trace-audit-2",
                    },
                )
                self.assertEqual(code, 400)
            finally:
                audit_server.stop()

            with open(audit_path, "r", encoding="utf-8") as f:
                lines = [json.loads(line) for line in f if line.strip()]
            self.assertGreaterEqual(len(lines), 2)

            ensure_events = [
                item
                for item in lines
                if item.get("control_action") == "ensure_session"
            ]
            submit_failed_events = [
                item
                for item in lines
                if item.get("control_action") == "submit_task"
                and item.get("status") == "FAILED"
            ]
            self.assertTrue(ensure_events)
            self.assertTrue(submit_failed_events)
            self.assertEqual(ensure_events[0].get("actor"), "qa-user")
            self.assertEqual(ensure_events[0].get("source"), "unit-test")
            self.assertEqual(ensure_events[0].get("trace_id"), "trace-audit-1")
            self.assertEqual(
                submit_failed_events[0].get("reason_code"),
                "INVALID_INSTRUCTION",
            )
            self.assertTrue(
                any(
                    item.get("control_action") == "submit_task"
                    and item.get("status") == "SUCCESS"
                    and item.get("run_id", "").startswith("api-audit:")
                    for item in lines
                )
            )


if __name__ == "__main__":
    unittest.main()
