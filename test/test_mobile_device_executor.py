import os
import tempfile
import unittest
from unittest.mock import patch

from guiagent_v2.runtime.mobile_device_executor import MobileDeviceExecutor


class TestMobileDeviceExecutor(unittest.TestCase):
    def test_shadow_mode_always_success(self):
        executor = MobileDeviceExecutor(
            adb_path="definitely-not-exists-adb-bin",
            execution_mode="shadow",
        )
        result = executor.execute_action({"name": "Wait", "arguments": {}})
        self.assertTrue(result["success"])
        self.assertEqual(result["execution_mode"], "shadow")
        self.assertFalse(result["device_executed"])

    def test_auto_mode_falls_back_when_adb_unavailable(self):
        executor = MobileDeviceExecutor(
            adb_path="definitely-not-exists-adb-bin",
            execution_mode="auto",
        )
        result = executor.execute_action({"name": "Wait", "arguments": {}}, context={"wait_ms": 0})
        self.assertTrue(result["success"])
        self.assertEqual(result["execution_mode"], "shadow")
        self.assertFalse(result["device_executed"])
        self.assertEqual(result["error"], "ADB_UNAVAILABLE_AUTO_FALLBACK")

    def test_device_mode_fails_when_adb_unavailable(self):
        executor = MobileDeviceExecutor(
            adb_path="definitely-not-exists-adb-bin",
            execution_mode="device",
        )
        result = executor.execute_action({"name": "Wait", "arguments": {}}, context={"wait_ms": 0})
        self.assertFalse(result["success"])
        self.assertEqual(result["execution_mode"], "device")
        self.assertFalse(result["device_executed"])
        self.assertEqual(result["error"], "ADB_UNAVAILABLE")

    def test_device_mode_captures_action_screenshot(self):
        with tempfile.TemporaryDirectory() as td:
            executor = MobileDeviceExecutor(
                adb_path="adb",
                execution_mode="device",
                screenshot_log_dir=td,
                capture_action_screenshot=True,
            )
            executor.is_adb_available = lambda: True
            executor._execute_device_action = lambda name, arguments, context: True  # noqa: ARG005

            with patch("guiagent_v2.runtime.mobile_device_executor.save_screenshot_to_file") as mock_save:
                result = executor.execute_action(
                    {"name": "Wait", "arguments": {}},
                    context={"step_id": 7, "wait_ms": 0, "screenshot_prefix": "utask"},
                )
                self.assertTrue(result["success"])
                self.assertEqual(result["execution_mode"], "device")
                self.assertTrue(str(result.get("screenshot_path", "")).endswith(".png"))
                self.assertIsNone(result.get("screenshot_error"))
                self.assertTrue(str(result["screenshot_path"]).startswith(td + os.sep))
                self.assertEqual(mock_save.call_count, 1)


if __name__ == "__main__":
    unittest.main()
