import json
import unittest
import urllib.error
import urllib.request

from guiagent_v2.runtime.session_runtime import SessionRuntime
from guiagent_v2.runtime.session_runtime_server import SessionRuntimeAPIServer
from guiagent_v2.runtime.status_api import get_global_status_store


def _http_json(base_url: str, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url=base_url + path,
        method=method,
        data=data,
        headers=headers,
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

        self.runtime = SessionRuntime(runner=fake_runner, per_session_max_workers=1)
        self.server = SessionRuntimeAPIServer(runtime=self.runtime, host="127.0.0.1", port=0)
        self.server.start()
        self.base_url = self.server.base_url

    def tearDown(self):
        self.server.stop()
        self.runtime.shutdown(wait=True)

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


if __name__ == "__main__":
    unittest.main()
