from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


DEFAULT_VALIDATION_THRESHOLDS: dict[str, Any] = {
    "task_success_rate_min": 0.70,
    "s2_takeover_rate_max": 0.60,
    "assertion_fail_rate_max": 0.45,
    "anchor_gate_deny_rate_max": 0.25,
    "topology_projection_min_samples": 3,
    "topology_projection_guard_block_rate_max": 0.25,
    "topology_projection_fit_error_p95_max": 0.20,
    "topology_projection_affine_rate_min": 0.40,
}


@dataclass
class ValidationCheck:
    name: str
    status: str
    message: str
    value: float | None
    threshold: float | None
    operator: str
    detail: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_status(status: str) -> str:
    value = str(status or "").strip().upper()
    if value in {"PASS", "WARN", "FAIL"}:
        return value
    return "WARN"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _resolve_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(summary, dict):
        return {}
    if isinstance(summary.get("metrics"), dict):
        return dict(summary.get("metrics", {}))
    return dict(summary)


def _build_thresholds(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    thresholds = dict(DEFAULT_VALIDATION_THRESHOLDS)
    if isinstance(overrides, dict):
        for key, value in overrides.items():
            thresholds[str(key)] = value
    return thresholds


def _check_min(name: str, value: float, threshold: float, detail: dict[str, Any] | None = None) -> ValidationCheck:
    passed = float(value) >= float(threshold)
    return ValidationCheck(
        name=name,
        status="PASS" if passed else "FAIL",
        message=f"{name} {'>=' if passed else '<'} {threshold}",
        value=float(value),
        threshold=float(threshold),
        operator=">=",
        detail=dict(detail or {}),
    )


def _check_max(name: str, value: float, threshold: float, detail: dict[str, Any] | None = None) -> ValidationCheck:
    passed = float(value) <= float(threshold)
    return ValidationCheck(
        name=name,
        status="PASS" if passed else "FAIL",
        message=f"{name} {'<=' if passed else '>'} {threshold}",
        value=float(value),
        threshold=float(threshold),
        operator="<=",
        detail=dict(detail or {}),
    )


def evaluate_runtime_summary(
    summary: dict[str, Any],
    *,
    thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metrics = _resolve_metrics(summary)
    cfg = _build_thresholds(thresholds)
    counts = dict(metrics.get("counts", {}) or {})
    checks: list[ValidationCheck] = []

    checks.append(
        _check_min(
            "task_success_rate",
            _safe_float(metrics.get("task_success_rate", 0.0), 0.0),
            _safe_float(cfg.get("task_success_rate_min", 0.0), 0.0),
        )
    )
    checks.append(
        _check_max(
            "s2_takeover_rate",
            _safe_float(metrics.get("s2_takeover_rate", 0.0), 0.0),
            _safe_float(cfg.get("s2_takeover_rate_max", 1.0), 1.0),
        )
    )
    checks.append(
        _check_max(
            "assertion_fail_rate",
            _safe_float(metrics.get("assertion_fail_rate", 0.0), 0.0),
            _safe_float(cfg.get("assertion_fail_rate_max", 1.0), 1.0),
        )
    )
    checks.append(
        _check_max(
            "anchor_gate_deny_rate",
            _safe_float(metrics.get("anchor_gate_deny_rate", 0.0), 0.0),
            _safe_float(cfg.get("anchor_gate_deny_rate_max", 1.0), 1.0),
        )
    )

    topology_count = _safe_int(counts.get("topology_projection", 0), 0)
    topology_min_samples = _safe_int(cfg.get("topology_projection_min_samples", 3), 3)
    if topology_count < topology_min_samples:
        checks.append(
            ValidationCheck(
                name="topology_projection_samples",
                status="WARN",
                message="topology projection samples below threshold; skip strict topology checks",
                value=float(topology_count),
                threshold=float(topology_min_samples),
                operator=">=",
                detail={"topology_projection_count": topology_count},
            )
        )
    else:
        checks.append(
            _check_max(
                "topology_projection_guard_block_rate",
                _safe_float(metrics.get("topology_projection_guard_block_rate", 0.0), 0.0),
                _safe_float(cfg.get("topology_projection_guard_block_rate_max", 1.0), 1.0),
                detail={"topology_projection_count": topology_count},
            )
        )
        checks.append(
            _check_max(
                "topology_projection_fit_error_p95",
                _safe_float(metrics.get("topology_projection_fit_error_p95", 0.0), 0.0),
                _safe_float(cfg.get("topology_projection_fit_error_p95_max", 1.0), 1.0),
                detail={"topology_projection_count": topology_count},
            )
        )
        checks.append(
            _check_min(
                "topology_projection_affine_rate",
                _safe_float(metrics.get("topology_projection_affine_rate", 0.0), 0.0),
                _safe_float(cfg.get("topology_projection_affine_rate_min", 0.0), 0.0),
                detail={"topology_projection_count": topology_count},
            )
        )

    totals = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for item in checks:
        totals[_normalize_status(item.status)] += 1

    overall_status = "PASS"
    if totals["FAIL"] > 0:
        overall_status = "FAIL"
    elif totals["WARN"] > 0:
        overall_status = "WARN"

    return {
        "overall_status": overall_status,
        "totals": totals,
        "thresholds": cfg,
        "metrics_snapshot": {
            "task_success_rate": _safe_float(metrics.get("task_success_rate", 0.0), 0.0),
            "s2_takeover_rate": _safe_float(metrics.get("s2_takeover_rate", 0.0), 0.0),
            "assertion_fail_rate": _safe_float(metrics.get("assertion_fail_rate", 0.0), 0.0),
            "anchor_gate_deny_rate": _safe_float(metrics.get("anchor_gate_deny_rate", 0.0), 0.0),
            "topology_projection_affine_rate": _safe_float(
                metrics.get("topology_projection_affine_rate", 0.0), 0.0
            ),
            "topology_projection_guard_block_rate": _safe_float(
                metrics.get("topology_projection_guard_block_rate", 0.0), 0.0
            ),
            "topology_projection_fit_error_p95": _safe_float(
                metrics.get("topology_projection_fit_error_p95", 0.0), 0.0
            ),
            "topology_projection_count": topology_count,
        },
        "checks": [item.to_dict() for item in checks],
    }
