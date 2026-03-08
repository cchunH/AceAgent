import unittest

from guiagent_v2.runtime.validation_gate import evaluate_runtime_summary


class TestRuntimeValidationGate(unittest.TestCase):
    def test_evaluate_runtime_summary_pass(self):
        summary = {
            "metrics": {
                "task_success_rate": 0.9,
                "s2_takeover_rate": 0.2,
                "assertion_fail_rate": 0.1,
                "anchor_gate_deny_rate": 0.1,
                "topology_projection_affine_rate": 0.7,
                "topology_projection_guard_block_rate": 0.1,
                "topology_projection_fit_error_p95": 0.08,
                "replay_gate_block_rate": 0.1,
                "blueprint_sync_failed_rate": 0.02,
                "counts": {"topology_projection": 8, "blueprint_sync": 10},
            }
        }
        report = evaluate_runtime_summary(summary)
        self.assertEqual(report["overall_status"], "PASS")
        self.assertEqual(report["totals"]["FAIL"], 0)

    def test_evaluate_runtime_summary_fail(self):
        summary = {
            "metrics": {
                "task_success_rate": 0.3,
                "s2_takeover_rate": 0.8,
                "assertion_fail_rate": 0.6,
                "anchor_gate_deny_rate": 0.4,
                "topology_projection_affine_rate": 0.1,
                "topology_projection_guard_block_rate": 0.9,
                "topology_projection_fit_error_p95": 0.4,
                "replay_gate_block_rate": 0.9,
                "blueprint_sync_failed_rate": 0.7,
                "counts": {"topology_projection": 10, "blueprint_sync": 12},
            }
        }
        report = evaluate_runtime_summary(summary)
        self.assertEqual(report["overall_status"], "FAIL")
        self.assertGreater(report["totals"]["FAIL"], 0)

    def test_evaluate_runtime_summary_warn_when_topology_samples_insufficient(self):
        summary = {
            "metrics": {
                "task_success_rate": 0.9,
                "s2_takeover_rate": 0.2,
                "assertion_fail_rate": 0.1,
                "anchor_gate_deny_rate": 0.1,
                "counts": {"topology_projection": 1},
            }
        }
        report = evaluate_runtime_summary(summary)
        self.assertEqual(report["overall_status"], "WARN")
        warns = [row for row in report["checks"] if row.get("status") == "WARN"]
        self.assertTrue(warns)
        self.assertEqual(warns[0].get("name"), "topology_projection_samples")


if __name__ == "__main__":
    unittest.main()
