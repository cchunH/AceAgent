import unittest

from guiagent_v2.runtime.status_api import RuntimeConfirmationStore, TaskStatusStore


class TestRuntimeStatusApi(unittest.TestCase):
    def test_list_tasks_and_filters(self):
        store = TaskStatusStore()
        store.update(
            {
                "run_id": "run-a",
                "task_id": "t1",
                "session_id": "sess-a",
                "event_type": "task_start",
                "status": "RUNNING",
                "ts": "2026-03-07T10:00:00Z",
            }
        )
        store.update(
            {
                "run_id": "run-a",
                "task_id": "t1",
                "session_id": "sess-a",
                "event_type": "task_end",
                "status": "SUCCESS",
                "ts": "2026-03-07T10:01:00Z",
            }
        )
        store.update(
            {
                "run_id": "run-b",
                "task_id": "t2",
                "session_id": "sess-b",
                "event_type": "task_end",
                "status": "FAILED",
                "ts": "2026-03-07T10:02:00Z",
            }
        )

        all_items = store.list_tasks()
        self.assertEqual(len(all_items), 2)
        self.assertEqual(all_items[0]["run_id"], "run-b")

        run_a_items = store.list_tasks(run_id="run-a")
        self.assertEqual(len(run_a_items), 1)
        self.assertEqual(run_a_items[0]["task_id"], "t1")

        failed_items = store.list_tasks(status="FAILED")
        self.assertEqual(len(failed_items), 1)
        self.assertEqual(failed_items[0]["run_id"], "run-b")

        sess_a_items = store.list_tasks(session_id="sess-a")
        self.assertEqual(len(sess_a_items), 1)
        self.assertEqual(sess_a_items[0]["task_id"], "t1")

    def test_list_run_ids(self):
        store = TaskStatusStore()
        store.update(
            {
                "run_id": "run-z",
                "task_id": "t9",
                "event_type": "task_start",
                "status": "RUNNING",
                "ts": "2026-03-07T11:00:00Z",
            }
        )
        store.update(
            {
                "run_id": "run-a",
                "task_id": "t1",
                "event_type": "task_start",
                "status": "RUNNING",
                "ts": "2026-03-07T11:00:01Z",
            }
        )
        self.assertEqual(store.list_run_ids(), ["run-a", "run-z"])

    def test_timeline_cap_drops_old_events(self):
        store = TaskStatusStore(max_timeline_events_per_task=2)
        store.update(
            {
                "run_id": "run-cap",
                "task_id": "t-cap",
                "event_type": "task_start",
                "status": "RUNNING",
                "ts": "2026-03-07T11:00:00Z",
            }
        )
        store.update(
            {
                "run_id": "run-cap",
                "task_id": "t-cap",
                "event_type": "step_start",
                "status": "RUNNING",
                "ts": "2026-03-07T11:00:01Z",
            }
        )
        store.update(
            {
                "run_id": "run-cap",
                "task_id": "t-cap",
                "event_type": "task_end",
                "status": "SUCCESS",
                "ts": "2026-03-07T11:00:02Z",
            }
        )

        timeline = store.get_task_timeline("run-cap", "t-cap")
        self.assertEqual(len(timeline), 2)
        self.assertEqual(timeline[0]["event_type"], "step_start")
        self.assertEqual(timeline[1]["event_type"], "task_end")

        status = store.get_task_status("run-cap", "t-cap")
        self.assertIsNotNone(status)
        self.assertEqual(status["event_count"], 3)
        self.assertEqual(status["timeline_dropped"], 1)

    def test_compute_metrics_from_store_scope(self):
        store = TaskStatusStore()
        store.update(
            {
                "run_id": "run-m1",
                "task_id": "task-m1",
                "session_id": "sess-m1",
                "event_type": "web_plan",
                "status": "SUCCESS",
                "intent_key": "web:OPEN:URL",
                "step_id": 1,
                "chain_mode": "guiagent_v2",
                "ts": "2026-03-08T12:01:00Z",
            }
        )
        store.update(
            {
                "run_id": "run-m1",
                "task_id": "task-m1",
                "session_id": "sess-m1",
                "event_type": "task_end",
                "status": "SUCCESS",
                "intent_key": "global:TASK:END",
                "step_id": 999999,
                "chain_mode": "guiagent_v2",
                "ts": "2026-03-08T12:01:01Z",
            }
        )
        metrics = store.compute_metrics(run_id="run-m1", task_id="task-m1")
        self.assertEqual(metrics["web_plan_count"], 1)
        self.assertAlmostEqual(metrics["task_success_rate"], 1.0)
        self.assertEqual(metrics["scope"]["run_id"], "run-m1")

    def test_compute_metrics_timeseries_from_store_scope(self):
        store = TaskStatusStore()
        store.update(
            {
                "run_id": "run-ts1",
                "task_id": "task-ts1",
                "session_id": "sess-ts1",
                "event_type": "task_end",
                "status": "SUCCESS",
                "intent_key": "global:TASK:END",
                "step_id": 1,
                "chain_mode": "guiagent_v2",
                "ts": "2026-03-08T12:10:00Z",
            }
        )
        store.update(
            {
                "run_id": "run-ts1",
                "task_id": "task-ts2",
                "session_id": "sess-ts1",
                "event_type": "task_end",
                "status": "FAILED",
                "intent_key": "global:TASK:END",
                "step_id": 1,
                "chain_mode": "guiagent_v2",
                "ts": "2026-03-08T12:11:01Z",
            }
        )

        metrics = store.compute_metrics_timeseries(
            session_id="sess-ts1",
            bucket_sec=60,
            max_buckets=5,
        )
        self.assertEqual(metrics["scope"]["session_id"], "sess-ts1")
        self.assertEqual(len(metrics["series"]), 2)
        self.assertEqual(metrics["series"][0]["event_count"], 1)
        self.assertEqual(metrics["series"][1]["event_count"], 1)

    def test_confirmation_store_register_resolve_and_wait(self):
        store = RuntimeConfirmationStore()
        pending = store.register_pending(
            {
                "confirm_id": "run-x:task-y:1",
                "run_id": "run-x",
                "task_id": "task-y",
                "step_id": 1,
                "session_id": "sess-z",
                "intent_key": "global:PAY:ORDER",
            }
        )
        self.assertEqual(pending["status"], "PENDING")

        resolved = store.resolve(
            confirm_id="run-x:task-y:1",
            decision="approve",
            actor="ops",
            source="control-panel",
            note="approved in ut",
        )
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["status"], "APPROVED")
        self.assertEqual(resolved["decision"], "approve")

        waited = store.wait_for_decision("run-x:task-y:1", timeout_sec=1.0, poll_interval_sec=0.1)
        self.assertIsNotNone(waited)
        self.assertEqual(waited["status"], "APPROVED")

    def test_confirmation_store_build_id_from_task_scope(self):
        store = RuntimeConfirmationStore()
        store.register_pending(
            {
                "run_id": "run-a",
                "task_id": "task-b",
                "step_id": 9,
            }
        )
        resolved = store.resolve(
            run_id="run-a",
            task_id="task-b",
            step_id=9,
            decision="reject",
            actor="ops",
        )
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["status"], "REJECTED")

        items = store.list(run_id="run-a", status="REJECTED")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["confirm_id"], "run-a:task-b:9")


if __name__ == "__main__":
    unittest.main()
