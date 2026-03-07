from __future__ import annotations

from typing import Any

from guiagent_v2.intent_contract import ExecutionRequest


def _normalize_text(value: str) -> str:
    return value.strip().lower()


def _extract_texts(
    perception_infos: list[dict[str, Any]] | None,
    check_region: dict[str, Any] | None = None,
) -> list[str]:
    if not perception_infos:
        return []
    texts: list[str] = []
    for info in perception_infos:
        raw = info.get("text")
        if not isinstance(raw, str):
            continue
        text = raw.strip()
        if not text or text == "icon: None":
            continue

        if check_region:
            x, y = info.get("coordinates", (None, None))
            if x is None or y is None:
                continue
            rx = check_region.get("x", 0)
            ry = check_region.get("y", 0)
            rw = check_region.get("w", 0)
            rh = check_region.get("h", 0)
            if not (rx <= x <= rx + rw and ry <= y <= ry + rh):
                continue
        texts.append(text)
    return texts


def semantic_pre_assertion_hook(
    request: ExecutionRequest,
    context: dict[str, Any],
) -> dict[str, Any]:
    expected = request.assertion.expected_semantics or []
    if not expected:
        return {"passed": True, "reason_code": "OK"}

    pre_infos = context.get("perception_infos_pre", [])
    observed = _extract_texts(pre_infos, request.assertion.check_region)
    observed_blob = " ".join(_normalize_text(t) for t in observed)

    for semantic in expected:
        if _normalize_text(str(semantic)) in observed_blob:
            return {"passed": True, "reason_code": "OK"}
    return {
        "passed": False,
        "reason_code": "ASSERTION_MISMATCH",
        "expected_semantics": expected,
    }


def post_state_check_hook(
    request: ExecutionRequest,
    context: dict[str, Any],
) -> dict[str, Any]:
    pre_infos = context.get("perception_infos_pre", [])
    post_infos = context.get("perception_infos_post", [])

    post_expectations = context.get("post_expectations", [])
    if post_expectations:
        post_texts = _extract_texts(post_infos)
        post_blob = " ".join(_normalize_text(t) for t in post_texts)
        for expected in post_expectations:
            if _normalize_text(str(expected)) not in post_blob:
                return {
                    "passed": False,
                    "reason_code": "POST_EXPECTATION_MISMATCH",
                    "expected": post_expectations,
                }

    pre_texts = set(_normalize_text(t) for t in _extract_texts(pre_infos))
    post_texts = set(_normalize_text(t) for t in _extract_texts(post_infos))
    if pre_texts == post_texts:
        return {"passed": False, "reason_code": "NO_STATE_CHANGE"}

    return {"passed": True, "reason_code": "STATE_TRANSITION_OK"}

