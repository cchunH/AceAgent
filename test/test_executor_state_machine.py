import unittest

from guiagent_v2.runtime.executor_state_machine import ProbeState, ProbeStateMachine


class TestExecutorStateMachine(unittest.TestCase):
    def test_transition_sequence_mobile_success(self):
        sm = ProbeStateMachine()
        t1 = sm.transition(ProbeState.ROUTED, "route")
        t2 = sm.transition(ProbeState.GUARDED, "guard_allow")
        t3 = sm.transition(ProbeState.EXECUTING_MOBILE, "dispatch_mobile")
        t4 = sm.transition(ProbeState.VERIFYING, "verify")
        t5 = sm.transition(ProbeState.COMPLETED, "done")

        self.assertTrue(all(item.ok for item in [t1, t2, t3, t4, t5]))
        self.assertEqual(sm.current, ProbeState.COMPLETED)

    def test_invalid_transition_recorded(self):
        sm = ProbeStateMachine()
        t = sm.transition(ProbeState.VERIFYING, "jump_invalid")
        self.assertFalse(t.ok)
        self.assertEqual(sm.current, ProbeState.INIT)


if __name__ == "__main__":
    unittest.main()

