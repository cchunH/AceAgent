#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_THIS_DIR)
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from guiagent_v2.runtime.validation_gate import evaluate_runtime_summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate GUIAgent stable validation gate.")
    parser.add_argument("--summary_json", type=str, required=True, help="Path to runtime_summary.json")
    parser.add_argument("--thresholds_json", type=str, default=None, help="Optional thresholds override json")
    parser.add_argument("--output_json", type=str, default=None, help="Optional output report path")
    parser.add_argument(
        "--strict_warn",
        action="store_true",
        default=False,
        help="Treat WARN as non-pass exit code",
    )
    return parser


def _load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON at {path} must be an object")
    return data


def main() -> int:
    args = _build_parser().parse_args()
    try:
        summary = _load_json(args.summary_json)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "overall_status": "FAIL",
                    "error": f"INVALID_SUMMARY_JSON:{exc}",
                    "summary_json": args.summary_json,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    thresholds = None
    if args.thresholds_json:
        try:
            thresholds = _load_json(args.thresholds_json)
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "overall_status": "FAIL",
                        "error": f"INVALID_THRESHOLDS_JSON:{exc}",
                        "thresholds_json": args.thresholds_json,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1

    report = evaluate_runtime_summary(summary, thresholds=thresholds)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    status = str(report.get("overall_status", "WARN")).upper()
    if status == "FAIL":
        return 1
    if status == "WARN" and args.strict_warn:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
