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
    parser = argparse.ArgumentParser(description="One-shot stable validation entry for GUIAgent v2.")
    parser.add_argument("--tasks_json", type=str, required=True)
    parser.add_argument("--run_name", type=str, default="stable_validation_entry")
    parser.add_argument("--log_root", type=str, default="logs")
    parser.add_argument("--runtime_mode", type=str, default="guiagent_v2", choices=["guiagent_v2_shadow", "guiagent_v2"])
    parser.add_argument("--mobile_execution_mode", type=str, default="shadow", choices=["auto", "shadow", "device"])
    parser.add_argument("--v2_use_live_perception", action="store_true", default=False)
    parser.add_argument("--v2_disable_action_screenshots", action="store_true", default=False)
    parser.add_argument("--skip_preflight", action="store_true", default=False)
    parser.add_argument("--require_adb", action="store_true", default=False)
    parser.add_argument(
        "--thresholds_json",
        type=str,
        default="docs/guiagent-plan/02-phase-0/stable-validation-thresholds-v1.json",
    )
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


def _collect_runtime_summaries(run_dir: str) -> list[str]:
    pattern = os.path.join(run_dir, "*", "runtime_summary.json")
    return sorted(glob.glob(pattern))


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
    thresholds = _load_json(args.thresholds_json) if os.path.exists(args.thresholds_json) else None
    reports: list[dict[str, Any]] = []
    for path in summaries:
        report = evaluate_runtime_summary(_load_json(path), thresholds=thresholds)
        report["runtime_summary_path"] = path
        reports.append(report)

    totals = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for row in reports:
        status = str(row.get("overall_status", "WARN")).upper()
        if status not in totals:
            status = "WARN"
        totals[status] += 1

    overall_status = "PASS"
    if run_rc != 0 or totals["FAIL"] > 0:
        overall_status = "FAIL"
    elif totals["WARN"] > 0:
        overall_status = "WARN"

    payload = {
        "overall_status": overall_status,
        "run_return_code": int(run_rc),
        "run_dir": run_dir,
        "summary_count": len(summaries),
        "totals": totals,
        "reports": reports,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    return 0 if overall_status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
