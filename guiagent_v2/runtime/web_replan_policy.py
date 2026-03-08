from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReplanDecision:
    allow: bool
    reason_key: str
    allowed_attempts: int
    attempted: int
    policy_note: str


def normalize_reason_key(reason: str) -> str:
    text = str(reason or "").strip().lower()
    if not text:
        return "unknown"
    if "cli_not_found" in text or "unsupported_request" in text:
        return "backend_unavailable"
    if "timeout" in text:
        return "timeout"
    if "selector" in text or "not_found" in text:
        return "selector_missing"
    if "auth" in text or "forbidden" in text or "unauthorized" in text:
        return "auth_blocked"
    return "generic_failure"


class WebReplanPolicy:
    """Task-local replan policy with simple feedback loop from past outcomes."""

    def __init__(self, base_max_attempts: int):
        self._base_max_attempts = max(0, int(base_max_attempts))
        self._stats: dict[str, dict[str, int]] = {}

    def _base_cap_for_reason(self, reason_key: str) -> int:
        caps = {
            "backend_unavailable": 0,
            "auth_blocked": 1,
            "timeout": 2,
            "selector_missing": 2,
            "generic_failure": self._base_max_attempts,
            "unknown": 1,
        }
        return min(self._base_max_attempts, caps.get(reason_key, self._base_max_attempts))

    def _get_stats(self, reason_key: str) -> dict[str, int]:
        return self._stats.setdefault(reason_key, {"failures": 0, "recoveries": 0})

    def decide(self, reason: str, attempted: int) -> ReplanDecision:
        reason_key = normalize_reason_key(reason)
        base_cap = self._base_cap_for_reason(reason_key)
        stats = self._get_stats(reason_key)
        failure_bias = int(stats.get("failures", 0)) - int(stats.get("recoveries", 0))
        adjusted_cap = base_cap
        note = "baseline_cap"

        if failure_bias >= 2 and adjusted_cap > 0:
            adjusted_cap = max(0, adjusted_cap - 1)
            note = "decrease_cap_by_failure_bias"
        elif stats.get("recoveries", 0) >= stats.get("failures", 0) + 2 and adjusted_cap < self._base_max_attempts:
            adjusted_cap = min(self._base_max_attempts, adjusted_cap + 1)
            note = "increase_cap_by_recovery_bias"

        attempted = max(0, int(attempted))
        return ReplanDecision(
            allow=attempted < adjusted_cap,
            reason_key=reason_key,
            allowed_attempts=adjusted_cap,
            attempted=attempted,
            policy_note=note,
        )

    def record_failure(self, reason: str) -> None:
        reason_key = normalize_reason_key(reason)
        stats = self._get_stats(reason_key)
        stats["failures"] = int(stats.get("failures", 0)) + 1

    def record_recovery(self, reason: str) -> None:
        reason_key = normalize_reason_key(reason)
        stats = self._get_stats(reason_key)
        stats["recoveries"] = int(stats.get("recoveries", 0)) + 1

