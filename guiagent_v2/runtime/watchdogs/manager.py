from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import Any

from .base import WatchdogPlugin
from .crash_watchdog import CrashWatchdog
from .security_watchdog import SecurityWatchdog
from ..watchdog_policy import WatchdogPolicyLoader


_SEVERITY_RANK = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


class WatchdogManager:
    """Dispatches runtime events to watchdog plugins and emits alerts."""

    def __init__(
        self,
        plugins: list[WatchdogPlugin] | None = None,
        policy_loader: WatchdogPolicyLoader | None = None,
    ):
        self._plugins = list(plugins or [])
        self._policy_loader = policy_loader or WatchdogPolicyLoader()
        self._lock = Lock()
        self._last_emit_at: dict[str, float] = {}
        self._window_emit_at: dict[str, list[float]] = defaultdict(list)
        self._escalation_observed_at: dict[str, list[float]] = defaultdict(list)
        self._cross_task_samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._cross_task_last_emit_at: dict[str, float] = {}

    def process(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        if str(event.get("event_type", "")) == "watchdog_alert":
            return []
        policy = self._policy_loader.load()
        enabled_watchdogs = {
            str(item).strip()
            for item in policy.get("enabled_watchdogs", [])
            if str(item).strip()
        }
        min_severity = str(policy.get("min_severity", "LOW")).upper()
        min_severity_rank = _SEVERITY_RANK.get(min_severity, _SEVERITY_RANK["LOW"])

        alerts: list[dict[str, Any]] = []
        for plugin in self._plugins:
            plugin_name = str(getattr(plugin, "name", "")).strip()
            if enabled_watchdogs and plugin_name not in enabled_watchdogs:
                continue
            try:
                generated = plugin.on_event(event)
            except Exception as exc:
                generated = [
                    {
                        "event_type": "watchdog_alert",
                        "status": "FAILED",
                        "watchdog_name": getattr(plugin, "name", "watchdog"),
                        "watchdog_severity": "HIGH",
                        "source_event_type": str(event.get("event_type", "unknown")),
                        "reason_code": "WATCHDOG_PLUGIN_ERROR",
                        "watchdog_error": str(exc),
                        "alert_category": "watchdog_internal",
                    }
                ]
            for alert in generated:
                hydrated = self._hydrate_alert(event, alert, policy_version=str(policy.get("version", "v1")))
                hydrated = self._apply_escalation(hydrated, policy)
                severity = str(hydrated.get("watchdog_severity", "LOW")).upper()
                severity_rank = _SEVERITY_RANK.get(severity, _SEVERITY_RANK["LOW"])
                if severity_rank < min_severity_rank:
                    continue
                if not self._allow_alert(hydrated, policy):
                    continue
                alerts.append(hydrated)
                aggregated = self._build_cross_task_alert(hydrated, policy)
                if aggregated is None:
                    continue
                agg_severity = str(aggregated.get("watchdog_severity", "LOW")).upper()
                agg_severity_rank = _SEVERITY_RANK.get(agg_severity, _SEVERITY_RANK["LOW"])
                if agg_severity_rank < min_severity_rank:
                    continue
                if not self._allow_aggregated_alert(aggregated, policy):
                    continue
                alerts.append(aggregated)
        return alerts

    def _hydrate_alert(
        self,
        source_event: dict[str, Any],
        alert: dict[str, Any],
        policy_version: str,
    ) -> dict[str, Any]:
        payload = dict(alert or {})
        payload.setdefault("run_id", source_event.get("run_id", ""))
        payload.setdefault("task_id", source_event.get("task_id", ""))
        payload.setdefault("step_id", int(source_event.get("step_id", 0)))
        payload.setdefault("chain_mode", source_event.get("chain_mode", "legacy"))
        payload.setdefault("intent_key", source_event.get("intent_key", "global:UNKNOWN:UNSPECIFIED_TARGET"))
        payload.setdefault("watchdog_policy_version", policy_version)
        payload.setdefault("watchdog_policy_source", self._policy_loader.source())

        source_session_id = source_event.get("session_id")
        if "session_id" not in payload and source_session_id is not None:
            payload["session_id"] = source_session_id
        return payload

    def _rule_match(self, alert: dict[str, Any], rule: dict[str, Any]) -> bool:
        for key in (
            "watchdog_name",
            "reason_code",
            "source_event_type",
            "alert_category",
            "policy_decision",
        ):
            expected = rule.get(key)
            if expected is None:
                continue
            actual = str(alert.get(key, "")).strip()
            if actual != str(expected).strip():
                return False
        return True

    def _apply_escalation(self, alert: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
        rules = policy.get("escalation_rules")
        if not isinstance(rules, list) or not rules:
            return alert

        base = dict(alert)
        current = str(base.get("watchdog_severity", "LOW")).upper()
        current_rank = _SEVERITY_RANK.get(current, _SEVERITY_RANK["LOW"])
        dedup_key = self._build_dedup_key(base, policy)
        now = time.monotonic()
        matched_escalation = False
        matched_rule_name = None
        matched_count = 0
        matched_window = 0.0

        with self._lock:
            for idx, rule in enumerate(rules):
                if not isinstance(rule, dict):
                    continue
                if not self._rule_match(base, rule):
                    continue

                threshold = max(1, int(rule.get("threshold", 3) or 3))
                window_sec = max(0.0, float(rule.get("window_sec", 120.0) or 0.0))
                hist_key = f"{idx}|{dedup_key}"
                history = self._escalation_observed_at[hist_key]
                if window_sec > 0:
                    history = [ts for ts in history if (now - ts) <= window_sec]
                history.append(now)
                self._escalation_observed_at[hist_key] = history
                if len(history) < threshold:
                    continue

                target = str(rule.get("target_severity", "CRITICAL") or "CRITICAL").upper()
                target_rank = _SEVERITY_RANK.get(target, _SEVERITY_RANK["CRITICAL"])
                if target_rank <= current_rank:
                    continue

                current = target
                current_rank = target_rank
                matched_escalation = True
                matched_rule_name = str(rule.get("name", f"rule_{idx}"))
                matched_count = len(history)
                matched_window = window_sec

        if not matched_escalation:
            return base

        escalated = dict(base)
        escalated["watchdog_severity_original"] = str(base.get("watchdog_severity", "LOW")).upper()
        escalated["watchdog_severity"] = current
        escalated["watchdog_escalated"] = True
        escalated["watchdog_escalation_rule"] = matched_rule_name
        escalated["watchdog_escalation_count"] = matched_count
        escalated["watchdog_escalation_window_sec"] = matched_window
        return escalated

    def _build_cross_task_alert(
        self,
        alert: dict[str, Any],
        policy: dict[str, Any],
    ) -> dict[str, Any] | None:
        cfg = policy.get("cross_task_aggregation")
        if not isinstance(cfg, dict):
            return None
        if not bool(cfg.get("enabled", False)):
            return None

        window_sec = max(0.0, float(cfg.get("window_sec", 300.0) or 0.0))
        min_distinct_tasks = max(1, int(cfg.get("min_distinct_tasks", 3) or 3))
        emit_throttle_sec = max(0.0, float(cfg.get("emit_throttle_sec", 120.0) or 0.0))
        severity = str(cfg.get("severity", "HIGH") or "HIGH").upper()
        if severity not in _SEVERITY_RANK:
            severity = "HIGH"
        group_fields = cfg.get("group_by_fields", ["watchdog_name", "reason_code", "alert_category"])
        if not isinstance(group_fields, list) or not group_fields:
            group_fields = ["watchdog_name", "reason_code", "alert_category"]

        parts: list[str] = []
        for raw_field in group_fields:
            field = str(raw_field).strip()
            if not field:
                continue
            parts.append(f"{field}={alert.get(field)}")
        if not parts:
            parts = [f"watchdog_name={alert.get('watchdog_name')}"]
        group_key = "|".join(parts)
        now = time.monotonic()

        with self._lock:
            samples = self._cross_task_samples[group_key]
            if window_sec > 0:
                samples = [item for item in samples if (now - float(item.get("at", 0.0))) <= window_sec]
            samples.append(
                {
                    "at": now,
                    "task_id": str(alert.get("task_id", "")).strip(),
                    "run_id": str(alert.get("run_id", "")).strip(),
                }
            )
            self._cross_task_samples[group_key] = samples
            distinct_tasks = {item.get("task_id") for item in samples if item.get("task_id")}
            if len(distinct_tasks) < min_distinct_tasks:
                return None

            last_emit = self._cross_task_last_emit_at.get(group_key)
            if emit_throttle_sec > 0 and last_emit is not None and (now - last_emit) < emit_throttle_sec:
                return None
            self._cross_task_last_emit_at[group_key] = now

        payload = dict(alert)
        payload["watchdog_name"] = "aggregate_watchdog"
        payload["watchdog_severity"] = severity
        payload["source_event_type"] = "watchdog_alert"
        payload["reason_code"] = "CROSS_TASK_ALERT_SPIKE"
        payload["alert_category"] = "cross_task_aggregation"
        payload["aggregated_watchdog_name"] = str(alert.get("watchdog_name", "")).strip()
        payload["aggregated_reason_code"] = str(alert.get("reason_code", "")).strip()
        payload["aggregated_group_key"] = group_key
        payload["aggregated_distinct_tasks"] = len(distinct_tasks)
        payload["aggregated_event_count"] = len(samples)
        payload["aggregated_window_sec"] = window_sec
        payload["aggregated_source_task_id"] = str(alert.get("task_id", "")).strip()
        payload["aggregated_source_run_id"] = str(alert.get("run_id", "")).strip()
        payload["watchdog_policy_mode"] = "cross_task_aggregation"
        return payload

    def _build_dedup_key(self, alert: dict[str, Any], policy: dict[str, Any]) -> str:
        fields = policy.get("dedup_key_fields", []) or ["watchdog_name", "task_id", "reason_code"]
        parts: list[str] = []
        for field in fields:
            key = str(field).strip()
            if not key:
                continue
            parts.append(f"{key}={alert.get(key)}")
        if not parts:
            parts.append(f"watchdog_name={alert.get('watchdog_name')}")
        return "|".join(parts)

    def _allow_aggregated_alert(self, alert: dict[str, Any], policy: dict[str, Any]) -> bool:
        cfg = policy.get("cross_task_aggregation")
        if not isinstance(cfg, dict):
            return self._allow_alert(alert, policy)

        aggregate_policy = dict(policy)
        aggregate_policy["dedup_window_sec"] = cfg.get(
            "dedup_window_sec",
            aggregate_policy.get("dedup_window_sec", 0.0),
        )
        aggregate_policy["throttle_window_sec"] = cfg.get(
            "throttle_window_sec",
            aggregate_policy.get("throttle_window_sec", 0.0),
        )
        aggregate_policy["max_alerts_per_key"] = cfg.get(
            "max_alerts_per_key",
            aggregate_policy.get("max_alerts_per_key", 1),
        )
        dedup_fields = cfg.get("dedup_key_fields")
        if isinstance(dedup_fields, list):
            normalized_fields = [str(item).strip() for item in dedup_fields if str(item).strip()]
            if normalized_fields:
                aggregate_policy["dedup_key_fields"] = normalized_fields
        return self._allow_alert(alert, aggregate_policy)

    def _allow_alert(self, alert: dict[str, Any], policy: dict[str, Any]) -> bool:
        dedup_key = self._build_dedup_key(alert, policy)
        dedup_window = float(policy.get("dedup_window_sec", 0.0) or 0.0)
        throttle_window = float(policy.get("throttle_window_sec", 0.0) or 0.0)
        max_alerts = int(policy.get("max_alerts_per_key", 1) or 1)
        now = time.monotonic()

        with self._lock:
            last_emit = self._last_emit_at.get(dedup_key)
            if dedup_window > 0 and last_emit is not None and (now - last_emit) < dedup_window:
                return False

            history = self._window_emit_at[dedup_key]
            if throttle_window > 0:
                history = [ts for ts in history if (now - ts) <= throttle_window]
                self._window_emit_at[dedup_key] = history
            if throttle_window > 0 and len(history) >= max_alerts:
                return False

            self._last_emit_at[dedup_key] = now
            history.append(now)
            self._window_emit_at[dedup_key] = history
        return True


def build_default_watchdog_manager(
    policy_path: str | None = None,
    reload_interval_sec: float = 1.0,
) -> WatchdogManager:
    return WatchdogManager(
        plugins=[CrashWatchdog(), SecurityWatchdog()],
        policy_loader=WatchdogPolicyLoader(
            policy_path=policy_path,
            reload_interval_sec=reload_interval_sec,
        ),
    )
