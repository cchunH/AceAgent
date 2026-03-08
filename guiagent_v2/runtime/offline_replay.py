from __future__ import annotations

import json
from statistics import median
from typing import Any

from guiagent_v2.blueprint_hub import BlueprintRepository
from guiagent_v2.intent_contract import map_legacy_action_to_request
from .blueprint_sync import upsert_blueprint_from_observation
from .replay_quality import score_replay_sample


def _load_steps(steps_path: str) -> list[dict[str, Any]]:
    with open(steps_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, list):
        return []
    return [dict(item) for item in payload if isinstance(item, dict)]


def rebuild_blueprints_from_steps(
    steps_path: str,
    blueprints_path: str,
    app_state: str = "global:DEFAULT",
    min_quality_score: float = 0.45,
) -> dict[str, Any]:
    """Offline replay: rebuild blueprints from legacy steps.json."""
    steps = _load_steps(steps_path)
    repo = BlueprintRepository(blueprints_path)

    perception_by_step: dict[int, list[dict[str, Any]]] = {}
    action_by_step: dict[int, dict[str, Any]] = {}
    screen_width = 1080
    screen_height = 2340

    for step in steps:
        step_id = int(step.get("step", 0) or 0)
        op = str(step.get("operation", ""))
        if op == "perception":
            perception_by_step[step_id] = list(step.get("perception_infos", []))
        elif op == "action":
            action_by_step[step_id] = dict(step)
        elif op == "init":
            init_pool = dict(step.get("init_info_pool", {}) or {})
            try:
                screen_width = int(init_pool.get("width", screen_width))
                screen_height = int(init_pool.get("height", screen_height))
            except Exception:
                pass

    rebuilt = 0
    skipped = 0
    low_quality_skipped = 0
    quality_scores: list[float] = []
    for step in steps:
        if str(step.get("operation", "")) != "action_reflection":
            continue
        step_id = int(step.get("step", 0) or 0)
        action_step = action_by_step.get(step_id, {})
        action_obj = action_step.get("action_object")
        if not isinstance(action_obj, dict):
            skipped += 1
            continue
        request = map_legacy_action_to_request(action_obj)
        outcome = str(step.get("outcome", "")).upper().strip()
        passed = "A" in outcome
        if passed:
            reason_code = "STATE_TRANSITION_OK"
        elif "B" in outcome:
            reason_code = "POST_CHECK_FAILED"
        elif "C" in outcome:
            reason_code = "ASSERTION_MISMATCH"
        else:
            reason_code = "UNKNOWN_ERROR"
        post_check = {"passed": passed, "reason_code": reason_code}

        quality = score_replay_sample(
            perception_infos_pre=perception_by_step.get(step_id, []),
            perception_infos_post=perception_by_step.get(step_id + 1, []),
            screen_width=screen_width,
            screen_height=screen_height,
            action_outcome="A" if passed else ("B" if "B" in outcome else "C"),
            post_check_result=post_check,
            min_score=float(min_quality_score),
        )
        quality_scores.append(float(quality.get("score", 0.0)))
        if not bool(quality.get("accepted", False)):
            low_quality_skipped += 1
            continue

        upsert_blueprint_from_observation(
            repo=repo,
            intent_key=request.intent_key,
            screen_width=screen_width,
            screen_height=screen_height,
            perception_infos_pre=perception_by_step.get(step_id, []),
            perception_infos_post=perception_by_step.get(step_id + 1, []),
            action_outcome="A" if passed else ("B" if "B" in outcome else "C"),
            post_check_result=post_check,
            app_state=app_state,
        )
        rebuilt += 1

    quality_p50 = float(median(quality_scores)) if quality_scores else 0.0
    return {
        "status": "SUCCESS",
        "steps_path": steps_path,
        "blueprints_path": blueprints_path,
        "rebuilt_count": rebuilt,
        "skipped_count": skipped,
        "low_quality_skipped_count": low_quality_skipped,
        "min_quality_score": float(min_quality_score),
        "replay_quality_score_p50": round(quality_p50, 4),
        "total_blueprints": len(repo.list_blueprints()),
    }
