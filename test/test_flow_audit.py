import unittest

from guiagent_v2.runtime.flow_audit import audit_flow_from_events


class TestFlowAudit(unittest.TestCase):
    def test_audit_flow_pass(self):
        events = [
            {"run_id": "r1", "task_id": "t1", "step_id": 0, "event_type": "task_start"},
            {"run_id": "r1", "task_id": "t1", "step_id": 1, "event_type": "step_start"},
            {"run_id": "r1", "task_id": "t1", "step_id": 1, "event_type": "skill_route"},
            {"run_id": "r1", "task_id": "t1", "step_id": 1, "event_type": "guard_decision"},
            {
                "run_id": "r1",
                "task_id": "t1",
                "step_id": 1,
                "event_type": "assertion",
                "assertion_result": {"passed": True},
            },
            {
                "run_id": "r1",
                "task_id": "t1",
                "step_id": 1,
                "event_type": "post_check",
                "post_check": {"passed": True},
            },
            {"run_id": "r1", "task_id": "t1", "step_id": 1, "event_type": "step_end", "status": "SUCCESS"},
            {"run_id": "r1", "task_id": "t1", "step_id": 999999, "event_type": "task_end", "status": "SUCCESS"},
        ]
        audit = audit_flow_from_events(events)
        self.assertEqual(audit["overall_status"], "PASS")
        self.assertEqual(audit["summary"]["task_fail"], 0)

    def test_audit_flow_fail_when_missing_required_step_event(self):
        events = [
            {"run_id": "r2", "task_id": "t2", "step_id": 0, "event_type": "task_start"},
            {"run_id": "r2", "task_id": "t2", "step_id": 1, "event_type": "step_start"},
            {"run_id": "r2", "task_id": "t2", "step_id": 1, "event_type": "guard_decision"},
            {"run_id": "r2", "task_id": "t2", "step_id": 1, "event_type": "assertion"},
            {"run_id": "r2", "task_id": "t2", "step_id": 1, "event_type": "step_end", "status": "SUCCESS"},
            {"run_id": "r2", "task_id": "t2", "step_id": 999999, "event_type": "task_end", "status": "SUCCESS"},
        ]
        audit = audit_flow_from_events(events)
        self.assertEqual(audit["overall_status"], "FAIL")
        issues = audit["tasks"][0]["issues"]
        self.assertTrue(any(item["code"] == "missing_required_step_events" for item in issues))

    def test_audit_flow_fail_for_web_plan_without_web_steps(self):
        events = [
            {"run_id": "r3", "task_id": "t3", "step_id": 0, "event_type": "task_start"},
            {"run_id": "r3", "task_id": "t3", "step_id": 1, "event_type": "step_start"},
            {"run_id": "r3", "task_id": "t3", "step_id": 1, "event_type": "assertion"},
            {"run_id": "r3", "task_id": "t3", "step_id": 1, "event_type": "post_check"},
            {"run_id": "r3", "task_id": "t3", "step_id": 1, "event_type": "step_end", "status": "SUCCESS"},
            {"run_id": "r3", "task_id": "t3", "step_id": 1, "event_type": "web_plan"},
            {"run_id": "r3", "task_id": "t3", "step_id": 999999, "event_type": "task_end", "status": "SUCCESS"},
        ]
        audit = audit_flow_from_events(events)
        self.assertEqual(audit["overall_status"], "FAIL")
        issues = audit["tasks"][0]["issues"]
        self.assertTrue(any(item["code"] == "web_plan_without_web_step_end" for item in issues))


if __name__ == "__main__":
    unittest.main()

