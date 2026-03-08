import time
from typing import Any, Callable

from guiagent_v2.intent_contract import (
    ExecutionResult,
    map_legacy_action_to_request,
    map_legacy_outcome_to_result,
)
from .hooks import HookManager
from .mobile_device_executor import MobileDeviceExecutor


class StepPipeline:
    """Modular step pipeline: map -> pre-assertion -> execute(no-op) -> post-check."""

    def __init__(self, hooks: HookManager, mobile_executor: MobileDeviceExecutor | None = None):
        self.hooks = hooks
        self.mobile_executor = mobile_executor

    def run_step(
        self,
        legacy_action: dict[str, Any] | None,
        context: dict[str, Any] | None = None,
        post_context_provider: Callable[[], dict[str, Any] | None] | None = None,
    ) -> tuple[dict[str, Any], ExecutionResult, dict[str, Any]]:
        start = time.time()
        context = dict(context or {})
        request = map_legacy_action_to_request(legacy_action, context=context)
        pre_assertion = self.hooks.run_pre_assertion(request, context=context)

        if not pre_assertion.get("passed", True):
            result = map_legacy_outcome_to_result(request.request_id, "C", latency_ms=0)
            result.assertion_result = pre_assertion
            return request.to_dict(), result, {
                "success": True,
                "execution_mode": "pre_assertion_blocked",
                "device_executed": False,
                "error": None,
                "action_name": str(request.action.get("name", "")),
                "latency_ms": 0,
            }

        exec_detail = {
            "success": True,
            "execution_mode": "shadow",
            "device_executed": False,
            "error": None,
            "action_name": str(request.action.get("name", "")),
            "latency_ms": 0,
        }
        if self.mobile_executor is not None:
            exec_detail = self.mobile_executor.execute_action(request.action, context=context)
            if not bool(exec_detail.get("success", False)):
                result = map_legacy_outcome_to_result(
                    request.request_id,
                    "B",
                    latency_ms=int((time.time() - start) * 1000),
                )
                reason_code = str(exec_detail.get("error") or "MOBILE_EXECUTION_FAILED")
                result.status = "FAILED"
                result.assertion_result = {
                    **dict(pre_assertion or {}),
                    "passed": False,
                    "reason_code": reason_code,
                }
                result.post_check = {
                    "passed": False,
                    "reason_code": reason_code,
                }
                result.recovery_level = "L2"
                return request.to_dict(), result, exec_detail

        if post_context_provider is not None:
            try:
                post_updates = post_context_provider() or {}
            except Exception:
                post_updates = {}
            if isinstance(post_updates, dict) and post_updates:
                context.update(post_updates)

        post_check = self.hooks.run_post_check(request, context=context)
        result = map_legacy_outcome_to_result(
            request.request_id,
            "A" if post_check.get("passed", True) else "B",
            latency_ms=int((time.time() - start) * 1000),
        )
        result.assertion_result = {**dict(result.assertion_result or {}), **dict(pre_assertion or {})}
        result.post_check = post_check
        return request.to_dict(), result, exec_detail

    def run_shadow_step(
        self,
        legacy_action: dict[str, Any] | None,
        context: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], ExecutionResult]:
        request, result, _ = self.run_step(legacy_action, context=context)
        return request, result
