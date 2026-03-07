from typing import Any

from guiagent_v2.intent_contract import ExecutionRequest


def project_action(
    request: ExecutionRequest,
    topology_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Phase-1 placeholder for affine projection.

    Current behavior keeps legacy absolute coordinates unchanged while
    preserving the projection interface for later topology-based mapping.
    """
    projected = {
        "name": request.action.get("name"),
        "arguments": dict(request.action.get("arguments", {})),
    }
    if topology_result:
        projected["topology_confidence"] = topology_result.get("confidence")
    return projected

