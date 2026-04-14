import unittest
import types
from unittest.mock import patch

from guiagent_v2.runtime.preflight import (
    _check_datasets_runtime_compat,
    _check_vector_backend,
    _parse_plugin_spec,
    run_preflight,
)


class TestRuntimePreflight(unittest.TestCase):
    def test_parse_plugin_spec(self):
        self.assertEqual(_parse_plugin_spec("a.b:factory"), ("a.b", "factory"))
        self.assertIsNone(_parse_plugin_spec("a.b"))
        self.assertIsNone(_parse_plugin_spec(":factory"))

    def test_check_vector_backend_memory_pass(self):
        rows = _check_vector_backend("memory", None)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, "PASS")

    def test_check_vector_backend_custom_missing_plugin_fail(self):
        rows = _check_vector_backend("custom", None)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, "FAIL")

    def test_run_preflight_reports_fail_when_torch_missing(self):
        with patch("guiagent_v2.runtime.preflight._module_available", return_value=False):
            report = run_preflight(
                require_adb=False,
                require_perception_stack=False,
                blueprint_vector_backend="memory",
            )
        self.assertEqual(report["overall_status"], "FAIL")
        self.assertGreaterEqual(report["totals"]["FAIL"], 1)

    def test_check_datasets_runtime_compat_missing_symbols_fail_when_required(self):
        fake_datasets = types.SimpleNamespace(__version__="2.16.0")
        fake_load = types.SimpleNamespace()

        def _fake_import_module(name: str):
            if name == "datasets":
                return fake_datasets
            if name == "datasets.load":
                return fake_load
            raise ModuleNotFoundError(name)

        with patch("guiagent_v2.runtime.preflight.importlib.import_module", side_effect=_fake_import_module):
            result = _check_datasets_runtime_compat(required=True)

        self.assertEqual(result.status, "FAIL")
        self.assertIn("LargeList", result.detail)
        self.assertFalse(result.detail["LargeList"])


if __name__ == "__main__":
    unittest.main()
