#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from guiagent_v2.runtime.preflight import run_preflight


@dataclass
class CmdResult:
    name: str
    rc: int
    stdout_tail: str
    stderr_tail: str
    timed_out: bool = False


def _tail(text: str, n: int = 3000) -> str:
    if not text:
        return ""
    return text[-n:]


def _run_shell(name: str, command: str, timeout_sec: int = 600) -> CmdResult:
    try:
        completed = subprocess.run(
            ["bash", "-lc", command],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=int(timeout_sec),
            check=False,
        )
        return CmdResult(
            name=name,
            rc=int(completed.returncode),
            stdout_tail=_tail(completed.stdout),
            stderr_tail=_tail(completed.stderr),
            timed_out=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CmdResult(
            name=name,
            rc=124,
            stdout_tail=_tail((exc.stdout or "") if isinstance(exc.stdout, str) else ""),
            stderr_tail=_tail((exc.stderr or "") if isinstance(exc.stderr, str) else ""),
            timed_out=True,
        )


def _collect_events(run_name: str, log_root: str) -> tuple[str | None, list[dict[str, Any]]]:
    pattern = str(Path(log_root) / "**" / run_name / "*" / "events.jsonl")
    files = sorted(glob.glob(pattern, recursive=True))
    if not files:
        return None, []
    target = files[-1]
    events: list[dict[str, Any]] = []
    with open(target, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                events.append(row)
    return target, events


def _event_checks(events: list[dict[str, Any]]) -> dict[str, Any]:
    has_intent_parse_event = any(e.get("event_type") == "model_intent_parse" for e in events)
    has_v2_cfg = any(e.get("event_type") == "v2_model_config" for e in events)
    has_intent_parse_ok = any(
        e.get("event_type") == "model_intent_parse" and str(e.get("status", "")).upper() == "SUCCESS"
        for e in events
    )
    has_agent_browser_success = any(
        e.get("event_type") == "adapter_call"
        and e.get("adapter_backend") == "agent-browser"
        and str(e.get("status", "")).upper() == "SUCCESS"
        for e in events
    )
    has_cli_not_found = any(
        e.get("event_type") == "adapter_call"
        and (
            str(e.get("reason_code", "")).upper() == "CLI_NOT_FOUND"
            or str(e.get("error", "")).upper() == "CLI_NOT_FOUND"
        )
        for e in events
    )
    has_step_end_success = any(
        e.get("event_type") == "step_end" and str(e.get("status", "")).upper() == "SUCCESS"
        for e in events
    )
    has_task_end = any(e.get("event_type") == "task_end" for e in events)

    return {
        "has_v2_model_config": has_v2_cfg,
        "has_model_intent_parse_event": has_intent_parse_event,
        "has_model_intent_parse_success": has_intent_parse_ok,
        "has_agent_browser_adapter_success": has_agent_browser_success,
        "has_cli_not_found_error": has_cli_not_found,
        "has_step_end_success": has_step_end_success,
        "has_task_end": has_task_end,
        "event_count": len(events),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="GUIAgent v2 readiness gate for real-device testing stage")
    parser.add_argument("--log_root", type=str, default="logs")
    parser.add_argument("--run_name_prefix", type=str, default="readiness_gate_v2")
    parser.add_argument("--instruction", type=str, default="open about:blank and take snapshot")
    parser.add_argument(
        "--smoke_runtime_mode",
        type=str,
        default="guiagent_v2",
        choices=["guiagent_v2", "guiagent_v2_shadow"],
    )
    parser.add_argument("--skip_setup", action="store_true", default=False)
    parser.add_argument("--skip_tests", action="store_true", default=False)
    parser.add_argument("--tests_scope", type=str, default="full", choices=["full", "targeted"])
    parser.add_argument("--smoke_use_models", action="store_true", default=False)
    parser.add_argument("--smoke_timeout_sec", type=int, default=180)
    parser.add_argument("--output_json", type=str, default=None)
    args = parser.parse_args()

    started_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    run_name = f"{args.run_name_prefix}_{time.strftime('%Y%m%d_%H%M%S')}"

    setup_result = None
    if not args.skip_setup:
        setup_result = _run_shell(
            name="setup_agent_browser_local",
            command="AGENT_BROWSER_SETUP_PREFER_NPM=1 ./scripts/setup_agent_browser_local.sh",
            timeout_sec=1200,
        )

    preflight = run_preflight(
        log_root=args.log_root,
        screenshot_dir="screenshot",
        temp_dir="temp",
        require_adb=False,
        require_perception_stack=False,
        blueprint_vector_backend="memory",
        blueprint_vector_plugin=None,
    )

    tests_result = None
    if not args.skip_tests:
        if args.tests_scope == "targeted":
            tests_cmd = (
                "python3 -m unittest discover -s test -p 'test_agent_browser_skill.py' -q && "
                "python3 -m unittest discover -s test -p 'test_runtime_preflight.py' -q && "
                "python3 -m unittest discover -s test -p 'test_v2_executor.py' -q"
            )
        else:
            tests_cmd = "python3 -m unittest discover -s test -p 'test_*.py' -q"
        tests_result = _run_shell(name="unittest", command=tests_cmd, timeout_sec=1800)

    smoke_prefix = [
        "source scripts/use_guiagent_v2_env.sh",
    ]
    if not args.smoke_use_models:
        smoke_prefix.append("export GUIAGENT_V2_ENABLE_INTENT_PARSER=0")
        smoke_prefix.append("export GUIAGENT_V2_ENABLE_WEB_REPLAN=0")
        smoke_prefix.append("export GUIAGENT_V2_ENABLE_ASSERTION_REPAIR=0")

    smoke_cmd = " && ".join(
        [
            *smoke_prefix,
            (
                f"python3 run.py --runtime_mode {shlex.quote(args.smoke_runtime_mode)} --v2_skip_legacy "
                "--mobile_execution_mode shadow "
                f"--instruction {shlex.quote(args.instruction)} "
                f"--run_name {shlex.quote(run_name)} --log_root {shlex.quote(args.log_root)} "
                "--max_itr 4 --max_consecutive_failures 2 --overwrite_task_log_dir"
            ),
        ]
    )
    smoke_result = _run_shell(name="dashscope_v2_smoke", command=smoke_cmd, timeout_sec=args.smoke_timeout_sec)

    events_path, events = _collect_events(run_name=run_name, log_root=args.log_root)
    event_summary = _event_checks(events)

    checks: dict[str, bool] = {
        "setup_ok": (setup_result is None) or (setup_result.rc == 0),
        "preflight_ok": str(preflight.get("overall_status", "")).upper() == "PASS",
        "tests_ok": (tests_result is None) or (tests_result.rc == 0),
        "smoke_ok": smoke_result.rc == 0 and not smoke_result.timed_out,
        "v2_model_config_ok": bool(event_summary["has_v2_model_config"]),
        "agent_browser_ok": bool(event_summary["has_agent_browser_adapter_success"]),
        "no_cli_not_found": not bool(event_summary["has_cli_not_found_error"]),
        "step_end_ok": bool(event_summary["has_step_end_success"]),
        "task_end_ok": bool(event_summary["has_task_end"]),
    }
    if args.smoke_use_models:
        checks["intent_parse_ok"] = bool(event_summary["has_model_intent_parse_success"])
    else:
        checks["intent_parse_path_ok"] = True

    overall = "PASS" if all(checks.values()) else "FAIL"

    payload = {
        "overall_status": overall,
        "started_at": started_at,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "run_name": run_name,
        "log_root": args.log_root,
        "checks": checks,
        "preflight": preflight,
        "setup_result": None if setup_result is None else setup_result.__dict__,
        "tests_result": None if tests_result is None else tests_result.__dict__,
        "smoke_result": smoke_result.__dict__,
        "events_path": events_path,
        "event_summary": event_summary,
    }

    if args.output_json:
        out = Path(args.output_json)
    else:
        out_dir = ROOT_DIR / "docs" / "guiagent-plan" / "02-phase-0"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"real-test-readiness-{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        "overall_status": overall,
        "run_name": run_name,
        "events_path": events_path,
        "report_path": str(out),
        "checks": checks,
    }, ensure_ascii=False, indent=2))
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
