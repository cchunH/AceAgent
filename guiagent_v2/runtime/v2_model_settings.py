from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class V2ModelSettings:
    enable_intent_parser: bool = False
    enable_web_replan: bool = False
    enable_assertion_repair: bool = False
    api_type: str = ""
    api_url: str = ""
    api_key: str = ""
    extra_body: dict[str, Any] | None = None
    intent_parser_model: str = ""
    web_replan_model: str = ""
    assertion_repair_model: str = ""
    temperature: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "enable_intent_parser": bool(self.enable_intent_parser),
            "enable_web_replan": bool(self.enable_web_replan),
            "enable_assertion_repair": bool(self.enable_assertion_repair),
            "api_type": str(self.api_type),
            "api_url": str(self.api_url),
            "api_key_configured": bool(str(self.api_key or "").strip()),
            "extra_body_keys": sorted(list((self.extra_body or {}).keys())),
            "intent_parser_model": str(self.intent_parser_model),
            "web_replan_model": str(self.web_replan_model),
            "assertion_repair_model": str(self.assertion_repair_model),
            "temperature": float(self.temperature),
        }


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _as_json_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return dict(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        return None
    return dict(parsed) if isinstance(parsed, dict) else None


def build_v2_model_settings(
    runtime_config: Any,
    *,
    enable_intent_parser: bool | None = None,
    enable_web_replan: bool | None = None,
    enable_assertion_repair: bool | None = None,
    api_type: str | None = None,
    api_url: str | None = None,
    api_key: str | None = None,
    extra_body: dict[str, Any] | str | None = None,
    intent_parser_model: str | None = None,
    web_replan_model: str | None = None,
    assertion_repair_model: str | None = None,
    temperature: float | None = None,
) -> V2ModelSettings:
    models_obj = getattr(runtime_config, "models", None)
    v2_obj = getattr(models_obj, "v2", None)

    def _get(name: str, fallback: Any) -> Any:
        if v2_obj is None:
            return fallback
        return getattr(v2_obj, name, fallback)

    resolved_temp = _as_float(
        temperature if temperature is not None else _get("TEMPERATURE", 0.0),
        0.0,
    )
    return V2ModelSettings(
        enable_intent_parser=_as_bool(
            enable_intent_parser if enable_intent_parser is not None else _get("ENABLE_INTENT_PARSER", False)
        ),
        enable_web_replan=_as_bool(
            enable_web_replan if enable_web_replan is not None else _get("ENABLE_WEB_REPLAN", False)
        ),
        enable_assertion_repair=_as_bool(
            enable_assertion_repair if enable_assertion_repair is not None else _get("ENABLE_ASSERTION_REPAIR", False)
        ),
        api_type=str(api_type if api_type is not None else _get("API_TYPE", "")).strip(),
        api_url=str(api_url if api_url is not None else _get("API_URL", "")).strip(),
        api_key=str(api_key if api_key is not None else _get("API_KEY", "")).strip(),
        extra_body=_as_json_dict(extra_body if extra_body is not None else _get("EXTRA_BODY_JSON", None)),
        intent_parser_model=str(
            intent_parser_model
            if intent_parser_model is not None
            else _get("INTENT_PARSER_MODEL", "")
        ).strip(),
        web_replan_model=str(
            web_replan_model if web_replan_model is not None else _get("WEB_REPLAN_MODEL", "")
        ).strip(),
        assertion_repair_model=str(
            assertion_repair_model
            if assertion_repair_model is not None
            else _get("ASSERTION_REPAIR_MODEL", "")
        ).strip(),
        temperature=resolved_temp,
    )
