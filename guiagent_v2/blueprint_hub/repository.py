from __future__ import annotations

import json
import os
from threading import Lock
from typing import Any, Callable

from .patch_model import Blueprint, BlueprintPatch
from guiagent_v2.state_engine import build_blueprint_match_index, match_blueprint_fast
from guiagent_v2.retrieval import (
    InMemoryVectorIndex,
    VectorIndexAdapter,
    deterministic_text_embedding,
)


def _make_key(intent_key: str, app_state: str) -> str:
    return f"{app_state}::{intent_key}"


class BlueprintRepository:
    """Local JSON-backed blueprint repository (single-file MVP)."""

    def __init__(
        self,
        file_path: str,
        vector_index: VectorIndexAdapter | None = None,
        embedding_fn: Callable[[str, int], list[float]] | None = None,
        embedding_dim: int = 32,
    ):
        self.file_path = file_path
        self._lock = Lock()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        self._store: dict[str, dict[str, Any]] = {}
        self._match_index_cache: dict[str, list[dict[str, Any]]] | None = None
        self._vector_index = vector_index or InMemoryVectorIndex()
        self._embedding_fn = embedding_fn or deterministic_text_embedding
        self._embedding_dim = max(1, int(embedding_dim))
        self._vector_backend_source = "vector_mock" if vector_index is None else "vector_custom"
        self._vector_index_ready = False
        self._load()

    def configure_vector_backend(
        self,
        *,
        vector_index: VectorIndexAdapter | None = None,
        embedding_fn: Callable[[str, int], list[float]] | None = None,
        embedding_dim: int | None = None,
        source: str | None = None,
        rebuild: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            if vector_index is not None:
                self._vector_index = vector_index
                self._vector_backend_source = str(source or "vector_custom")
            if embedding_fn is not None:
                self._embedding_fn = embedding_fn
            if embedding_dim is not None:
                self._embedding_dim = max(1, int(embedding_dim))
            if source is not None and vector_index is None:
                self._vector_backend_source = str(source)
            self._vector_index_ready = False
        if rebuild:
            return self.rebuild_vector_index()
        return self.get_vector_backend_info()

    def get_vector_backend_info(self) -> dict[str, Any]:
        with self._lock:
            return {
                "backend_type": self._vector_index.__class__.__name__,
                "embedding_dim": int(self._embedding_dim),
                "source": str(self._vector_backend_source),
                "ready": bool(self._vector_index_ready),
            }

    def _encode_text(self, text: str) -> list[float]:
        return self._embedding_fn(str(text or ""), self._embedding_dim)

    def _load(self) -> None:
        if not os.path.exists(self.file_path):
            self._store = {}
            self._match_index_cache = None
            self._vector_index_ready = False
            return
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self._store = payload if isinstance(payload, dict) else {}
        except Exception:
            self._store = {}
        self._match_index_cache = None
        self._vector_index_ready = False

    def _save(self) -> None:
        tmp = f"{self.file_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._store, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.file_path)
        self._match_index_cache = None
        self._vector_index_ready = False

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

    def _compose_vector_text(self, blueprint: dict[str, Any]) -> str:
        intent_key = str(blueprint.get("intent_key", "")).strip()
        anchors = blueprint.get("anchors", [])
        anchor_texts: list[str] = []
        if isinstance(anchors, list):
            for item in anchors:
                if not isinstance(item, dict):
                    continue
                text = str(item.get("text", "")).strip()
                if text:
                    anchor_texts.append(text)
        post_expectations = blueprint.get("post_expectations", [])
        exp_values = []
        if isinstance(post_expectations, list):
            exp_values = [str(item).strip() for item in post_expectations if str(item).strip()]
        parts = [intent_key]
        if anchor_texts:
            parts.append("anchors:" + " ".join(anchor_texts[:8]))
        if exp_values:
            parts.append("expect:" + " ".join(exp_values[:8]))
        return " | ".join([p for p in parts if p])

    def rebuild_vector_index(self, app_state: str | None = None) -> dict[str, Any]:
        with self._lock:
            snapshot = [dict(v) for v in self._store.values()]
        target_state = str(app_state).strip() if app_state is not None else None

        self._vector_index.clear()
        indexed = 0
        for item in snapshot:
            state = str(item.get("app_state", "global:DEFAULT"))
            if target_state and state != target_state:
                continue
            intent_key = str(item.get("intent_key", "")).strip()
            if not intent_key:
                continue
            item_id = _make_key(intent_key, state)
            vector_text = self._compose_vector_text(item)
            vector = self._encode_text(vector_text)
            self._vector_index.upsert(
                item_id,
                vector,
                metadata={
                    "intent_key": intent_key,
                    "app_state": state,
                    "vector_text": vector_text,
                },
            )
            indexed += 1

        with self._lock:
            self._vector_index_ready = True
        return {
            "status": "SUCCESS",
            "indexed_count": indexed,
            "app_state": target_state or "ALL",
        }

    def match_by_vector(
        self,
        query_text: str,
        app_state: str = "global:DEFAULT",
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        if not str(query_text or "").strip():
            return []
        with self._lock:
            ready = bool(self._vector_index_ready)
        if not ready:
            self.rebuild_vector_index()

        state = str(app_state).strip() or "global:DEFAULT"
        query_vector = self._encode_text(str(query_text))
        hits = self._vector_index.search(query_vector, top_k=max(1, int(top_k)) * 4)

        rows: list[dict[str, Any]] = []
        for hit in hits:
            metadata = dict(hit.metadata or {})
            if str(metadata.get("app_state", "")) != state:
                continue
            rows.append(
                {
                    "intent_key": str(metadata.get("intent_key", "")),
                    "app_state": str(metadata.get("app_state", state)),
                    "score": float(hit.score),
                    "item_id": hit.item_id,
                    "source": str(self._vector_backend_source),
                }
            )
            if len(rows) >= max(1, int(top_k)):
                break
        return rows
