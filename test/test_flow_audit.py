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

    def test_audit_warns_for_low_core_confidence_even_when_passed(self):
        events = [
            {"run_id": "r4", "task_id": "t4", "step_id": 0, "event_type": "task_start"},
            {"run_id": "r4", "task_id": "t4", "step_id": 1, "event_type": "step_start"},
            {"run_id": "r4", "task_id": "t4", "step_id": 1, "event_type": "guard_decision"},
            {
                "run_id": "r4",
                "task_id": "t4",
                "step_id": 1,
                "event_type": "assertion",
                "assertion_result": {
                    "passed": True,
                    "core_anchor_confidence": 0.2,
                    "geometry_confidence": 0.3,
                },
            },
            {
                "run_id": "r4",
                "task_id": "t4",
                "step_id": 1,
                "event_type": "post_check",
                "post_check": {"passed": True},
            },
            {"run_id": "r4", "task_id": "t4", "step_id": 1, "event_type": "step_end", "status": "SUCCESS"},
            {"run_id": "r4", "task_id": "t4", "step_id": 999999, "event_type": "task_end", "status": "SUCCESS"},
        ]
        audit = audit_flow_from_events(events)
        self.assertEqual(audit["overall_status"], "WARN")
        issues = audit["tasks"][0]["issues"]
        self.assertTrue(any(item["code"] == "low_core_anchor_confidence" for item in issues))
        self.assertTrue(any(item["code"] == "low_geometry_confidence" for item in issues))

    def test_audit_fail_when_intent_guard_but_task_success(self):
        events = [
            {"run_id": "r5", "task_id": "t5", "step_id": 0, "event_type": "task_start"},
            {"run_id": "r5", "task_id": "t5", "step_id": 1, "event_type": "step_start"},
            {"run_id": "r5", "task_id": "t5", "step_id": 1, "event_type": "intent_parse_guard", "status": "HANDOVER"},
            {"run_id": "r5", "task_id": "t5", "step_id": 1, "event_type": "assertion"},
            {"run_id": "r5", "task_id": "t5", "step_id": 1, "event_type": "post_check"},
            {"run_id": "r5", "task_id": "t5", "step_id": 1, "event_type": "step_end", "status": "HANDOVER"},
            {"run_id": "r5", "task_id": "t5", "step_id": 999999, "event_type": "task_end", "status": "SUCCESS"},
        ]
        audit = audit_flow_from_events(events)
        self.assertEqual(audit["overall_status"], "FAIL")
        issues = audit["tasks"][0]["issues"]
        self.assertTrue(any(item["code"] == "intent_guard_with_success_end" for item in issues))


if __name__ == "__main__":
    unittest.main()
