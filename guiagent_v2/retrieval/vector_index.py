from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from threading import Lock
from typing import Iterable


def deterministic_text_embedding(text: str, dim: int = 32) -> list[float]:
    token_pattern = re.compile(r"[a-z0-9_]+|[\u4e00-\u9fff]")
    tokens = token_pattern.findall(str(text or "").lower())
    if not tokens:
        tokens = [str(text or "").strip() or "__empty__"]

    dim_value = max(1, int(dim))
    vec = [0.0 for _ in range(dim_value)]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], byteorder="big", signed=False) % dim_value
        sign = 1.0 if (digest[2] % 2 == 0) else -1.0
        weight = 1.0 + (digest[3] / 255.0) * 0.1
        vec[index] += sign * weight
    return _l2_normalize(vec)


def _l2_normalize(vec: Iterable[float]) -> list[float]:
    values = [float(v) for v in vec]
    norm = math.sqrt(sum(v * v for v in values))
    if norm <= 1e-12:
        return [0.0 for _ in values]
    return [v / norm for v in values]


def _cosine_similarity(v1: list[float], v2: list[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    return sum(a * b for a, b in zip(v1, v2))


@dataclass
class VectorHit:
    item_id: str
    score: float
    metadata: dict

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "score": float(self.score),
            "metadata": dict(self.metadata),
        }


class VectorIndexAdapter:
    def upsert(self, item_id: str, vector: list[float], metadata: dict | None = None) -> None:
        raise NotImplementedError

    def delete(self, item_id: str) -> None:
        raise NotImplementedError

    def search(self, vector: list[float], top_k: int = 3) -> list[VectorHit]:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError


class InMemoryVectorIndex(VectorIndexAdapter):
    def __init__(self):
        self._lock = Lock()
        self._items: dict[str, tuple[list[float], dict]] = {}

    def upsert(self, item_id: str, vector: list[float], metadata: dict | None = None) -> None:
        key = str(item_id or "").strip()
        if not key:
            raise ValueError("item_id is required")
        norm_vector = _l2_normalize(vector)
        with self._lock:
            self._items[key] = (norm_vector, dict(metadata or {}))

    def delete(self, item_id: str) -> None:
        key = str(item_id or "").strip()
        if not key:
            return
        with self._lock:
            self._items.pop(key, None)

    def search(self, vector: list[float], top_k: int = 3) -> list[VectorHit]:
        norm_vector = _l2_normalize(vector)
        k = max(1, int(top_k))
        with self._lock:
            rows = [
                VectorHit(item_id=item_id, score=_cosine_similarity(norm_vector, item_vector), metadata=dict(metadata))
                for item_id, (item_vector, metadata) in self._items.items()
            ]
        rows.sort(key=lambda x: (-x.score, x.item_id))
        return rows[:k]

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
