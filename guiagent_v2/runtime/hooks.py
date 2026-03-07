from dataclasses import dataclass
from typing import Any, Callable

from guiagent_v2.intent_contract import ExecutionRequest


PreAssertionHook = Callable[[ExecutionRequest, dict[str, Any]], dict[str, Any]]
PostCheckHook = Callable[[ExecutionRequest, dict[str, Any]], dict[str, Any]]


@dataclass
class HookManager:
    pre_assertion_hooks: list[PreAssertionHook]
    post_check_hooks: list[PostCheckHook]

    def __init__(self):
        self.pre_assertion_hooks = []
        self.post_check_hooks = []

    def register_pre_assertion_hook(self, hook: PreAssertionHook) -> None:
        self.pre_assertion_hooks.append(hook)

    def register_post_check_hook(self, hook: PostCheckHook) -> None:
        self.post_check_hooks.append(hook)

    def run_pre_assertion(
        self,
        request: ExecutionRequest,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = {"passed": True, "reason_code": "OK"}
        context = context or {}
        for hook in self.pre_assertion_hooks:
            hook_result = hook(request, context)
            if not hook_result.get("passed", True):
                return hook_result
            result.update(hook_result)
        return result

    def run_post_check(
        self,
        request: ExecutionRequest,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = {"passed": True, "reason_code": "STATE_TRANSITION_OK"}
        context = context or {}
        for hook in self.post_check_hooks:
            hook_result = hook(request, context)
            if not hook_result.get("passed", True):
                return hook_result
            result.update(hook_result)
        return result

