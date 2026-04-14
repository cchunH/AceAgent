from __future__ import annotations

import importlib
import importlib.util
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class CheckResult:
    name: str
    status: str
    message: str
    detail: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _status(status: str) -> str:
    value = str(status or "").strip().upper()
    if value in {"PASS", "WARN", "FAIL"}:
        return value
    return "WARN"


def _check_python_version(min_version: tuple[int, int] = (3, 10)) -> CheckResult:
    current = (sys.version_info.major, sys.version_info.minor)
    passed = current >= min_version
    return CheckResult(
        name="python_version",
        status="PASS" if passed else "FAIL",
        message=(
            f"Python {current[0]}.{current[1]} detected"
            if passed
            else f"Python {current[0]}.{current[1]} is below required {min_version[0]}.{min_version[1]}"
        ),
        detail={"current": current, "required": min_version},
    )


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(str(module_name).strip()) is not None


def _check_module(module_name: str, required: bool = True) -> CheckResult:
    exists = _module_available(module_name)
    if exists:
        return CheckResult(
            name=f"module:{module_name}",
            status="PASS",
            message=f"Module '{module_name}' is available",
            detail={"module": module_name},
        )
    return CheckResult(
        name=f"module:{module_name}",
        status="FAIL" if required else "WARN",
        message=(
            f"Module '{module_name}' is missing"
            if required
            else f"Optional module '{module_name}' is missing"
        ),
        detail={"module": module_name, "required": bool(required)},
    )


def _check_datasets_runtime_compat(required: bool = False) -> CheckResult:
    """
    Validate datasets symbols that modelscope-dependent runtime paths rely on.

    We specifically probe:
    - datasets.load.ALL_ALLOWED_EXTENSIONS
    - datasets.LargeList
    """
    try:
        datasets_mod = importlib.import_module("datasets")
        load_mod = importlib.import_module("datasets.load")
    except Exception as exc:
        return CheckResult(
            name="module:datasets_runtime_compat",
            status="FAIL" if required else "WARN",
            message="datasets runtime probe failed",
            detail={"required": bool(required), "error": str(exc)},
        )

    has_allowed_ext = hasattr(load_mod, "ALL_ALLOWED_EXTENSIONS")
    has_largelist = hasattr(datasets_mod, "LargeList")
    ok = bool(has_allowed_ext and has_largelist)
    version = str(getattr(datasets_mod, "__version__", "unknown"))

    if ok:
        return CheckResult(
            name="module:datasets_runtime_compat",
            status="PASS",
            message=f"datasets runtime symbols are compatible (version={version})",
            detail={
                "version": version,
                "ALL_ALLOWED_EXTENSIONS": bool(has_allowed_ext),
                "LargeList": bool(has_largelist),
            },
        )

    return CheckResult(
        name="module:datasets_runtime_compat",
        status="FAIL" if required else "WARN",
        message=(
            "datasets runtime symbols are incomplete"
            if required
            else "datasets runtime symbols are incomplete (optional path may fail)"
        ),
        detail={
            "version": version,
            "ALL_ALLOWED_EXTENSIONS": bool(has_allowed_ext),
            "LargeList": bool(has_largelist),
            "required": bool(required),
            "hint": "Install a compatible datasets version, e.g. datasets>=2.21.0,<3",
        },
    )


def _check_command(command: str, required: bool = True) -> CheckResult:
    path = shutil.which(str(command).strip())
    if path:
        return CheckResult(
            name=f"command:{command}",
            status="PASS",
            message=f"Command '{command}' found at {path}",
            detail={"command": command, "path": path},
        )
    return CheckResult(
        name=f"command:{command}",
        status="FAIL" if required else "WARN",
        message=(
            f"Command '{command}' is not found"
            if required
            else f"Optional command '{command}' is not found"
        ),
        detail={"command": command, "required": bool(required)},
    )


def _check_agent_browser_local_runtime() -> CheckResult:
    root = Path(__file__).resolve().parents[2]
    default_dir = root / "third_party" / "agent-browser"
    if not default_dir.exists():
        default_dir = root / "demo" / "agent-browser"
    configured_dir = str(os.getenv("AGENT_BROWSER_PROJECT_DIR", str(default_dir))).strip()
    local_dir = Path(configured_dir).expanduser()
    local_bin = local_dir / "bin" / "agent-browser.js"
    local_ready = local_bin.exists() and shutil.which("node")
    global_ready = shutil.which("agent-browser")

    if local_ready:
        return CheckResult(
            name="command:agent-browser-local",
            status="PASS",
            message=f"Local agent-browser runtime is available at {local_bin}",
            detail={"project_dir": str(local_dir), "bin": str(local_bin)},
        )
    if global_ready:
        return CheckResult(
            name="command:agent-browser-local",
            status="WARN",
            message="Local agent-browser runtime missing; global command is available",
            detail={"global_path": str(global_ready), "project_dir": str(local_dir), "bin": str(local_bin)},
        )
    return CheckResult(
        name="command:agent-browser-local",
        status="WARN",
        message="agent-browser runtime not found (local/global). Web skill fallback may occur.",
        detail={
            "project_dir": str(local_dir),
            "bin": str(local_bin),
            "setup_hint": "Run scripts/setup_agent_browser_local.sh",
        },
    )


