from __future__ import annotations

import json
from typing import Any


def _task_key(event: dict[str, Any]) -> tuple[str, str]:
    return str(event.get("run_id", "")), str(event.get("task_id", ""))


def _step_id(event: dict[str, Any]) -> int | None:
    raw = event.get("step_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except Exception:
        return None


def _issue(level: str, code: str, message: str, **extra: Any) -> dict[str, Any]:
    payload = {
        "level": str(level).upper(),
        "code": str(code),
        "message": str(message),
    }
    payload.update(extra)
    return payload


def _audit_single_task(run_id: str, task_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    typed_events = [dict(item) for item in events if isinstance(item, dict)]
    issues: list[dict[str, Any]] = []
    event_types = [str(item.get("event_type", "")) for item in typed_events]
    type_set = set(event_types)

    if "task_start" not in type_set:
        issues.append(_issue("ERROR", "missing_task_start", "Task missing task_start event"))
    if "task_end" not in type_set:
        issues.append(_issue("ERROR", "missing_task_end", "Task missing task_end event"))
    else:
        task_end_event = next(
            (item for item in reversed(typed_events) if str(item.get("event_type", "")) == "task_end"),
            None,
        )
        if isinstance(task_end_event, dict):
            task_end_status = str(task_end_event.get("status", "")).upper()
            if task_end_status != "SUCCESS":
                issues.append(
                    _issue(
                        "ERROR",
                        "task_end_not_success",
                        "Task ended with non-success status",
                        task_end_status=task_end_status or "UNKNOWN",
                    )
                )

    if "intent_parse_guard" in type_set:
        task_end_event = next(
            (item for item in reversed(typed_events) if str(item.get("event_type", "")) == "task_end"),
            None,
        )
        if isinstance(task_end_event, dict):
            task_end_status = str(task_end_event.get("status", "")).upper()
            if task_end_status == "SUCCESS":
                issues.append(
                    _issue(
                        "ERROR",
                        "intent_guard_with_success_end",
                        "Task has intent_parse_guard but still ends SUCCESS",
                        task_end_status=task_end_status,
                    )
                )

    step_events: dict[int, list[dict[str, Any]]] = {}
    for event in typed_events:
        sid = _step_id(event)
        if sid is None:
            continue
        step_events.setdefault(sid, []).append(event)

    step_end_steps = sorted(
        sid
        for sid, bucket in step_events.items()
        if any(str(item.get("event_type", "")) == "step_end" for item in bucket)
    )

    require_guard = "guard_decision" in type_set
    required = ["step_start", "assertion", "post_check", "step_end"]
    if require_guard:
        required.append("guard_decision")

    passed_steps = 0
    for sid in step_end_steps:
        bucket = step_events.get(sid, [])
        bucket_types = {str(item.get("event_type", "")) for item in bucket}
        missing = [name for name in required if name not in bucket_types]
        if missing:
            issues.append(
                _issue(
                    "ERROR",
                    "missing_required_step_events",
                    "Step missing required events",
                    step_id=sid,
                    missing=missing,
                )
            )
        else:
            passed_steps += 1

        step_end = next((item for item in bucket if str(item.get("event_type", "")) == "step_end"), None)
        if step_end is not None and str(step_end.get("status", "")).upper() == "HANDOVER":
            if "handover" not in bucket_types:
                issues.append(
                    _issue(
                        "WARN",
                        "handover_without_event",
                        "Step ended with HANDOVER but no handover event found",
                        step_id=sid,
                    )
                )

        assertion_event = next((item for item in bucket if str(item.get("event_type", "")) == "assertion"), None)
        if isinstance(assertion_event, dict):
            assertion_result = dict(assertion_event.get("assertion_result", {}) or {})
            if bool(assertion_result.get("passed", False)):
                core_value = assertion_result.get("core_anchor_confidence")
                if core_value is not None:
                    try:
                        core_conf = float(core_value)
                        if core_conf < 0.45:
                            issues.append(
                                _issue(
                                    "WARN",
                                    "low_core_anchor_confidence",
                                    "Step assertion passed but core anchor confidence is low",
                                    step_id=sid,
                                    core_anchor_confidence=core_conf,
                                )
                            )
                    except Exception:
                        pass
                geom_value = assertion_result.get("geometry_confidence")
                if geom_value is not None:
                    try:
                        geom_conf = float(geom_value)
                        if geom_conf < 0.4:
                            issues.append(
                                _issue(
                                    "WARN",
                                    "low_geometry_confidence",
                                    "Step assertion passed but geometry confidence is low",
                                    step_id=sid,
                                    geometry_confidence=geom_conf,
                                )
                            )
                    except Exception:
                        pass

    if "web_plan" in type_set:
        if "web_step_start" not in type_set:
            issues.append(
                _issue(
                    "ERROR",
                    "web_plan_without_web_step_start",
                    "Task has web_plan but no web_step_start",
                )
            )
        if "web_step_end" not in type_set:
            issues.append(
                _issue(
                    "ERROR",
                    "web_plan_without_web_step_end",
                    "Task has web_plan but no web_step_end",
                )
            )
        if "skill_fallback" in type_set and "fallback_action_selected" not in type_set:
            issues.append(
                _issue(
                    "ERROR",
                    "fallback_without_action_selection",
                    "Task has skill_fallback but no fallback_action_selected",
                )
            )

    if "pending_confirm" in type_set:
        resolved_types = {"confirm_approved", "confirm_rejected", "confirm_timeout"}
        if not (type_set & resolved_types):
            issues.append(
                _issue(
                    "WARN",
                    "confirm_unresolved",
                    "Task has pending_confirm but no resolve event",
                )
            )

    has_error = any(item.get("level") == "ERROR" for item in issues)
    has_warn = any(item.get("level") == "WARN" for item in issues)
    status = "FAIL" if has_error else ("WARN" if has_warn else "PASS")

    return {
        "run_id": run_id,
        "task_id": task_id,
        "status": status,
        "issues": issues,
        "coverage": {
            "step_end_total": len(step_end_steps),
            "step_checks_passed": passed_steps,
        },
        "event_counts": {
            "total": len(typed_events),
            "unique_event_types": len(type_set),
        },
    }


def audit_flow_from_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [dict(item) for item in list(events or []) if isinstance(item, dict)]
    task_events: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for event in rows:
        task_events.setdefault(_task_key(event), []).append(event)

    tasks: list[dict[str, Any]] = []
    for key in sorted(task_events.keys()):
        run_id, task_id = key
        tasks.append(_audit_single_task(run_id, task_id, task_events[key]))

    task_total = len(tasks)
    pass_count = sum(1 for item in tasks if str(item.get("status")) == "PASS")
    warn_count = sum(1 for item in tasks if str(item.get("status")) == "WARN")
    fail_count = sum(1 for item in tasks if str(item.get("status")) == "FAIL")

    if fail_count > 0:
        overall_status = "FAIL"
    elif warn_count > 0:
        overall_status = "WARN"
    else:
        overall_status = "PASS"

    return {
        "overall_status": overall_status,
        "summary": {
            "task_total": task_total,
            "task_pass": pass_count,
            "task_warn": warn_count,
            "task_fail": fail_count,
        },
        "tasks": tasks,
    }


def audit_flow_from_jsonl(jsonl_path: str) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return audit_flow_from_events(events)
