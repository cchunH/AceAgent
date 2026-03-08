from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProbeState(str, Enum):
    INIT = "INIT"
    ROUTED = "ROUTED"
    GUARDED = "GUARDED"
    CONFIRM_PENDING = "CONFIRM_PENDING"
    EXECUTING_WEB = "EXECUTING_WEB"
    EXECUTING_MOBILE = "EXECUTING_MOBILE"
    FALLBACK = "FALLBACK"
    VERIFYING = "VERIFYING"
    HANDOVER = "HANDOVER"
    COMPLETED = "COMPLETED"


@dataclass
class StateTransition:
    prev_state: ProbeState
    next_state: ProbeState
    reason: str
    ok: bool

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "prev_state": self.prev_state.value,
            "next_state": self.next_state.value,
            "reason": self.reason,
            "ok": self.ok,
        }


_ALLOWED_TRANSITIONS: dict[ProbeState, set[ProbeState]] = {
    ProbeState.INIT: {ProbeState.ROUTED, ProbeState.HANDOVER, ProbeState.COMPLETED},
    ProbeState.ROUTED: {ProbeState.GUARDED, ProbeState.HANDOVER},
    ProbeState.GUARDED: {
        ProbeState.CONFIRM_PENDING,
        ProbeState.EXECUTING_WEB,
        ProbeState.EXECUTING_MOBILE,
        ProbeState.HANDOVER,
    },
    ProbeState.CONFIRM_PENDING: {
        ProbeState.EXECUTING_WEB,
        ProbeState.EXECUTING_MOBILE,
        ProbeState.HANDOVER,
    },
    ProbeState.EXECUTING_WEB: {ProbeState.FALLBACK, ProbeState.VERIFYING, ProbeState.HANDOVER},
    ProbeState.EXECUTING_MOBILE: {ProbeState.VERIFYING, ProbeState.HANDOVER},
    ProbeState.FALLBACK: {ProbeState.EXECUTING_MOBILE, ProbeState.HANDOVER},
    ProbeState.VERIFYING: {ProbeState.HANDOVER, ProbeState.COMPLETED},
    ProbeState.HANDOVER: {ProbeState.COMPLETED},
    ProbeState.COMPLETED: set(),
}


class ProbeStateMachine:
    def __init__(self, initial_state: ProbeState = ProbeState.INIT):
        self._current = initial_state
        self._history: list[StateTransition] = []

    @property
    def current(self) -> ProbeState:
        return self._current

    @property
    def history(self) -> list[StateTransition]:
        return list(self._history)

    def can_transition(self, next_state: ProbeState) -> bool:
        return next_state in _ALLOWED_TRANSITIONS.get(self._current, set())

    def transition(self, next_state: ProbeState, reason: str) -> StateTransition:
        ok = self.can_transition(next_state)
        prev = self._current
        if ok:
            self._current = next_state
        record = StateTransition(
            prev_state=prev,
            next_state=next_state,
            reason=str(reason or "").strip() or "unspecified",
            ok=ok,
        )
        self._history.append(record)
        return record

