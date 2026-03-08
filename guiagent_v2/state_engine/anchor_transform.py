from __future__ import annotations

from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _anchor_xy(anchor: dict[str, Any]) -> tuple[float, float]:
    bbox = dict(anchor.get("norm_bbox", {}) or {})
    return _safe_float(bbox.get("x", 0.0), 0.0), _safe_float(bbox.get("y", 0.0), 0.0)


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float] | None:
    n = len(matrix)
    if n <= 0 or any(len(row) != n for row in matrix) or len(vector) != n:
        return None

    a = [list(row) for row in matrix]
    b = list(vector)

    for col in range(n):
        pivot = col
        for row in range(col + 1, n):
            if abs(a[row][col]) > abs(a[pivot][col]):
                pivot = row
        if abs(a[pivot][col]) < 1e-9:
            return None
        if pivot != col:
            a[col], a[pivot] = a[pivot], a[col]
            b[col], b[pivot] = b[pivot], b[col]

        denom = a[col][col]
        for k in range(col, n):
            a[col][k] /= denom
        b[col] /= denom

        for row in range(n):
            if row == col:
                continue
            factor = a[row][col]
            if abs(factor) < 1e-12:
                continue
            for k in range(col, n):
                a[row][k] -= factor * a[col][k]
            b[row] -= factor * b[col]

    return b


def _least_square_affine(pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> tuple[dict[str, float], float] | None:
    if len(pairs) < 3:
        return None
    ata = [[0.0 for _ in range(6)] for _ in range(6)]
    atb = [0.0 for _ in range(6)]

    for exp, obs in pairs:
        x, y = _anchor_xy(exp)
        u, v = _anchor_xy(obs)
        rows = (
            ([x, y, 1.0, 0.0, 0.0, 0.0], u),
            ([0.0, 0.0, 0.0, x, y, 1.0], v),
        )
        for row_vec, target in rows:
            for i in range(6):
                atb[i] += row_vec[i] * target
                for j in range(6):
                    ata[i][j] += row_vec[i] * row_vec[j]

    solved = _solve_linear_system(ata, atb)
    if solved is None:
        return None

    affine = {
        "a": float(solved[0]),
        "b": float(solved[1]),
        "tx": float(solved[2]),
        "c": float(solved[3]),
        "d": float(solved[4]),
        "ty": float(solved[5]),
    }
    error = _fit_error(affine, pairs)
    return affine, error


def _scale_translate_affine(
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
) -> tuple[dict[str, float], float]:
    exp_xs: list[float] = []
    exp_ys: list[float] = []
    obs_xs: list[float] = []
    obs_ys: list[float] = []
    for exp, obs in pairs:
        ex, ey = _anchor_xy(exp)
        ox, oy = _anchor_xy(obs)
        exp_xs.append(ex)
        exp_ys.append(ey)
        obs_xs.append(ox)
        obs_ys.append(oy)

    if not exp_xs:
        return {"a": 1.0, "b": 0.0, "tx": 0.0, "c": 0.0, "d": 1.0, "ty": 0.0}, 0.0

    exp_span_x = max(exp_xs) - min(exp_xs)
    exp_span_y = max(exp_ys) - min(exp_ys)
    obs_span_x = max(obs_xs) - min(obs_xs)
    obs_span_y = max(obs_ys) - min(obs_ys)

    scale_x = 1.0 if exp_span_x < 1e-6 else obs_span_x / max(exp_span_x, 1e-6)
    scale_y = 1.0 if exp_span_y < 1e-6 else obs_span_y / max(exp_span_y, 1e-6)
    scale_x = max(0.2, min(5.0, float(scale_x)))
    scale_y = max(0.2, min(5.0, float(scale_y)))

    tx_values: list[float] = []
    ty_values: list[float] = []
    for exp, obs in pairs:
        ex, ey = _anchor_xy(exp)
        ox, oy = _anchor_xy(obs)
        tx_values.append(ox - (scale_x * ex))
        ty_values.append(oy - (scale_y * ey))
    tx = sum(tx_values) / max(1, len(tx_values))
    ty = sum(ty_values) / max(1, len(ty_values))

    affine = {
        "a": float(scale_x),
        "b": 0.0,
        "tx": float(tx),
        "c": 0.0,
        "d": float(scale_y),
        "ty": float(ty),
    }
    error = _fit_error(affine, pairs)
    return affine, error


def _fit_error(affine: dict[str, float], pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> float:
    if not pairs:
        return 0.0
    sq_sum = 0.0
    for exp, obs in pairs:
        x, y = _anchor_xy(exp)
        u, v = _anchor_xy(obs)
        pu = affine["a"] * x + affine["b"] * y + affine["tx"]
        pv = affine["c"] * x + affine["d"] * y + affine["ty"]
        du = pu - u
        dv = pv - v
        sq_sum += (du * du) + (dv * dv)
    rmse = (sq_sum / max(1, len(pairs))) ** 0.5
    return float(rmse)


def estimate_anchor_affine(
    matched_pairs: list[tuple[dict[str, Any], dict[str, Any]]],
) -> dict[str, Any]:
    """Estimate normalized affine transform from expected anchors to observed anchors."""
    pairs = [
        (dict(exp), dict(obs))
        for exp, obs in (matched_pairs or [])
        if isinstance(exp, dict) and isinstance(obs, dict)
    ]
    if not pairs:
        return {
            "transform_mode": "identity",
            "affine_norm": {"a": 1.0, "b": 0.0, "tx": 0.0, "c": 0.0, "d": 1.0, "ty": 0.0},
            "transform_fit_error": 0.0,
            "transform_pair_count": 0,
        }

    lsq = _least_square_affine(pairs)
    if lsq is not None:
        affine, error = lsq
        return {
            "transform_mode": "affine6",
            "affine_norm": affine,
            "transform_fit_error": float(error),
            "transform_pair_count": len(pairs),
        }

    affine, error = _scale_translate_affine(pairs)
    return {
        "transform_mode": "scale_translate",
        "affine_norm": affine,
        "transform_fit_error": float(error),
        "transform_pair_count": len(pairs),
    }
