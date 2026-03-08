import json
from datetime import datetime, timedelta, timezone
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


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _to_utc_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalize_bucket_sec(bucket_sec: int | None) -> int:
    if bucket_sec is None:
        return 60
    try:
        value = int(bucket_sec)
    except Exception:
        return 60
    if value <= 0:
        return 60
    return min(value, 3600)


def _normalize_max_buckets(max_buckets: int | None) -> int:
    if max_buckets is None:
        return 240
    try:
        value = int(max_buckets)
    except Exception:
        return 240
    if value <= 0:
        return 1
    return min(value, 1440)


def _bucket_start(dt: datetime, bucket_sec: int) -> datetime:
    ts = int(dt.timestamp())
    floored = ts - (ts % bucket_sec)
    return datetime.fromtimestamp(floored, tz=timezone.utc)


def compute_metrics_from_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    events = [dict(item) for item in list(events or []) if isinstance(item, dict)]
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
    pending_confirm_events = [e for e in events if e.get("event_type") == "pending_confirm"]
    confirm_approved_events = [e for e in events if e.get("event_type") == "confirm_approved"]
    confirm_rejected_events = [e for e in events if e.get("event_type") == "confirm_rejected"]
    confirm_timeout_events = [e for e in events if e.get("event_type") == "confirm_timeout"]
    post_check_events = [e for e in events if e.get("event_type") == "post_check"]

    success_tasks = [e for e in task_end_events if str(e.get("status", "")).upper() == "SUCCESS"]
    latencies = [int(e.get("latency_ms", 0)) for e in step_end_events if e.get("latency_ms") is not None]
    failed_assertions = [e for e in assertion_events if not e.get("assertion_result", {}).get("passed", False)]

    total_tasks = len(task_end_events)
    total_steps = len(step_end_events)
    total_assertions = len(assertion_events)
    total_web_plans = len(web_plan_events)
    total_web_steps = len(web_step_end_events)
    total_pending_confirms = len(pending_confirm_events)
    total_resolved_confirms = len(confirm_approved_events) + len(confirm_rejected_events)
    denoise_values: list[float] = []
    skeleton_values: list[float] = []
    fast_match_scores: list[float] = []
    fast_match_hits = 0
    fast_match_total = 0
    for event in assertion_events:
        result = dict(event.get("assertion_result", {}) or {})
        if result.get("denoise_stable_ratio") is not None:
            try:
                denoise_values.append(float(result.get("denoise_stable_ratio")))
            except Exception:
                pass
        if result.get("skeleton_confidence") is not None:
            try:
                skeleton_values.append(float(result.get("skeleton_confidence")))
            except Exception:
                pass
        hint = event.get("fast_match_hint")
        if isinstance(hint, dict):
            score = hint.get("matched_score")
            try:
                fast_match_scores.append(float(score))
            except Exception:
                pass
            fast_match_total += 1
            if bool(hint.get("signature_hit", False)):
                fast_match_hits += 1
    for event in post_check_events:
        result = dict(event.get("post_check", {}) or {})
        if result.get("denoise_stable_ratio") is not None:
            try:
                denoise_values.append(float(result.get("denoise_stable_ratio")))
            except Exception:
                pass
        if result.get("skeleton_confidence") is not None:
            try:
                skeleton_values.append(float(result.get("skeleton_confidence")))
            except Exception:
                pass

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
        "pending_confirm_count": total_pending_confirms,
        "confirm_approved_count": len(confirm_approved_events),
        "confirm_rejected_count": len(confirm_rejected_events),
        "confirm_timeout_count": len(confirm_timeout_events),
        "confirm_resolution_rate": (
            total_resolved_confirms / total_pending_confirms
        ) if total_pending_confirms else 0.0,
        "confirm_approval_rate": (
            len(confirm_approved_events) / total_resolved_confirms
        ) if total_resolved_confirms else 0.0,
        "denoise_stable_ratio_avg": (
            sum(denoise_values) / len(denoise_values)
        ) if denoise_values else 0.0,
        "skeleton_confidence_p50": median(skeleton_values) if skeleton_values else 0.0,
        "skeleton_confidence_p95": _percentile(skeleton_values, 0.95) if skeleton_values else 0.0,
        "fast_match_hit_rate": (fast_match_hits / fast_match_total) if fast_match_total else 0.0,
        "fast_match_score_p50": median(fast_match_scores) if fast_match_scores else 0.0,
        "fast_match_score_p95": _percentile(fast_match_scores, 0.95) if fast_match_scores else 0.0,
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
            "pending_confirm": total_pending_confirms,
            "confirm_approved": len(confirm_approved_events),
            "confirm_rejected": len(confirm_rejected_events),
            "confirm_timeout": len(confirm_timeout_events),
            "fast_match_total": fast_match_total,
            "fast_match_hits": fast_match_hits,
        },
    }


def compute_timeseries_from_events(
    events: list[dict[str, Any]],
    *,
    bucket_sec: int | None = None,
    max_buckets: int | None = None,
) -> dict[str, Any]:
    normalized_bucket_sec = _normalize_bucket_sec(bucket_sec)
    normalized_max_buckets = _normalize_max_buckets(max_buckets)
    rows = [dict(item) for item in list(events or []) if isinstance(item, dict)]

    buckets: dict[datetime, list[dict[str, Any]]] = {}
    no_ts_events: list[dict[str, Any]] = []
    for event in rows:
        event_dt = _parse_ts(event.get("ts"))
        if event_dt is None:
            no_ts_events.append(event)
            continue
        start_dt = _bucket_start(event_dt, normalized_bucket_sec)
        buckets.setdefault(start_dt, []).append(event)

    ordered_starts = sorted(buckets.keys())
    if len(ordered_starts) > normalized_max_buckets:
        ordered_starts = ordered_starts[-normalized_max_buckets:]

    series: list[dict[str, Any]] = []
    for start_dt in ordered_starts:
        end_dt = start_dt + timedelta(seconds=normalized_bucket_sec)
        bucket_events = buckets.get(start_dt, [])
        series.append(
            {
                "bucket_start": _to_utc_z(start_dt),
                "bucket_end": _to_utc_z(end_dt),
                "event_count": len(bucket_events),
                "metrics": compute_metrics_from_events(bucket_events),
            }
        )

    return {
        "bucket_sec": normalized_bucket_sec,
        "max_buckets": normalized_max_buckets,
        "series": series,
        "meta": {
            "source_event_count": len(rows),
            "bucketed_event_count": sum(item["event_count"] for item in series),
            "events_without_ts": len(no_ts_events),
        },
    }


def compute_metrics_from_jsonl(jsonl_path: str) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return compute_metrics_from_events(events)
