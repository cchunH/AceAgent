from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import Any

from UniMind.device.controller import (
    back,
    enter,
    ensure_adb_keyboard_active,
    home,
    long_press,
    swipe,
    switch_app,
    tap,
    type,
)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _normalize_mode(value: str | None) -> str:
    mode = str(value or "auto").strip().lower()
    if mode in {"shadow", "device", "auto"}:
        return mode
    return "auto"


@dataclass
class MobileDeviceExecutor:
    adb_path: str = "adb"
    execution_mode: str = "auto"
    default_wait_ms: int = 1000
    adb_check_timeout_sec: float = 2.0

    def __post_init__(self) -> None:
        self.execution_mode = _normalize_mode(self.execution_mode)
        self._adb_available_cache: bool | None = None

    def is_adb_available(self) -> bool:
        if self._adb_available_cache is not None:
            return bool(self._adb_available_cache)

        cmd = f"{self.adb_path} devices"
        try:
            completed = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=max(0.5, float(self.adb_check_timeout_sec)),
                check=False,
            )
            available = completed.returncode == 0
        except Exception:
            available = False
        self._adb_available_cache = bool(available)
        return bool(available)

    def execute_action(
        self,
        action: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = dict(context or {})
        action_obj = dict(action or {})
        name = str(action_obj.get("name", "Wait")).strip() or "Wait"
        arguments = dict(action_obj.get("arguments", {}) or {})
        mode = _normalize_mode(self.execution_mode)

        if mode == "shadow":
            return {
                "success": True,
                "execution_mode": "shadow",
                "device_executed": False,
                "error": None,
                "action_name": name,
                "latency_ms": 0,
            }

        adb_available = self.is_adb_available()
        if mode == "auto" and not adb_available:
            return {
                "success": True,
                "execution_mode": "shadow",
                "device_executed": False,
                "error": "ADB_UNAVAILABLE_AUTO_FALLBACK",
                "action_name": name,
                "latency_ms": 0,
            }
        if mode == "device" and not adb_available:
            return {
                "success": False,
                "execution_mode": "device",
                "device_executed": False,
                "error": "ADB_UNAVAILABLE",
                "action_name": name,
                "latency_ms": 0,
            }

        start = time.time()
        try:
            executed = self._execute_device_action(name, arguments, context=context)
        except Exception as exc:
            return {
                "success": False,
                "execution_mode": "device",
                "device_executed": False,
                "error": f"DEVICE_EXEC_ERROR:{exc}",
                "action_name": name,
                "latency_ms": int(max(0.0, time.time() - start) * 1000),
            }

        return {
            "success": bool(executed),
            "execution_mode": "device",
            "device_executed": bool(executed),
            "error": None if executed else "DEVICE_EXEC_NOT_EXECUTED",
            "action_name": name,
            "latency_ms": int(max(0.0, time.time() - start) * 1000),
        }

    def _execute_device_action(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        context: dict[str, Any],
    ) -> bool:
        action = str(name or "").strip().lower()
        if action == "tap":
            tap(self.adb_path, _as_int(arguments.get("x")), _as_int(arguments.get("y")))
            return True
        if action == "swipe":
            swipe(
                self.adb_path,
                _as_int(arguments.get("x1")),
                _as_int(arguments.get("y1")),
                _as_int(arguments.get("x2")),
                _as_int(arguments.get("y2")),
            )
            return True
        if action == "type":
            ensure_adb_keyboard_active(self.adb_path)
            text(self.adb_path, str(arguments.get("text", "")))
            return True
        if action == "enter":
            enter(self.adb_path)
            return True
        if action == "back":
            back(self.adb_path)
            return True
        if action == "home":
            home(self.adb_path)
            return True
        if action == "switch_app":
            switch_app(self.adb_path)
            return True
        if action == "long_press":
            duration_ms = _as_int(arguments.get("duration_ms"), default=1000)
            long_press(
                self.adb_path,
                _as_int(arguments.get("x")),
                _as_int(arguments.get("y")),
                duration_ms=max(100, duration_ms),
            )
            return True
        if action == "wait":
            wait_ms = _as_int(
                context.get("wait_ms", arguments.get("wait_ms", self.default_wait_ms)),
                default=self.default_wait_ms,
            )
            time.sleep(max(0, wait_ms) / 1000.0)
            return True
        if action == "open_app":
            # Keep explicit failure until Open_App is bridged with live perception pipeline.
            raise RuntimeError("OPEN_APP_NOT_YET_SUPPORTED_IN_V2_DEVICE_BRIDGE")
        raise RuntimeError(f"UNSUPPORTED_ACTION:{name}")
