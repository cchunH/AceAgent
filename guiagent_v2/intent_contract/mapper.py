from typing import Any

from .schema import ExecutionResult, ExecutionRequest, build_intent_key


_ACTION_TO_VERB = {
    "tap": "TAP",
    "swipe": "SWIPE",
    "type": "INPUT",
    "enter": "INPUT",
    "long_press": "LONG_PRESS",
    "back": "BACK",
    "home": "HOME",
    "wait": "WAIT",
    "open_app": "OPEN_APP",
    "switch_app": "SWITCH_APP",
}


def map_legacy_action_to_request(
    action_obj: dict[str, Any] | None,
    context: dict[str, Any] | None = None,
) -> ExecutionRequest:
    context = context or {}
    action_obj = action_obj or {"name": "Wait", "arguments": {}}
    action_name = str(action_obj.get("name", "Wait"))
    verb = _ACTION_TO_VERB.get(action_name.lower(), action_name.upper())
    domain = context.get("domain", "global")
    obj = context.get("object", "UNSPECIFIED_TARGET")
    intent_key = build_intent_key(domain, verb, obj)

    return ExecutionRequest(
        intent_key=intent_key,
        action={
            "name": action_name,
            "arguments": action_obj.get("arguments", {}) or {},
        },
        timeout_ms=int(context.get("timeout_ms", 3000)),
        retry_policy={
            "max_retries": int(context.get("max_retries", 0)),
            "backoff_ms": int(context.get("backoff_ms", 0)),
        },
    )


def map_legacy_outcome_to_result(
    request_id: str,
    outcome: str | None,
    latency_ms: int = 0,
) -> ExecutionResult:
    outcome = (outcome or "").strip().upper()
    if outcome == "A":
        status = "SUCCESS"
        assertion = {"passed": True, "reason_code": "OK"}
        post_check = {"passed": True, "reason_code": "STATE_TRANSITION_OK"}
        recovery = "NONE"
    elif outcome == "B":
        status = "FAILED"
        assertion = {"passed": True, "reason_code": "OK"}
        post_check = {"passed": False, "reason_code": "POST_CHECK_FAILED"}
        recovery = "L2"
    elif outcome == "C":
        status = "FAILED"
        assertion = {"passed": False, "reason_code": "ASSERTION_MISMATCH"}
        post_check = {"passed": False, "reason_code": "NO_CHANGE"}
        recovery = "L1"
    else:
        status = "FAILED"
        assertion = {"passed": False, "reason_code": "UNKNOWN_ERROR"}
        post_check = {"passed": False, "reason_code": "UNKNOWN_ERROR"}
        recovery = "L3"

    return ExecutionResult(
        request_id=request_id,
        status=status,
        assertion_result=assertion,
        post_check=post_check,
        recovery_level=recovery,
        latency_ms=max(0, int(latency_ms)),
    )

