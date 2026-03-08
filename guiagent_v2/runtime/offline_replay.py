from __future__ import annotations

import json
from typing import Any

from guiagent_v2.blueprint_hub import BlueprintRepository
from guiagent_v2.intent_contract import map_legacy_action_to_request
from .blueprint_sync import upsert_blueprint_from_observation


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

        upsert_blueprint_from_observation(
            repo=repo,
            intent_key=request.intent_key,
            screen_width=screen_width,
            screen_height=screen_height,
            perception_infos_pre=perception_by_step.get(step_id, []),
            perception_infos_post=perception_by_step.get(step_id + 1, []),
            action_outcome="A" if passed else ("B" if "B" in outcome else "C"),
            post_check_result={"passed": passed, "reason_code": reason_code},
            app_state=app_state,
        )
        rebuilt += 1

    return {
        "status": "SUCCESS",
        "steps_path": steps_path,
        "blueprints_path": blueprints_path,
        "rebuilt_count": rebuilt,
        "skipped_count": skipped,
        "total_blueprints": len(repo.list_blueprints()),
    }
