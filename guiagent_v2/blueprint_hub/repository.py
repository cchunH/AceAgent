from __future__ import annotations

import json
import os
from threading import Lock
from typing import Any

from .patch_model import Blueprint, BlueprintPatch
from guiagent_v2.state_engine import build_blueprint_match_index, match_blueprint_fast


def _make_key(intent_key: str, app_state: str) -> str:
    return f"{app_state}::{intent_key}"


class BlueprintRepository:
    """Local JSON-backed blueprint repository (single-file MVP)."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self._lock = Lock()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        self._store: dict[str, dict[str, Any]] = {}
        self._match_index_cache: dict[str, list[dict[str, Any]]] | None = None
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.file_path):
            self._store = {}
            self._match_index_cache = None
            return
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self._store = payload if isinstance(payload, dict) else {}
        except Exception:
            self._store = {}
        self._match_index_cache = None

    def _save(self) -> None:
        tmp = f"{self.file_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._store, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.file_path)
        self._match_index_cache = None

    def get_blueprint(self, intent_key: str, app_state: str = "global:DEFAULT") -> dict[str, Any] | None:
        with self._lock:
            item = self._store.get(_make_key(intent_key, app_state))
            if item is None:
                return None
            return dict(item)

    def save_blueprint(self, blueprint: Blueprint | dict[str, Any]) -> None:
        if isinstance(blueprint, Blueprint):
            item = blueprint.to_dict()
        else:
            item = dict(blueprint)
        intent_key = str(item.get("intent_key", "")).strip()
        app_state = str(item.get("app_state", "global:DEFAULT"))
        if not intent_key:
            raise ValueError("intent_key is required for blueprint")
        with self._lock:
            self._store[_make_key(intent_key, app_state)] = item
            self._save()

    def apply_patch(self, patch: BlueprintPatch | dict[str, Any]) -> dict[str, Any]:
        patch_obj = patch if isinstance(patch, BlueprintPatch) else BlueprintPatch(**patch)
        key = _make_key(patch_obj.target_intent_key, patch_obj.target_state)
        with self._lock:
            if key not in self._store:
                return {"status": "FAILED", "reason_code": "BLUEPRINT_NOT_FOUND"}
            item = dict(self._store[key])
            delta = patch_obj.delta or {}
            for k, v in delta.items():
                item[k] = v
            item["version"] = patch_obj.version
            self._store[key] = item
            self._save()
        return {
            "status": "SUCCESS",
            "patch_id": patch_obj.patch_id,
            "target_intent_key": patch_obj.target_intent_key,
            "target_state": patch_obj.target_state,
            "version": patch_obj.version,
        }

    def list_blueprints(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(v) for v in self._store.values()]

    def build_match_index(
        self,
        app_state: str | None = None,
        force_rebuild: bool = False,
    ) -> dict[str, list[dict[str, Any]]]:
        with self._lock:
            needs_rebuild = self._match_index_cache is None or force_rebuild
            snapshot = [dict(v) for v in self._store.values()] if needs_rebuild else None
            cached = dict(self._match_index_cache or {})

        if needs_rebuild:
            rebuilt = build_blueprint_match_index(snapshot or [])
            with self._lock:
                self._match_index_cache = rebuilt
                cached = dict(rebuilt)

        if app_state is None:
            return cached
        state = str(app_state).strip() or "global:DEFAULT"
        return {state: list(cached.get(state, []))}

    def match_by_skeleton(
        self,
        observed_skeleton: dict[str, Any] | None,
        app_state: str = "global:DEFAULT",
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        index = self.build_match_index(app_state=app_state, force_rebuild=False)
        return match_blueprint_fast(
            observed_skeleton=observed_skeleton,
            index=index,
            app_state=app_state,
            top_k=top_k,
        )
