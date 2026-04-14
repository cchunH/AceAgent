#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
from typing import Any

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_THIS_DIR)
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from guiagent_v2.runtime.validation_gate import evaluate_runtime_summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Complex-task validation entry for GUIAgent v2.")
    parser.add_argument(
        "--tasks_json",
        type=str,
        default="docs/guiagent-plan/02-phase-0/stable-validation-complex-tasks-v1.json",
    )
    parser.add_argument("--run_name", type=str, default="stable_validation_complex_v1")
    parser.add_argument("--log_root", type=str, default="logs")
    parser.add_argument("--runtime_mode", type=str, default="guiagent_v2", choices=["guiagent_v2"])
    parser.add_argument("--mobile_execution_mode", type=str, default="device", choices=["auto", "shadow", "device"])
    parser.add_argument("--v2_use_live_perception", action="store_true", default=False)
    parser.add_argument("--v2_disable_action_screenshots", action="store_true", default=False)
    parser.add_argument("--skip_preflight", action="store_true", default=False)
    parser.add_argument("--require_adb", action="store_true", default=True)
    parser.add_argument(
        "--thresholds_json",
        type=str,
        default="docs/guiagent-plan/02-phase-0/stable-validation-thresholds-v1.json",
    )
    parser.add_argument("--require_model_task_plan", action="store_true", default=True)
    parser.add_argument("--min_planned_subtasks", type=int, default=2)
    parser.add_argument("--require_page_hint_gate", action="store_true", default=True)
    parser.add_argument("--output_json", type=str, default=None)
    return parser


def _run(cmd: list[str]) -> int:
    completed = subprocess.run(cmd, cwd=_ROOT_DIR, check=False)
    return int(completed.returncode)


def _load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a JSON object")
    return data


def _load_events(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            try:
                item = json.loads(raw)
            except Exception:
                continue
            if isinstance(item, dict):
                rows.append(item)
    return rows


def _collect_task_dirs(run_dir: str) -> list[str]:
    return sorted([p for p in glob.glob(os.path.join(run_dir, "*")) if os.path.isdir(p)])


def _collect_runtime_summaries(run_dir: str) -> list[str]:
    return sorted(glob.glob(os.path.join(run_dir, "*", "runtime_summary.json")))


def _task_extra_checks(
    *,
    task_dir: str,
    require_model_task_plan: bool,
    min_planned_subtasks: int,
    require_page_hint_gate: bool,
) -> dict[str, Any]:
    events_path = os.path.join(task_dir, "events.jsonl")
    if not os.path.exists(events_path):
        return {
            "overall_status": "FAIL",
            "checks": {
                "events_exists": False,
                "model_task_plan_ok": False,
                "page_hint_gate_ok": False,
            },
            "issues": ["MISSING_EVENTS_JSONL"],
        }

    events = _load_events(events_path)
    plan_events = [
        e for e in events
        if str(e.get("event_type", "")) == "model_task_plan"
        and str(e.get("status", "")).upper() == "SUCCESS"
    ]
    page_gate_events = [e for e in events if str(e.get("event_type", "")) == "page_hint_gate"]

    max_subtasks = 0
    for e in plan_events:
        try:
            max_subtasks = max(max_subtasks, int(e.get("planned_subtasks_count", 0) or 0))
        except Exception:
            pass

    checks = {
        "events_exists": True,
        "model_task_plan_ok": (not require_model_task_plan) or (len(plan_events) > 0 and max_subtasks >= int(min_planned_subtasks)),
        "page_hint_gate_ok": (not require_page_hint_gate) or (len(page_gate_events) > 0),
    }
    issues: list[str] = []
    if not checks["model_task_plan_ok"]:
        issues.append("MODEL_TASK_PLAN_MISSING_OR_WEAK")
    if not checks["page_hint_gate_ok"]:
        issues.append("PAGE_HINT_GATE_MISSING")

    overall = "PASS" if all(checks.values()) else "FAIL"
    return {
        "overall_status": overall,
        "checks": checks,
        "issues": issues,
        "events_path": events_path,
        "model_task_plan_count": len(plan_events),
        "max_planned_subtasks_count": int(max_subtasks),
        "page_hint_gate_count": len(page_gate_events),
    }


def main() -> int:
    args = _build_parser().parse_args()

    if not args.skip_preflight:
        preflight_cmd = [
            "python3",
            "scripts/blueprint_preflight.py",
            "--blueprint_vector_backend",
            "memory",
        ]
        if args.require_adb:
            preflight_cmd.append("--require_adb")
        if _run(preflight_cmd) != 0:
            print(json.dumps({"overall_status": "FAIL", "stage": "preflight"}, ensure_ascii=False, indent=2))
            return 1

    run_cmd = [
        "python3",
        "run.py",
        "--tasks_json",
        args.tasks_json,
        "--run_name",
        args.run_name,
        "--log_root",
        args.log_root,
        "--runtime_mode",
        args.runtime_mode,
        "--v2_skip_legacy",
        "--mobile_execution_mode",
        args.mobile_execution_mode,
    ]
    if args.v2_use_live_perception:
        run_cmd.append("--v2_use_live_perception")
    if args.v2_disable_action_screenshots:
        run_cmd.append("--v2_disable_action_screenshots")
    run_rc = _run(run_cmd)

    run_dir = os.path.join(args.log_root, args.run_name)
    summaries = _collect_runtime_summaries(run_dir)
    task_dirs = _collect_task_dirs(run_dir)
    thresholds = _load_json(args.thresholds_json) if os.path.exists(args.thresholds_json) else None

    reports: list[dict[str, Any]] = []
    summary_map = {os.path.dirname(path): path for path in summaries}
    for task_dir in task_dirs:
        summary_path = summary_map.get(task_dir)
        if summary_path and os.path.exists(summary_path):
            gate_report = evaluate_runtime_summary(_load_json(summary_path), thresholds=thresholds)
        else:
            gate_report = {
                "overall_status": "FAIL",
                "error": "MISSING_RUNTIME_SUMMARY",
            }
        extra = _task_extra_checks(
            task_dir=task_dir,
            require_model_task_plan=bool(args.require_model_task_plan),
            min_planned_subtasks=int(args.min_planned_subtasks),
            require_page_hint_gate=bool(args.require_page_hint_gate),
        )
        status = "PASS"
        if str(gate_report.get("overall_status", "WARN")).upper() == "FAIL":
            status = "FAIL"
        elif str(gate_report.get("overall_status", "WARN")).upper() == "WARN":
            status = "WARN"
        if str(extra.get("overall_status", "PASS")).upper() == "FAIL":
            status = "FAIL"

        reports.append(
            {
                "task_dir": task_dir,
                "runtime_summary_path": summary_path,
                "status": status,
                "gate": gate_report,
                "extra": extra,
            }
        )

    totals = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for row in reports:
        status = str(row.get("status", "WARN")).upper()
        if status not in totals:
            status = "WARN"
        totals[status] += 1

    overall = "PASS"
    if run_rc != 0 or totals["FAIL"] > 0:
        overall = "FAIL"
    elif totals["WARN"] > 0:
        overall = "WARN"

    payload = {
        "overall_status": overall,
        "run_return_code": int(run_rc),
        "run_dir": run_dir,
        "task_count": len(task_dirs),
        "totals": totals,
        "reports": reports,
        "checks_config": {
            "require_model_task_plan": bool(args.require_model_task_plan),
            "min_planned_subtasks": int(args.min_planned_subtasks),
            "require_page_hint_gate": bool(args.require_page_hint_gate),
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
