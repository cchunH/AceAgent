import time
from typing import Any

from guiagent_v2.intent_contract import (
    ExecutionResult,
    map_legacy_action_to_request,
    map_legacy_outcome_to_result,
)
from .hooks import HookManager


class StepPipeline:
    """Modular step pipeline: map -> pre-assertion -> execute(no-op) -> post-check."""

    def __init__(self, hooks: HookManager):
        self.hooks = hooks

    def run_shadow_step(
        self,
        legacy_action: dict[str, Any] | None,
        context: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], ExecutionResult]:
        start = time.time()
        request = map_legacy_action_to_request(legacy_action, context=context)
        pre_assertion = self.hooks.run_pre_assertion(request, context=context)

        if not pre_assertion.get("passed", True):
            result = map_legacy_outcome_to_result(request.request_id, "C", latency_ms=0)
            result.assertion_result = pre_assertion
            return request.to_dict(), result

        # Shadow mode does no physical execution yet.
        post_check = self.hooks.run_post_check(request, context=context)
        result = map_legacy_outcome_to_result(
            request.request_id,
            "A" if post_check.get("passed", True) else "B",
            latency_ms=int((time.time() - start) * 1000),
        )
        result.post_check = post_check
        return request.to_dict(), result

