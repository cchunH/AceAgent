import json
from statistics import median
from typing import Any


def _percentile(values: list[int], q: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    idx = (len(values) - 1) * q
    lower = int(idx)
    upper = min(lower + 1, len(values) - 1)
    weight = idx - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def _task_key(event: dict[str, Any]) -> tuple[str, str]:
    return str(event.get("run_id", "")), str(event.get("task_id", ""))


def compute_metrics_from_jsonl(jsonl_path: str) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))

    task_end_events = [e for e in events if e.get("event_type") == "task_end"]
    step_end_events = [e for e in events if e.get("event_type") == "step_end"]
    handover_events = [e for e in events if e.get("event_type") == "handover"]
    assertion_events = [e for e in events if e.get("event_type") == "assertion"]
    retry_events = [e for e in events if e.get("event_type") == "action_exec" and int(e.get("retry_count", 0)) > 0]
    web_plan_events = [e for e in events if e.get("event_type") == "web_plan"]
    web_replan_events = [e for e in events if e.get("event_type") == "web_replan"]
    web_replan_skipped_events = [e for e in events if e.get("event_type") == "web_replan_skipped"]
    web_step_end_events = [e for e in events if e.get("event_type") == "web_step_end"]
    web_step_success_events = [e for e in web_step_end_events if str(e.get("status", "")).upper() == "SUCCESS"]
    fallback_events = [e for e in events if e.get("event_type") == "skill_fallback"]
    fallback_action_events = [e for e in events if e.get("event_type") == "fallback_action_selected"]

    success_tasks = [e for e in task_end_events if str(e.get("status", "")).upper() == "SUCCESS"]
    latencies = [int(e.get("latency_ms", 0)) for e in step_end_events if e.get("latency_ms") is not None]
    failed_assertions = [e for e in assertion_events if not e.get("assertion_result", {}).get("passed", False)]

    total_tasks = len(task_end_events)
    total_steps = len(step_end_events)
    total_assertions = len(assertion_events)
    total_web_plans = len(web_plan_events)
    total_web_steps = len(web_step_end_events)

    replan_tasks = {_task_key(e) for e in web_replan_events}
    fallback_tasks = {_task_key(e) for e in fallback_events}
    task_final_status: dict[tuple[str, str], str] = {}
    for event in task_end_events:
        task_final_status[_task_key(event)] = str(event.get("status", "")).upper()
    for event in step_end_events:
        task_final_status.setdefault(_task_key(event), str(event.get("status", "")).upper())

    replan_recovered_tasks = [
        key
        for key in replan_tasks
        if task_final_status.get(key) == "SUCCESS" and key not in fallback_tasks
    ]

    return {
        "task_success_rate": (len(success_tasks) / total_tasks) if total_tasks else 0.0,
        "step_latency_p50_ms": median(latencies) if latencies else 0.0,
        "step_latency_p95_ms": _percentile(latencies, 0.95) if latencies else 0.0,
        "s2_takeover_rate": (len(handover_events) / total_steps) if total_steps else 0.0,
        "retry_rate": (len(retry_events) / total_steps) if total_steps else 0.0,
        "assertion_fail_rate": (len(failed_assertions) / total_assertions) if total_assertions else 0.0,
        "web_plan_count": total_web_plans,
        "web_replan_count": len(web_replan_events),
        "web_replan_skipped_count": len(web_replan_skipped_events),
        "web_step_success_rate": (len(web_step_success_events) / total_web_steps) if total_web_steps else 0.0,
        "web_fallback_rate": (len(fallback_events) / total_web_plans) if total_web_plans else 0.0,
        "web_replan_recovery_rate": (
            len(replan_recovered_tasks) / len(replan_tasks)
        ) if replan_tasks else 0.0,
        "web_replan_task_count": len(replan_tasks),
        "fallback_action_selected_count": len(fallback_action_events),
        "counts": {
            "events": len(events),
            "task_end": total_tasks,
            "step_end": total_steps,
            "handover": len(handover_events),
            "assertion": total_assertions,
            "web_plan": total_web_plans,
            "web_replan": len(web_replan_events),
            "web_replan_skipped": len(web_replan_skipped_events),
            "web_step_end": total_web_steps,
            "skill_fallback": len(fallback_events),
            "fallback_action_selected": len(fallback_action_events),
        },
    }
