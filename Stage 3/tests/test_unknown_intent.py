"""Test unknown intent handling."""
import os
from app.services import llm_service


def test_unknown_intent_no_backend_operations(client, monkeypatch):
    """Verify unknown intents return clean response without DB operations."""
    
    # Mock the planner to return unknown type
    async def fake_plan_unknown(message: str):
        return {
            "actions": [{
                "type": "unknown",
                "action": "none",
                "params": {}
            }]
        }
    
    monkeypatch.setattr(llm_service, "plan_actions", fake_plan_unknown)
    
    AGENT_NAME = os.getenv("A2A_AGENT_NAME", "Raven")
    
    payload = {
        "jsonrpc": "2.0",
        "id": "unknown-test",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": "What's the weather like?"}]
            },
            "user_id": "u_unknown_test",
            "configuration": {"blocking": True}
        }
    }
    
    resp = client.post(f"/a2a/agent/{AGENT_NAME}", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    
    # Check response structure
    assert body.get("result") and isinstance(body.get("result"), dict)
    result = body["result"]
    assert result.get("kind") == "task"
    
    # Should be completed (blocking mode)
    status = result.get("status")
    assert status and status.get("state") == "completed"
    
    # Check the message indicates it's unclassifiable
    message = status.get("message", {})
    parts = message.get("parts", [])
    assert len(parts) > 0
    
    # Should have text indicating couldn't classify
    text_parts = [p.get("text", "") for p in parts if p.get("kind") == "text"]
    response_text = " ".join(text_parts)
    assert "couldn't determine" in response_text.lower() or "more specific" in response_text.lower()
    
    # Verify no database operations in metadata (soft error recorded)
    artifacts = result.get("artifacts", [])
    exec_results = [a for a in artifacts if a.get("name") == "ExecutionResults"]
    
    if exec_results:
        parts = exec_results[0].get("parts", [])
        data_parts = [p.get("data", {}) for p in parts if p.get("kind") == "data"]
        if data_parts:
            data = data_parts[0]
            # No executed actions should be present
            executed = data.get("executed", [])
            assert len(executed) == 0, f"Expected no executed actions for unknown type, got: {executed}"
            
            # Should have error entry indicating unknown type
            errors = data.get("errors", [])
            assert len(errors) > 0, "Expected error entry for unknown type"
            assert any(e.get("type") == "unknown" for e in errors)