def _check_writable_dir(path: str) -> CheckResult:
    target = str(path).strip() or "."
    try:
        os.makedirs(target, exist_ok=True)
        probe = os.path.join(target, ".preflight_write_probe")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
    except Exception as exc:
        return CheckResult(
            name=f"writable:{target}",
            status="FAIL",
            message=f"Directory '{target}' is not writable",
            detail={"path": target, "error": str(exc)},
        )
    return CheckResult(
        name=f"writable:{target}",
        status="PASS",
        message=f"Directory '{target}' is writable",
        detail={"path": target},
    )


def _parse_plugin_spec(spec: str) -> tuple[str, str] | None:
    raw = str(spec or "").strip()
    if not raw or ":" not in raw:
        return None
    module_name, factory_name = raw.split(":", 1)
    module_name = module_name.strip()
    factory_name = factory_name.strip()
    if not module_name or not factory_name:
        return None
    return module_name, factory_name


def _check_vector_backend(backend: str, plugin_spec: str | None) -> list[CheckResult]:
    normalized = str(backend or "memory").strip().lower() or "memory"
    memory_aliases = {"memory", "in_memory", "default"}
    if normalized in memory_aliases:
        return [
            CheckResult(
                name="vector_backend",
                status="PASS",
                message=f"Blueprint vector backend '{normalized}' is enabled",
                detail={"backend": normalized},
            )
        ]

    if normalized != "custom":
        return [
            CheckResult(
                name="vector_backend",
                status="FAIL",
                message=f"Unsupported blueprint vector backend '{normalized}'",
                detail={"backend": normalized},
            )
        ]

    parsed = _parse_plugin_spec(str(plugin_spec or ""))
    if parsed is None:
        return [
            CheckResult(
                name="vector_backend",
                status="FAIL",
                message="Custom vector backend requires plugin '<module>:<factory>'",
                detail={"backend": normalized, "plugin": plugin_spec},
            )
        ]

    module_name, factory_name = parsed
    results: list[CheckResult] = [
        CheckResult(
            name="vector_backend",
            status="PASS",
            message="Custom vector backend selected",
            detail={"backend": normalized, "plugin": plugin_spec},
        )
    ]
    try:
        module = importlib.import_module(module_name)
        factory = getattr(module, factory_name)
        if not callable(factory):
            raise TypeError("factory is not callable")
    except Exception as exc:
        results.append(
            CheckResult(
                name="vector_backend_plugin",
                status="FAIL",
                message="Unable to load vector backend plugin",
                detail={
                    "plugin": plugin_spec,
                    "module": module_name,
                    "factory": factory_name,
                    "error": str(exc),
                },
            )
        )
        return results

    results.append(
        CheckResult(
            name="vector_backend_plugin",
            status="PASS",
            message="Vector backend plugin is importable",
            detail={"plugin": plugin_spec},
        )
    )
    return results


def run_preflight(
    *,
    log_root: str = "logs",
    screenshot_dir: str = "screenshot",
    temp_dir: str = "temp",
    require_adb: bool = False,
    require_perception_stack: bool = False,
    blueprint_vector_backend: str | None = None,
    blueprint_vector_plugin: str | None = None,
) -> dict[str, Any]:
    backend = str(
        blueprint_vector_backend
        if blueprint_vector_backend is not None
        else os.getenv("GUIAGENT_BLUEPRINT_VECTOR_BACKEND", "memory")
    ).strip()
    plugin = (
        str(blueprint_vector_plugin).strip()
        if blueprint_vector_plugin is not None
        else str(os.getenv("GUIAGENT_BLUEPRINT_VECTOR_PLUGIN", "")).strip()
    )
    checks: list[CheckResult] = []
    has_modelscope = _module_available("modelscope")
    checks.append(_check_python_version())
    checks.append(_check_module("torch", required=True))
    checks.append(_check_module("transformers", required=False))
    checks.append(_check_module("modelscope", required=False))
    checks.append(_check_datasets_runtime_compat(required=bool(has_modelscope)))

    if require_perception_stack:
        checks.append(_check_module("opencv-python", required=False))
        checks.append(_check_module("PIL", required=False))

    checks.append(_check_command("adb", required=require_adb))
    checks.append(_check_agent_browser_local_runtime())
    checks.append(_check_writable_dir(log_root))
    checks.append(_check_writable_dir(screenshot_dir))
    checks.append(_check_writable_dir(temp_dir))
    checks.extend(_check_vector_backend(backend=backend, plugin_spec=plugin))

    totals = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for item in checks:
        totals[_status(item.status)] += 1

    overall = "PASS"
    if totals["FAIL"] > 0:
        overall = "FAIL"
    elif totals["WARN"] > 0:
        overall = "WARN"
    return {
        "overall_status": overall,
        "totals": totals,
        "checks": [item.to_dict() for item in checks],
    }
