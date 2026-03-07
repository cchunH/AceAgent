from typing import Any

from guiagent_v2.intent_contract import ExecutionRequest


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _resolve_transform(topology_result: dict[str, Any] | None) -> dict[str, float]:
    topology_result = topology_result or {}
    if "scale_x" in topology_result and "scale_y" in topology_result:
        return {
            "scale_x": float(topology_result.get("scale_x", 1.0)),
            "scale_y": float(topology_result.get("scale_y", 1.0)),
            "offset_x": float(topology_result.get("offset_x", 0.0)),
            "offset_y": float(topology_result.get("offset_y", 0.0)),
        }

    ref = topology_result.get("reference_screen", {}) or {}
    tgt = topology_result.get("target_screen", {}) or {}
    ref_w = max(1, _safe_int(ref.get("width"), 1080))
    ref_h = max(1, _safe_int(ref.get("height"), 2340))
    tgt_w = max(1, _safe_int(tgt.get("width"), ref_w))
    tgt_h = max(1, _safe_int(tgt.get("height"), ref_h))
    return {
        "scale_x": tgt_w / ref_w,
        "scale_y": tgt_h / ref_h,
        "offset_x": 0.0,
        "offset_y": 0.0,
    }


def _project_point(x: Any, y: Any, transform: dict[str, float]) -> tuple[int, int]:
    px = int(round(float(x) * transform["scale_x"] + transform["offset_x"]))
    py = int(round(float(y) * transform["scale_y"] + transform["offset_y"]))
    return px, py


def project_action(
    request: ExecutionRequest,
    topology_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project action coordinates from reference space to current screen space."""
    projected = {
        "name": request.action.get("name"),
        "arguments": dict(request.action.get("arguments", {})),
    }
    action_name = str(projected["name"] or "").lower()
    args = projected["arguments"]
    transform = _resolve_transform(topology_result)

    if action_name in {"tap", "long_press"} and "x" in args and "y" in args:
        x, y = _project_point(args["x"], args["y"], transform)
        args["x"] = x
        args["y"] = y
    elif action_name == "swipe":
        needed = ("x1", "y1", "x2", "y2")
        if all(k in args for k in needed):
            x1, y1 = _project_point(args["x1"], args["y1"], transform)
            x2, y2 = _project_point(args["x2"], args["y2"], transform)
            args.update({"x1": x1, "y1": y1, "x2": x2, "y2": y2})

    if topology_result:
        projected["topology_confidence"] = topology_result.get("confidence")
        projected["projection"] = {
            "scale_x": transform["scale_x"],
            "scale_y": transform["scale_y"],
            "offset_x": transform["offset_x"],
            "offset_y": transform["offset_y"],
        }
    return projected
