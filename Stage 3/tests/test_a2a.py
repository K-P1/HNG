import json
import sys
import os
from fastapi.testclient import TestClient

# Ensure project root is importable during tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
import app.services as services


def test_a2a_reflective_assistant_monkeypatched(monkeypatch):
    client = TestClient(app)

    # Stub the services.process_telex_message to avoid external LLM/DB calls
    def fake_process(user_id, message):
        return {"status": "ok", "message": "Got it — I scheduled your task.", "task_id": 1}

    monkeypatch.setattr(services, "process_telex_message", fake_process)

    import os

    AGENT_NAME = os.getenv("A2A_AGENT_NAME", os.getenv("AGENT_NAME", "reflectiveAssistant"))

    payload = {
        "jsonrpc": "2.0",
        "id": "test-123",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": "Please add buy milk to my todo"}]
            },
            "user_id": "u1"
        }
    }

    resp = client.post(f"/a2a/agent/{AGENT_NAME}", json=payload)
    assert resp.status_code == 200
    body = resp.json()

    # Basic JSON-RPC shape
    assert body.get("jsonrpc") == "2.0"
    assert body.get("id") == "test-123"
    result = body.get("result")
    assert isinstance(result, dict)
    messages = result.get("messages")
    assert isinstance(messages, list) and len(messages) > 0
    first = messages[0]
    assert first.get("role") == "assistant"
    assert "scheduled" in first.get("content")
