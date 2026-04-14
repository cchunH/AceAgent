from __future__ import annotations

import json
import os
from typing import Any

from UniMind.utils.api_client import get_model_api_response


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


def _sanitize_steps(raw_steps: Any, max_steps: int) -> list[str]:
    if not isinstance(raw_steps, list):
        return []
    cap = max(1, int(max_steps))
    clean: list[str] = []
    for item in raw_steps:
        text = str(item or "").strip()
        if not text:
            continue
        if clean and clean[-1] == text:
            continue
        clean.append(text)
        if len(clean) >= cap:
            break
    return clean


def _sanitize_subtasks(raw_subtasks: Any, max_steps: int) -> list[dict[str, str]]:
    if not isinstance(raw_subtasks, list):
        return []
    cap = max(1, int(max_steps))
    clean: list[dict[str, str]] = []
    for item in raw_subtasks:
        if not isinstance(item, dict):
            continue
        instruction = str(item.get("instruction", "")).strip()
        if not instruction:
            continue
        row = {
            "instruction": instruction,
            "subtask_key": str(item.get("subtask_key", "")).strip(),
            "page_hint": str(item.get("page_hint", "")).strip(),
            "page_fingerprint_id": str(item.get("page_fingerprint_id", "")).strip(),
            "match_threshold": str(item.get("match_threshold", "")).strip(),
            "goal_state": str(item.get("goal_state", "")).strip(),
            "task_level": str(item.get("task_level", "L2")).strip() or "L2",
        }
        if clean and clean[-1].get("instruction") == row["instruction"]:
            continue
        clean.append(row)
        if len(clean) >= cap:
            break
    return clean


def build_task_plan_with_model(
    *,
    instruction: str,
    max_steps: int,
    model: str,
    model_type: str | None = None,
    api_url: str | None = None,
    api_key: str | None = None,
    extra_body: dict[str, Any] | None = None,
    temperature: float = 0.0,
) -> dict[str, Any]:
    prompt = (
        "You are a mobile GUI task planner.\n"
        "Output ONLY JSON with keys:\n"
        "{\n"
        '  "steps": [string],\n'
        '  "subtasks": [{"instruction": string, "subtask_key": string, "page_hint": string, "page_fingerprint_id": string, "match_threshold": number, "goal_state": string, "task_level": "L2"}],\n'
        '  "plan_confidence": number,\n'
        '  "reason": string\n'
        "}\n"
        f"Rules:\n"
        f"1) steps must be concise executable step instructions.\n"
        f"2) max steps <= {int(max_steps)}.\n"
        "3) Keep user intent and order.\n"
        "4) If task is already atomic, return one step.\n"
        "5) Prefer filling subtasks for multi-step tasks; keep steps compatible.\n"
        f"Instruction: {instruction}\n"
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
            "error": "MODEL_TASK_PLAN_INVALID_JSON",
            "raw": str(raw or ""),
            "steps": [],
        }

    subtasks = _sanitize_subtasks(payload.get("subtasks", []), max_steps=int(max_steps))
    steps = _sanitize_steps(payload.get("steps", []), max_steps=int(max_steps))
    if not steps and subtasks:
        steps = [str(item.get("instruction", "")).strip() for item in subtasks if str(item.get("instruction", "")).strip()]
    if not steps:
        return {
            "ok": False,
            "error": "MODEL_TASK_PLAN_EMPTY",
            "raw": str(raw or ""),
            "steps": [],
            "subtasks": [],
        }
    try:
        plan_confidence = float(payload.get("plan_confidence", 0.0) or 0.0)
    except Exception:
        plan_confidence = 0.0
    return {
        "ok": True,
        "steps": steps,
        "subtasks": subtasks,
        "plan_confidence": plan_confidence,
        "reason": str(payload.get("reason", "")).strip(),
        "raw": str(raw or ""),
    }
