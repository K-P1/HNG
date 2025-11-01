import os
import sys
import time
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app import services
from app import crud
from app import database
import app.routes as routes


def test_a2a_followup_posts_task_list(monkeypatch):
    # Instead of touching the DB, stub crud.get_tasks to return real Task
    # model instances so the follow-up formatting uses real model fields.
    from app.models.models import Task

    user_id = "u_follow"
    t1 = Task(user_id=user_id, description="Finish stage 3")
    t2 = Task(user_id=user_id, description="Restock milk")

    async def fake_get_tasks(uid):
        return [t1, t2] if uid == user_id else []

    monkeypatch.setattr(crud, "get_tasks", fake_get_tasks)

    client = TestClient(app)

    # Avoid external LLM calls in background follow-up
    def fake_plan_actions(message: str):
        return {"actions": [{"type": "list_tasks", "params": {}}]}
    monkeypatch.setattr(services.llm, "plan_actions", fake_plan_actions)

    recorded = []

    async def fake_send_telex(push_url, message, *args, **kwargs):
        # record the call for assertions
        recorded.append((push_url, message))

    # Monkeypatch the send_telex_followup function imported in routes
    monkeypatch.setattr(routes, "send_telex_followup", fake_send_telex)

    AGENT_NAME = os.getenv("A2A_AGENT_NAME", os.getenv("AGENT_NAME", "reflectiveAssistant"))

    payload = {
        "jsonrpc": "2.0",
        "id": "followup-test",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": "Please list my todos"}]
            },
            "user_id": user_id,
            "configuration": {
                "pushNotificationConfig": {"url": "http://example.test/push"}
            }
        }
    }

    resp = client.post(f"/a2a/agent/{AGENT_NAME}", json=payload)
    assert resp.status_code == 200
    body = resp.json()

    # Immediate acknowledgement should be returned
    assert body.get("result") and isinstance(body.get("result"), dict)
    messages = body["result"].get("messages", [])
    assert messages and "I'll compile your pending to-do list" in messages[0]["content"]

    # Wait for the background follow-up to be invoked (give it up to 2s)
    deadline = time.time() + 2.0
    while time.time() < deadline and not recorded:
        time.sleep(0.05)

    assert recorded, "Expected follow-up to be sent via send_telex_followup"
    push_url, message = recorded[0]
    assert push_url == "http://example.test/push"

    # Message should include counts header and both tasks with status
    assert "tasks (total: 2" in message or "tasks (total: 2, pending: 2)" in message
    assert "Finish stage 3" in message
    assert "status: pending" in message
    assert "Restock milk" in message
    # Tip line present
    assert "Tip: reply 'complete <id>'" in message
