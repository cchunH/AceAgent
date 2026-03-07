from __future__ import annotations

from typing import Any, Protocol


class WatchdogPlugin(Protocol):
    name: str

    def on_event(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        ...
