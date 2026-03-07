from __future__ import annotations

from typing import Any


class ContextCompactor:
    """Keep runtime context bounded and emit compact summaries."""

    def __init__(
        self,
        max_events: int = 30,
        keep_recent: int = 12,
    ):
        self.max_events = max(5, int(max_events))
        self.keep_recent = max(3, int(keep_recent))

    @staticmethod
    def _build_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for event in events:
            et = str(event.get("event_type", "unknown"))
            counts[et] = counts.get(et, 0) + 1
        top_event_types = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:5]
        return {
            "event_type_counts": dict(top_event_types),
            "total_events": len(events),
        }

    def compact(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(events)
        if total <= self.max_events:
            return {
                "applied": False,
                "events": list(events),
                "before_count": total,
                "after_count": total,
                "summary": None,
            }

        keep = min(self.keep_recent, total)
        compacted_events = list(events[-keep:])
        summary = self._build_summary(events[:-keep])
        return {
            "applied": True,
            "events": compacted_events,
            "before_count": total,
            "after_count": len(compacted_events),
            "summary": summary,
            "truncated_count": total - len(compacted_events),
        }
