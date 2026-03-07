from guiagent_v2.action_engine.assertion_guard import run_pre_assertion
from guiagent_v2.action_engine.post_check import run_post_check
from guiagent_v2.intent_contract import ExecutionRequest


def semantic_pre_assertion_hook(
    request: ExecutionRequest,
    context: dict,
) -> dict:
    return run_pre_assertion(request, context=context)


def post_state_check_hook(
    request: ExecutionRequest,
    context: dict,
) -> dict:
    return run_post_check(request, context=context)
