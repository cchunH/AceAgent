from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from guiagent_v2.blueprint_hub import BlueprintRepository
from .metrics import compute_metrics_from_jsonl


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_runtime_summary(
    log_dir: str,
    event_log_path: str,
    blueprint_repo: BlueprintRepository | None = None,
) -> dict[str, Any]:
    metrics = compute_metrics_from_jsonl(event_log_path)
    summary = {
        "generated_at": _utc_now_iso(),
        "event_log": event_log_path,
        "metrics": metrics,
        "blueprint_count": len(blueprint_repo.list_blueprints()) if blueprint_repo else 0,
    }

    out_path = os.path.join(log_dir, "runtime_summary.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return {"summary_path": out_path, "summary": summary}

