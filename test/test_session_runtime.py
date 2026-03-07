import time
import unittest

from guiagent_v2.runtime.session_runtime import SessionRuntime
from guiagent_v2.runtime.status_api import get_global_status_store


class TestSessionRuntime(unittest.TestCase):
    def test_submit_and_wait_across_sessions(self):
        def fake_runner(**kwargs):
            return {
                "status": "SUCCESS",
                "run_id": f'{kwargs["run_name"]}:{kwargs["task_id"]}',
                "task_id": kwargs["task_id"],
            }

        runtime = SessionRuntime(runner=fake_runner, per_session_max_workers=1)
        try:
            s1 = runtime.ensure_session("s-alpha")
            self.assertEqual(s1["session_id"], "s-alpha")

            t1 = runtime.submit_task(
                instruction="task-1",
                session_id="s-alpha",
                runtime_mode="guiagent_v2",
                run_name="ut",
            )
            t2 = runtime.submit_task(
                instruction="task-2",
                session_id="s-beta",
                runtime_mode="guiagent_v2",
                run_name="ut",
            )

            done1 = runtime.wait(t1["request_id"], timeout=1.0)
            done2 = runtime.wait(t2["request_id"], timeout=1.0)

            self.assertIsNotNone(done1)
            self.assertIsNotNone(done2)
            self.assertEqual(done1["status"], "SUCCESS")
            self.assertEqual(done2["status"], "SUCCESS")
            self.assertEqual(done1["session_id"], "s-alpha")
            self.assertEqual(done2["session_id"], "s-beta")

            sessions = runtime.list_sessions()
            session_ids = {item["session_id"] for item in sessions}
            self.assertIn("s-alpha", session_ids)
            self.assertIn("s-beta", session_ids)
        finally:
            runtime.shutdown(wait=True)

    def test_list_tasks_filter_by_session(self):
        def slow_runner(**kwargs):
            time.sleep(0.05)
            return {"status": "SUCCESS"}

        runtime = SessionRuntime(runner=slow_runner, per_session_max_workers=1)
        try:
            a = runtime.submit_task("a", session_id="sess-a", run_name="ut")
            b = runtime.submit_task("b", session_id="sess-b", run_name="ut")

            runtime.wait(a["request_id"], timeout=1.0)
            runtime.wait(b["request_id"], timeout=1.0)

            all_items = runtime.list_tasks()
            self.assertGreaterEqual(len(all_items), 2)

            a_items = runtime.list_tasks(session_id="sess-a")
            self.assertTrue(all(item["session_id"] == "sess-a" for item in a_items))
        finally:
            runtime.shutdown(wait=True)

    def test_status_and_timeline_proxy(self):
        runtime = SessionRuntime(runner=lambda **kwargs: {"status": "SUCCESS"})
        try:
            store = get_global_status_store()
            store.update(
                {
                    "run_id": "run-s",
                    "task_id": "task-s",
                    "event_type": "task_start",
                    "status": "RUNNING",
                    "ts": "2026-03-08T00:00:00Z",
                }
            )
            store.update(
                {
                    "run_id": "run-s",
                    "task_id": "task-s",
                    "event_type": "task_end",
                    "status": "SUCCESS",
                    "ts": "2026-03-08T00:00:01Z",
                }
            )

            status = runtime.status("run-s", "task-s")
            timeline = runtime.timeline("run-s", "task-s")

            self.assertIsNotNone(status)
            self.assertEqual(status["status"], "SUCCESS")
            self.assertEqual(len(timeline), 2)
        finally:
            runtime.shutdown(wait=True)

    def test_submit_injects_session_id_into_runner_options(self):
        captured = {}

        def capture_runner(**kwargs):
            captured.update(kwargs)
            return {"status": "SUCCESS"}

        runtime = SessionRuntime(runner=capture_runner, per_session_max_workers=1)
        try:
            item = runtime.submit_task(
                instruction="x",
                session_id="sess-capture",
                runtime_mode="guiagent_v2",
                run_name="ut",
            )
            runtime.wait(item["request_id"], timeout=1.0)
            self.assertEqual(captured.get("session_id"), "sess-capture")
        finally:
            runtime.shutdown(wait=True)


if __name__ == "__main__":
    unittest.main()
