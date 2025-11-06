from typing import Any, Dict, List, Optional, Literal
from uuid import uuid4
import app.models.a2a as a2a_models


def as_message_part(p: Dict[str, Any]) -> a2a_models.MessagePart:
    """Convert dict to MessagePart model."""
    return a2a_models.MessagePart(
        kind=p.get("kind", "text"),
        text=p.get("text"),
        data=p.get("data"),
        file_url=p.get("file_url"),
    )


def build_artifacts(artifacts: Optional[List[Dict[str, Any]]]) -> List[a2a_models.Artifact]:
    """Convert artifact dicts to A2A Artifact models."""
    if not artifacts:
        return []
    
    result = []
    for art in artifacts:
        if isinstance(art, a2a_models.Artifact):
            result.append(art)
        else:
            parts = [as_message_part(p) for p in art.get("parts", [])]
            result.append(a2a_models.Artifact(name=art.get("name", "artifact"), parts=parts))
    return result


def build_task_result(
    request_id: str,
    context_id: str,
    state: Literal["working", "completed", "input-required", "failed"],
    message_text: str,
    artifacts: Optional[List[Dict[str, Any]]] = None,
    history_msgs: Optional[List[a2a_models.A2AMessage]] = None,
) -> Dict[str, Any]:
    """Build A2A-compliant TaskResult response."""
    status_msg = a2a_models.A2AMessage(
        role="agent",
        parts=[a2a_models.MessagePart(kind="text", text=message_text)]
    )
    task = a2a_models.TaskResult(
        id=str(uuid4()),
        contextId=context_id,
        status=a2a_models.TaskStatus(state=state, message=status_msg),
        artifacts=build_artifacts(artifacts),
        history=history_msgs or [],
    )
    return {"jsonrpc": "2.0", "id": request_id, "result": task.model_dump()}
