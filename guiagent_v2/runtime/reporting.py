from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from guiagent_v2.blueprint_hub import BlueprintRepository
from .flow_audit import audit_flow_from_jsonl
from .metrics import compute_metrics_from_jsonl


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _build_anchor_strategy_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    counts = dict(metrics.get("counts", {}) or {})
    return {
        "gate_count": int(counts.get("anchor_gate", 0) or 0),
        "allow_count": int(counts.get("anchor_gate_allow", 0) or 0),
        "retry_count": int(counts.get("anchor_gate_retry", 0) or 0),
        "deny_count": int(counts.get("anchor_gate_deny", 0) or 0),
        "retry_result_count": int(counts.get("anchor_micro_retry_result", 0) or 0),
        "retry_applied_count": int(counts.get("anchor_micro_retry_applied", 0) or 0),
        "retry_success_count": int(counts.get("anchor_micro_retry_success", 0) or 0),
        "retry_recovered_count": int(counts.get("anchor_micro_retry_recovered", 0) or 0),
        "allow_rate": float(metrics.get("anchor_gate_allow_rate", 0.0) or 0.0),
        "retry_rate": float(metrics.get("anchor_gate_retry_rate", 0.0) or 0.0),
        "deny_rate": float(metrics.get("anchor_gate_deny_rate", 0.0) or 0.0),
        "retry_applied_rate": float(metrics.get("anchor_micro_retry_applied_rate", 0.0) or 0.0),
        "retry_success_rate": float(metrics.get("anchor_micro_retry_success_rate", 0.0) or 0.0),
        "retry_recovered_rate": float(metrics.get("anchor_micro_retry_recovered_rate", 0.0) or 0.0),
    }


def _build_topology_projection_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    counts = dict(metrics.get("counts", {}) or {})
    return {
        "projection_event_count": int(counts.get("topology_projection", 0) or 0),
        "affine_count": int(counts.get("topology_projection_affine", 0) or 0),
        "scale_count": int(counts.get("topology_projection_scale", 0) or 0),
        "guard_block_count": int(counts.get("topology_projection_guard_block", 0) or 0),
        "affine_rate": float(metrics.get("topology_projection_affine_rate", 0.0) or 0.0),
        "scale_rate": float(metrics.get("topology_projection_scale_rate", 0.0) or 0.0),
        "guard_block_rate": float(metrics.get("topology_projection_guard_block_rate", 0.0) or 0.0),
        "fit_error_p50": float(metrics.get("topology_projection_fit_error_p50", 0.0) or 0.0),
        "fit_error_p95": float(metrics.get("topology_projection_fit_error_p95", 0.0) or 0.0),
    }


def _build_screenshot_trace_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    counts = dict(metrics.get("counts", {}) or {})
    return {
        "snapshot_event_count": int(counts.get("snapshot_captured", 0) or 0),
        "snapshot_with_path_count": int(counts.get("snapshot_with_path", 0) or 0),
        "snapshot_with_path_rate": float(metrics.get("snapshot_with_path_rate", 0.0) or 0.0),
        "mobile_adapter_call_count": int(counts.get("mobile_adapter_call", 0) or 0),
        "mobile_action_screenshot_count": int(counts.get("mobile_action_screenshot", 0) or 0),
        "mobile_action_screenshot_rate": float(metrics.get("mobile_action_screenshot_rate", 0.0) or 0.0),
    }


def _build_blueprint_sync_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    counts = dict(metrics.get("counts", {}) or {})
    return {
        "sync_event_count": int(counts.get("blueprint_sync", 0) or 0),
        "success_count": int(counts.get("blueprint_sync_success", 0) or 0),
        "failed_count": int(counts.get("blueprint_sync_failed", 0) or 0),
        "metadata_only_count": int(counts.get("blueprint_sync_metadata_only", 0) or 0),
        "replay_gate_pass_count": int(counts.get("replay_gate_pass", 0) or 0),
        "replay_gate_block_count": int(counts.get("replay_gate_block", 0) or 0),
        "success_rate": float(metrics.get("blueprint_sync_success_rate", 0.0) or 0.0),
        "failed_rate": float(metrics.get("blueprint_sync_failed_rate", 0.0) or 0.0),
        "metadata_only_rate": float(metrics.get("blueprint_sync_metadata_only_rate", 0.0) or 0.0),
        "replay_gate_pass_rate": float(metrics.get("replay_gate_pass_rate", 0.0) or 0.0),
        "replay_gate_block_rate": float(metrics.get("replay_gate_block_rate", 0.0) or 0.0),
        "replay_quality_score_p50": float(metrics.get("replay_quality_score_p50", 0.0) or 0.0),
        "replay_quality_score_p95": float(metrics.get("replay_quality_score_p95", 0.0) or 0.0),
    }


def write_runtime_summary(
    log_dir: str,
    event_log_path: str,
    blueprint_repo: BlueprintRepository | None = None,
) -> dict[str, Any]:
    metrics = compute_metrics_from_jsonl(event_log_path)
    summary = {
        "generated_at": _utc_now_iso(),
        "event_log": event_log_path,
        "metrics": metrics,
        "anchor_strategy": _build_anchor_strategy_summary(metrics),
        "topology_projection": _build_topology_projection_summary(metrics),
        "screenshot_trace": _build_screenshot_trace_summary(metrics),
        "blueprint_sync": _build_blueprint_sync_summary(metrics),
        "flow_audit": audit_flow_from_jsonl(event_log_path),
        "blueprint_count": len(blueprint_repo.list_blueprints()) if blueprint_repo else 0,
        "blueprint_vector_backend": (
            blueprint_repo.get_vector_backend_info() if blueprint_repo else None
        ),
    }

    out_path = os.path.join(log_dir, "runtime_summary.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return {"summary_path": out_path, "summary": summary}
