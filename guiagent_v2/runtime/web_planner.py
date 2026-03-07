from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_WEB_SNAPSHOT_HINTS = (
    "snapshot",
    "截图",
    "检查",
    "校验",
)


@dataclass
class WebPlanStep:
    task: dict[str, Any]
    checkpoint: str
    rationale: str
    revision: int = 0

    def to_event_payload(self) -> dict[str, Any]:
        return {
            "task": dict(self.task),
            "checkpoint": self.checkpoint,
            "rationale": self.rationale,
            "revision": int(self.revision),
        }


def _normalize_web_task(route_context: dict[str, Any]) -> dict[str, Any]:
    base_task = route_context.get("web_task")
    if not isinstance(base_task, dict):
        return {"action": "snapshot", "interactive": True}
    action = str(base_task.get("action", "snapshot")).strip().lower() or "snapshot"
    normalized = dict(base_task)
    normalized["action"] = action
    return normalized


def build_initial_web_plan(
    instruction: str,
    route_context: dict[str, Any],
    max_steps: int,
) -> list[WebPlanStep]:
    budget = max(1, int(max_steps))
    text = str(instruction or "").strip().lower()
    task = _normalize_web_task(route_context)
    action = str(task.get("action", "snapshot")).strip().lower()
    steps: list[WebPlanStep] = []

    if action == "open":
        url = str(task.get("url", "")).strip()
        if url:
            steps.append(
                WebPlanStep(
                    task={"action": "open", "url": url},
                    checkpoint="page_opened",
                    rationale="open_target_url",
                )
            )
        else:
            steps.append(
                WebPlanStep(
                    task={"action": "snapshot", "interactive": True},
                    checkpoint="page_state_captured",
                    rationale="missing_url_fallback_to_snapshot",
                )
            )
        if len(steps) < budget:
            steps.append(
                WebPlanStep(
                    task={"action": "wait", "ms": 1000},
                    checkpoint="page_settled",
                    rationale="wait_for_page_stabilization",
                )
            )
        if len(steps) < budget:
            steps.append(
                WebPlanStep(
                    task={"action": "snapshot", "interactive": True},
                    checkpoint="page_state_verified",
                    rationale="verify_page_after_open",
                )
            )
    elif action in {"click", "type", "fill", "hover", "check", "uncheck"}:
        steps.append(
            WebPlanStep(
                task=dict(task),
                checkpoint="interaction_applied",
                rationale="execute_web_interaction",
            )
        )
        if len(steps) < budget:
            steps.append(
                WebPlanStep(
                    task={"action": "snapshot", "interactive": True},
                    checkpoint="post_interaction_verified",
                    rationale="verify_interaction_effect",
                )
            )
    else:
        steps.append(
            WebPlanStep(
                task=dict(task),
                checkpoint="web_task_applied",
                rationale="execute_base_web_task",
            )
        )

    if len(steps) < budget and any(hint in text for hint in _WEB_SNAPSHOT_HINTS):
        snapshot_task = {"action": "snapshot", "interactive": True}
        if not steps or steps[-1].task != snapshot_task:
            steps.append(
                WebPlanStep(
                    task=snapshot_task,
                    checkpoint="user_requested_snapshot",
                    rationale="instruction_contains_snapshot_hint",
                )
            )

    deduped: list[WebPlanStep] = []
    for step in steps:
        if deduped and deduped[-1].task == step.task:
            continue
        deduped.append(step)
        if len(deduped) >= budget:
            break
    return deduped


def build_replan_after_failure(
    failed_step: WebPlanStep,
    failed_reason: str,
    route_context: dict[str, Any],
    remaining_steps: int,
    revision: int,
) -> tuple[str, list[WebPlanStep]]:
    budget = max(0, int(remaining_steps))
    if budget <= 0:
        return "no_budget", []

    reason = str(failed_reason or "").strip().lower()
    base_task = _normalize_web_task(route_context)
    base_action = str(base_task.get("action", "snapshot")).strip().lower()
    replanned: list[WebPlanStep] = []
    strategy = "generic_snapshot"

    if "cli_not_found" in reason or "unsupported_request" in reason:
        # Backend capability is missing: skip local replan and fallback immediately.
        return "backend_unavailable", []

    if "timeout" in reason:
        strategy = "timeout_wait_then_snapshot"
        replanned.append(
            WebPlanStep(
                task={"action": "wait", "ms": 1500},
                checkpoint="page_settled_after_timeout",
                rationale="replan_wait_after_timeout",
                revision=revision,
            )
        )
        replanned.append(
            WebPlanStep(
                task={"action": "snapshot", "interactive": True},
                checkpoint="state_recaptured_after_timeout",
                rationale="replan_snapshot_after_timeout",
                revision=revision,
            )
        )
    elif "not_found" in reason or "selector" in reason:
        strategy = "selector_refresh_snapshot"
        replanned.append(
            WebPlanStep(
                task={"action": "snapshot", "interactive": True},
                checkpoint="state_recaptured_for_selector_recovery",
                rationale="replan_refresh_for_missing_selector",
                revision=revision,
            )
        )
    elif "auth" in reason or "forbidden" in reason or "unauthorized" in reason:
        strategy = "auth_recovery_snapshot"
        replanned.append(
            WebPlanStep(
                task={"action": "snapshot", "interactive": True},
                checkpoint="state_recaptured_for_auth",
                rationale="replan_auth_state_snapshot",
                revision=revision,
            )
        )
        replanned.append(
            WebPlanStep(
                task={"action": "wait", "ms": 800},
                checkpoint="auth_state_settled",
                rationale="replan_wait_for_auth_state",
                revision=revision,
            )
        )
    elif base_action == "open" and "url" in failed_step.task:
        strategy = "retry_open_after_wait"
        replanned.append(
            WebPlanStep(
                task={"action": "wait", "ms": 800},
                checkpoint="pre_retry_wait",
                rationale="replan_short_wait_before_retry_open",
                revision=revision,
            )
        )
        replanned.append(
            WebPlanStep(
                task={"action": "open", "url": str(failed_step.task.get("url", "")).strip()},
                checkpoint="retry_page_opened",
                rationale="replan_retry_open",
                revision=revision,
            )
        )
        replanned.append(
            WebPlanStep(
                task={"action": "snapshot", "interactive": True},
                checkpoint="retry_page_verified",
                rationale="replan_verify_after_retry_open",
                revision=revision,
            )
        )
    else:
        strategy = "generic_snapshot"
        replanned.append(
            WebPlanStep(
                task={"action": "snapshot", "interactive": True},
                checkpoint="state_recaptured_generic",
                rationale="replan_generic_snapshot",
                revision=revision,
            )
        )

    trimmed: list[WebPlanStep] = []
    for step in replanned:
        if step.task.get("action") == "open" and not str(step.task.get("url", "")).strip():
            continue
        if trimmed and trimmed[-1].task == step.task:
            continue
        trimmed.append(step)
        if len(trimmed) >= budget:
            break
    return strategy, trimmed
