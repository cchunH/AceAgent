from typing import Any

from guiagent_v2.intent_contract import ExecutionRequest


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _resolve_transform(topology_result: dict[str, Any] | None) -> dict[str, Any]:
    topology_result = topology_result or {}
    affine_norm = topology_result.get("affine_norm")
    if isinstance(affine_norm, dict):
        return {
            "mode": "affine_norm",
            "a": float(affine_norm.get("a", 1.0)),
            "b": float(affine_norm.get("b", 0.0)),
            "c": float(affine_norm.get("c", 0.0)),
            "d": float(affine_norm.get("d", 1.0)),
            "tx": float(affine_norm.get("tx", 0.0)),
            "ty": float(affine_norm.get("ty", 0.0)),
        }

    if "scale_x" in topology_result and "scale_y" in topology_result:
        return {
            "mode": "scale",
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
        "mode": "scale",
        "scale_x": tgt_w / ref_w,
        "scale_y": tgt_h / ref_h,
        "offset_x": 0.0,
        "offset_y": 0.0,
    }


def _project_point(x: Any, y: Any, transform: dict[str, Any]) -> tuple[int, int]:
    px = int(round(float(x) * transform["scale_x"] + transform["offset_x"]))
    py = int(round(float(y) * transform["scale_y"] + transform["offset_y"]))
    return px, py


def _project_point_affine_norm(
    x: Any,
    y: Any,
    transform: dict[str, Any],
    reference_screen: dict[str, Any],
    target_screen: dict[str, Any],
) -> tuple[int, int]:
    ref_w = max(1, _safe_int(reference_screen.get("width"), 1080))
    ref_h = max(1, _safe_int(reference_screen.get("height"), 2340))
    tgt_w = max(1, _safe_int(target_screen.get("width"), ref_w))
    tgt_h = max(1, _safe_int(target_screen.get("height"), ref_h))

    xn = float(x) / float(ref_w)
    yn = float(y) / float(ref_h)
    un = (transform["a"] * xn) + (transform["b"] * yn) + transform["tx"]
    vn = (transform["c"] * xn) + (transform["d"] * yn) + transform["ty"]
    px = int(round(un * tgt_w))
    py = int(round(vn * tgt_h))
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
    transform_mode = str(transform.get("mode", "scale"))
    reference_screen = dict((topology_result or {}).get("reference_screen", {}) or {})
    target_screen = dict((topology_result or {}).get("target_screen", {}) or {})

    if action_name in {"tap", "long_press"} and "x" in args and "y" in args:
        if transform_mode == "affine_norm":
            x, y = _project_point_affine_norm(args["x"], args["y"], transform, reference_screen, target_screen)
        else:
            x, y = _project_point(args["x"], args["y"], transform)
        args["x"] = x
        args["y"] = y
    elif action_name == "swipe":
        needed = ("x1", "y1", "x2", "y2")
        if all(k in args for k in needed):
            if transform_mode == "affine_norm":
                x1, y1 = _project_point_affine_norm(args["x1"], args["y1"], transform, reference_screen, target_screen)
                x2, y2 = _project_point_affine_norm(args["x2"], args["y2"], transform, reference_screen, target_screen)
            else:
                x1, y1 = _project_point(args["x1"], args["y1"], transform)
                x2, y2 = _project_point(args["x2"], args["y2"], transform)
            args.update({"x1": x1, "y1": y1, "x2": x2, "y2": y2})

    if topology_result:
        projected["topology_confidence"] = topology_result.get("confidence")
        if transform_mode == "affine_norm":
            projected["projection"] = {
                "mode": "affine_norm",
                "a": transform["a"],
                "b": transform["b"],
                "c": transform["c"],
                "d": transform["d"],
                "tx": transform["tx"],
                "ty": transform["ty"],
            }
        else:
            projected["projection"] = {
                "mode": "scale",
                "scale_x": transform["scale_x"],
                "scale_y": transform["scale_y"],
                "offset_x": transform["offset_x"],
                "offset_y": transform["offset_y"],
            }
    return projected
