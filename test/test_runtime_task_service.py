import time
import unittest

from guiagent_v2.runtime.task_service import RuntimeTaskService


class TestRuntimeTaskService(unittest.TestCase):
    def test_submit_and_wait_success(self):
        def fake_runner(**kwargs):
            return {
                "status": "SUCCESS",
                "run_id": f'{kwargs["run_name"]}:{kwargs["task_id"]}',
                "task_id": kwargs["task_id"],
            }

        service = RuntimeTaskService(runner=fake_runner, max_workers=1)
        try:
            submitted = service.submit_task(
                instruction="open app",
                runtime_mode="guiagent_v2",
                run_name="ut",
            )
            request_id = submitted["request_id"]
            done = service.wait(request_id, timeout=1.0)
            self.assertIsNotNone(done)
            self.assertEqual(done["status"], "SUCCESS")
            self.assertIsNotNone(done["result"])
            self.assertIsNone(done["error"])
        finally:
            service.shutdown(wait=True)

    def test_submit_failure(self):
        def bad_runner(**kwargs):
            raise RuntimeError("runner crashed")

        service = RuntimeTaskService(runner=bad_runner, max_workers=1)
        try:
            submitted = service.submit_task(
                instruction="broken",
                runtime_mode="legacy",
                run_name="ut",
            )
            request_id = submitted["request_id"]
            done = service.wait(request_id, timeout=1.0)
            self.assertIsNotNone(done)
            self.assertEqual(done["status"], "FAILED")
            self.assertIn("runner crashed", done["error"])
        finally:
            service.shutdown(wait=True)

    def test_wait_timeout_and_list_filter(self):
        def slow_runner(**kwargs):
            time.sleep(0.2)
            return {"status": "SUCCESS"}

        service = RuntimeTaskService(runner=slow_runner, max_workers=1)
        try:
            submitted = service.submit_task(
                instruction="slow job",
                runtime_mode="guiagent_v2_shadow",
                run_name="ut",
            )
            request_id = submitted["request_id"]
            mid = service.wait(request_id, timeout=0.01)
            self.assertIsNotNone(mid)
            self.assertIn(mid["status"], {"QUEUED", "RUNNING"})

            done = service.wait(request_id, timeout=1.0)
            self.assertEqual(done["status"], "SUCCESS")

            success_items = service.list_tasks(status="SUCCESS")
            self.assertTrue(any(item["request_id"] == request_id for item in success_items))
        finally:
            service.shutdown(wait=True)


if __name__ == "__main__":
    unittest.main()
