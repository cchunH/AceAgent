import unittest

from guiagent_v2.runtime.hooks import HookManager
from guiagent_v2.runtime.pipeline import StepPipeline


class _PassHooks:
    @staticmethod
    def build() -> HookManager:
        hooks = HookManager()
        hooks.register_pre_assertion_hook(lambda req, ctx: {"passed": True, "reason_code": "OK"})  # noqa: ARG005
        hooks.register_post_check_hook(
            lambda req, ctx: {"passed": True, "reason_code": "STATE_TRANSITION_OK"}  # noqa: ARG005
        )
        return hooks


class _CaptureMobileExecutor:
    def __init__(self):
        self.last_action = None

    def execute_action(self, action, context=None):  # noqa: ANN001
        del context
        self.last_action = dict(action or {})
        return {
            "success": True,
            "execution_mode": "shadow",
            "device_executed": False,
            "error": None,
            "action_name": str(self.last_action.get("name", "")),
            "latency_ms": 0,
        }


class TestPipelineProjection(unittest.TestCase):
    def test_pipeline_applies_topology_projection_before_execute(self):
        mobile = _CaptureMobileExecutor()
        pipeline = StepPipeline(hooks=_PassHooks.build(), mobile_executor=mobile)
        context = {
            "topology_result": {
                "reference_screen": {"width": 1000, "height": 2000},
                "target_screen": {"width": 500, "height": 1000},
                "affine_norm": {"a": 1.0, "b": 0.0, "tx": 0.1, "c": 0.0, "d": 1.0, "ty": 0.2},
                "confidence": 0.9,
            }
        }
        request, result, detail = pipeline.run_step(
            {"name": "Tap", "arguments": {"x": 100, "y": 200}},
            context=context,
        )
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(mobile.last_action.get("arguments", {}).get("x"), 100)
        self.assertEqual(mobile.last_action.get("arguments", {}).get("y"), 300)
        self.assertEqual(request.get("action", {}).get("arguments", {}).get("x"), 100)
        self.assertEqual(request.get("action", {}).get("arguments", {}).get("y"), 300)
        self.assertEqual(detail.get("context", {}).get("projected_action", {}).get("arguments", {}).get("y"), 300)


if __name__ == "__main__":
    unittest.main()
