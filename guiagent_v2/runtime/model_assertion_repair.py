from __future__ import annotations

import json
import os
from typing import Any

from UniMind.utils.api_client import get_model_api_response


def _strip_code_fence(text: str) -> str:
    value = str(text or "").strip()
    if value.startswith("```json"):
        value = value[7:]
    elif value.startswith("```"):
        value = value[3:]
    if value.endswith("```"):
        value = value[:-3]
    return value.strip()


def _parse_json_payload(raw: str) -> dict[str, Any] | None:
    text = _strip_code_fence(raw)
    if not text:
        return None
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    return None


def _extract_texts(items: list[dict[str, Any]], limit: int = 20) -> list[str]:
    out: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _build_structured_extra_body(extra_body: dict[str, Any] | None) -> dict[str, Any] | None:
    body = dict(extra_body or {})
    force_disable_thinking = str(
        os.environ.get("GUIAGENT_V2_FORCE_DISABLE_THINKING_FOR_STRUCTURED", "1")
    ).strip().lower() in {"1", "true", "yes", "on"}
    force_json_response = str(
        os.environ.get("GUIAGENT_V2_FORCE_JSON_RESPONSE_FOR_STRUCTURED", "1")
    ).strip().lower() in {"1", "true", "yes", "on"}
    if force_disable_thinking and "enable_thinking" in body:
        body["enable_thinking"] = False
    if force_json_response and "response_format" not in body:
        body["response_format"] = {"type": "json_object"}
    return body or None


def _node_timeout_sec() -> float:
    try:
        return float(os.environ.get("GUIAGENT_V2_MODEL_NODE_TIMEOUT_SEC", "35"))
    except Exception:
        return 35.0


def repair_assertion_with_model(
    *,
    instruction: str,
    action_name: str,
    assertion_result: dict[str, Any],
    post_check: dict[str, Any],
    step_context: dict[str, Any],
    model: str,
    model_type: str | None = None,
    api_url: str | None = None,
    api_key: str | None = None,
    extra_body: dict[str, Any] | None = None,
    temperature: float = 0.0,
) -> dict[str, Any]:
    pre_texts = _extract_texts(list(step_context.get("perception_infos_pre", [])))
    post_texts = _extract_texts(list(step_context.get("perception_infos_post", [])))
    prompt = (
        "You are an assertion repair policy for GUI agent runtime.\n"
        "Output ONLY JSON:\n"
        "{\n"
        '  "decision": "accept"|"keep"|"handover",\n'
        '  "reason_code": string,\n'
        '  "note": string\n'
        "}\n"
        "accept means override assertion failure to pass only when confidence is high that this is a benign mismatch.\n"
        "keep means keep current assertion result.\n"
        "handover means enforce fail fast.\n"
        f"instruction={instruction}\n"
        f"action_name={action_name}\n"
        f"assertion_result={json.dumps(assertion_result, ensure_ascii=False)}\n"
        f"post_check={json.dumps(post_check, ensure_ascii=False)}\n"
        f"pre_texts={json.dumps(pre_texts, ensure_ascii=False)}\n"
        f"post_texts={json.dumps(post_texts, ensure_ascii=False)}\n"
    )
    chat = [
        ("system", [{"type": "text", "text": "You output strict JSON only."}]),
        ("user", [{"type": "text", "text": prompt}]),
    ]
    raw = get_model_api_response(
        chat=chat,
        model_type=str(model_type or "").strip() or None,
        model=model,
        api_url=str(api_url or "").strip() or None,
        api_key=str(api_key or "").strip() or None,
        extra_body=_build_structured_extra_body(extra_body),
        temperature=float(temperature),
        request_timeout_sec=_node_timeout_sec(),
    )
    payload = _parse_json_payload(str(raw or ""))
    if not isinstance(payload, dict):
        return {
            "ok": False,
            "error": "MODEL_ASSERTION_REPAIR_INVALID_JSON",
            "raw": str(raw or ""),
        }
    decision = str(payload.get("decision", "keep")).strip().lower()
    if decision not in {"accept", "keep", "handover"}:
        decision = "keep"
    reason_code = str(payload.get("reason_code", "MODEL_ASSERTION_REPAIR")).strip() or "MODEL_ASSERTION_REPAIR"
    note = str(payload.get("note", "")).strip()
    return {
        "ok": True,
        "decision": decision,
        "reason_code": reason_code,
        "note": note,
        "raw": str(raw or ""),
    }
