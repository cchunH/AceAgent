#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_THIS_DIR)
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from guiagent_v2.runtime.preflight import run_preflight


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GUIAgent blueprint preflight checks.")
    parser.add_argument("--log_root", type=str, default="logs")
    parser.add_argument("--screenshot_dir", type=str, default="screenshot")
    parser.add_argument("--temp_dir", type=str, default="temp")
    parser.add_argument("--require_adb", action="store_true", default=False)
    parser.add_argument("--require_perception_stack", action="store_true", default=False)
    parser.add_argument("--blueprint_vector_backend", type=str, default=None)
    parser.add_argument("--blueprint_vector_plugin", type=str, default=None)
    parser.add_argument("--output_json", type=str, default=None)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    report = run_preflight(
        log_root=args.log_root,
        screenshot_dir=args.screenshot_dir,
        temp_dir=args.temp_dir,
        require_adb=args.require_adb,
        require_perception_stack=args.require_perception_stack,
        blueprint_vector_backend=args.blueprint_vector_backend,
        blueprint_vector_plugin=args.blueprint_vector_plugin,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    return 0 if str(report.get("overall_status")) == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
