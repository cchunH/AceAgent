from __future__ import annotations

import hashlib
import json
from collections import deque
from typing import Any


def _stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class LoopDetector:
    """Detect repeated actions and page stagnation in runtime loops."""

    def __init__(
        self,
        repeat_threshold: int = 3,
        stagnation_threshold: int = 3,
        max_history: int = 32,
    ):
        self.repeat_threshold = max(2, int(repeat_threshold))
        self.stagnation_threshold = max(2, int(stagnation_threshold))
        self._action_history: deque[str] = deque(maxlen=max_history)
        self._page_history: deque[str] = deque(maxlen=max_history)

    @staticmethod
    def build_page_fingerprint(perception_infos: list[dict[str, Any]] | None) -> str:
        infos = perception_infos or []
        items: list[str] = []
        for info in infos:
            text = str(info.get("text", "")).strip().lower()
            if not text:
                continue
            items.append(text)
        items.sort()
        blob = "|".join(items[:20])
        if not blob:
            blob = "__empty_page__"
        return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def _action_signature(action: dict[str, Any] | None) -> str:
        payload = dict(action or {})
        stable = _stable_json(payload)
        return hashlib.sha1(stable.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def _count_trailing_same(history: deque[str], value: str) -> int:
        count = 0
        for item in reversed(history):
            if item != value:
                break
            count += 1
        return count

    def observe(
        self,
        action: dict[str, Any] | None,
        page_fingerprint: str,
    ) -> dict[str, Any]:
        action_sig = self._action_signature(action)
        page_fingerprint = str(page_fingerprint or "").strip() or "__empty_page__"

        self._action_history.append(action_sig)
        self._page_history.append(page_fingerprint)

        repeated_action_count = self._count_trailing_same(self._action_history, action_sig)
        stagnation_steps = self._count_trailing_same(self._page_history, page_fingerprint)

        repeat_score = repeated_action_count / float(self.repeat_threshold)
        stagnation_score = stagnation_steps / float(self.stagnation_threshold)
        loop_score = min(1.0, max(repeat_score, stagnation_score))
        should_warn = (
            repeated_action_count >= self.repeat_threshold
            or stagnation_steps >= self.stagnation_threshold
        )

        return {
            "action_signature": action_sig,
            "page_fingerprint": page_fingerprint,
            "repeated_action_count": repeated_action_count,
            "stagnation_steps": stagnation_steps,
            "loop_score": round(loop_score, 4),
            "should_warn": should_warn,
        }
