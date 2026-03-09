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


def _normalize_action_name(name: str) -> str:
    mapping = {
        "back": "Back",
        "home": "Home",
        "wait": "Wait",
        "tap": "Tap",
        "swipe": "Swipe",
        "type": "Type",
        "enter": "Enter",
        "open_app": "Open_App",
        "switch_app": "Switch_App",
        "web_open": "web_open",
        "web_snapshot": "web_snapshot",
    }
    key = str(name or "").strip().lower()
    return mapping.get(key, str(name or "Wait").strip() or "Wait")


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


def parse_probe_instruction_with_model(
    instruction: str,
    *,
    model: str,
    model_type: str | None = None,
    api_url: str | None = None,
    api_key: str | None = None,
    extra_body: dict[str, Any] | None = None,
    temperature: float = 0.0,
) -> dict[str, Any]:
    prompt = (
        "You are an instruction parser for GUI automation.\n"
        "Output ONLY JSON with keys:\n"
        "{\n"
        '  "action_name": string,\n'
        '  "arguments": object,\n'
        '  "task_type": "mobile"|"web",\n'
        '  "is_web_subtask": boolean,\n'
        '  "web_task": object|null,\n'
        '  "confidence": number\n'
        "}\n"
        "Rules:\n"
        "1) For explicit url/http/about, choose web_open and set web_task.action=open.\n"
        "2) For browser/web/h5 navigation without url, choose web_snapshot.\n"
        "3) For 返回/back choose Back.\n"
        "4) For 回到桌面/home choose Home.\n"
        "5) If uncertain choose Wait.\n"
        "Do not add extra fields.\n"
        f"Instruction: {instruction}"
    )
    chat = [
        ("system", [{"type": "text", "text": "You are a strict JSON parser."}]),
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
            "error": "MODEL_INTENT_PARSE_INVALID_JSON",
            "raw": str(raw or ""),
        }

    action_name = _normalize_action_name(str(payload.get("action_name", "Wait")))
    args = payload.get("arguments", {})
    if not isinstance(args, dict):
        args = {}
    task_type = str(payload.get("task_type", "mobile")).strip().lower()
    if task_type not in {"mobile", "web"}:
        task_type = "mobile"
    is_web = bool(payload.get("is_web_subtask", False) or task_type == "web")
    web_task = payload.get("web_task")
    if web_task is not None and not isinstance(web_task, dict):
        web_task = None
    return {
        "ok": True,
        "action_obj": {"name": action_name, "arguments": args},
        "route_context": {
            "task_type": "web" if is_web else "mobile",
            "is_web_subtask": bool(is_web),
            "web_task": web_task if is_web else None,
        },
        "confidence": float(payload.get("confidence", 0.0) or 0.0),
        "raw": str(raw or ""),
    }
