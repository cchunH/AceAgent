from __future__ import annotations

import json
import os
from typing import Any

from UniMind.utils.api_client import get_model_api_response

from .web_planner import WebPlanStep


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


def _sanitize_step(step: dict[str, Any], revision: int) -> WebPlanStep | None:
    task = step.get("task")
    if not isinstance(task, dict):
        return None
    action = str(task.get("action", "")).strip().lower()
    allowed_actions = {
        "open",
        "navigate",
        "goto",
        "click",
        "type",
        "fill",
        "hover",
        "check",
        "uncheck",
        "wait",
        "snapshot",
        "eval",
    }
    if action not in allowed_actions:
        return None
    checkpoint = str(step.get("checkpoint", "replan_step")).strip() or "replan_step"
    rationale = str(step.get("rationale", "model_replan")).strip() or "model_replan"
    return WebPlanStep(
        task=dict(task),
        checkpoint=checkpoint,
        rationale=rationale,
        revision=int(revision),
    )


def build_replan_after_failure_with_model(
    *,
    instruction: str,
    failed_reason: str,
    failed_task: dict[str, Any],
    route_context: dict[str, Any],
    remaining_steps: int,
    revision: int,
    model: str,
    model_type: str | None = None,
    api_url: str | None = None,
    api_key: str | None = None,
    extra_body: dict[str, Any] | None = None,
    temperature: float = 0.0,
) -> dict[str, Any]:
    prompt = (
        "You are a web automation recovery planner.\n"
        "Output ONLY JSON with keys:\n"
        "{\n"
        '  "strategy": string,\n'
        '  "steps": [\n'
        '    {"task": object, "checkpoint": string, "rationale": string}\n'
        "  ]\n"
        "}\n"
        "Keep steps <= remaining_steps.\n"
        "Use web actions only.\n"
        f"instruction={instruction}\n"
        f"failed_reason={failed_reason}\n"
        f"failed_task={json.dumps(failed_task, ensure_ascii=False)}\n"
        f"route_context={json.dumps(route_context, ensure_ascii=False)}\n"
        f"remaining_steps={int(remaining_steps)}\n"
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
            "error": "MODEL_WEB_REPLAN_INVALID_JSON",
            "raw": str(raw or ""),
        }
    strategy = str(payload.get("strategy", "model_replan")).strip() or "model_replan"
    raw_steps = payload.get("steps", [])
    if not isinstance(raw_steps, list):
        raw_steps = []
    steps: list[WebPlanStep] = []
    for item in raw_steps:
        if not isinstance(item, dict):
            continue
        parsed = _sanitize_step(item, revision=revision)
        if parsed is None:
            continue
        steps.append(parsed)
        if len(steps) >= max(0, int(remaining_steps)):
            break
    if not steps:
        return {
            "ok": False,
            "error": "MODEL_WEB_REPLAN_EMPTY",
            "raw": str(raw or ""),
        }
    return {
        "ok": True,
        "strategy": strategy,
        "steps": steps,
        "raw": str(raw or ""),
    }
