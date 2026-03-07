import unittest

from guiagent_v2.runtime.status_api import TaskStatusStore


class TestRuntimeStatusApi(unittest.TestCase):
    def test_list_tasks_and_filters(self):
        store = TaskStatusStore()
        store.update(
            {
                "run_id": "run-a",
                "task_id": "t1",
                "event_type": "task_start",
                "status": "RUNNING",
                "ts": "2026-03-07T10:00:00Z",
            }
        )
        store.update(
            {
                "run_id": "run-a",
                "task_id": "t1",
                "event_type": "task_end",
                "status": "SUCCESS",
                "ts": "2026-03-07T10:01:00Z",
            }
        )
        store.update(
            {
                "run_id": "run-b",
                "task_id": "t2",
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


if __name__ == "__main__":
    unittest.main()
