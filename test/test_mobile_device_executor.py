import unittest

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


if __name__ == "__main__":
    unittest.main()
