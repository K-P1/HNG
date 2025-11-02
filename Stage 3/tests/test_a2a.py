import json
import os

from app.services import llm_service


def test_a2a_reflective_assistant_monkeypatched(client, monkeypatch):

	# Stub planner to return strict-schema create action (no external LLM)
	async def fake_plan_actions(text: str):
		return {
			"actions": [
				{"type": "todo", "action": "create", "params": {"description": "buy milk"}}
			]
		}

	monkeypatch.setattr(llm_service, "plan_actions", fake_plan_actions)

	AGENT_NAME = os.getenv("A2A_AGENT_NAME", "Raven")

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

	# A2A-compliant JSON-RPC response
	assert body.get("jsonrpc") == "2.0"
	assert body.get("id") == "test-123"
	result = body.get("result")
	assert isinstance(result, dict)

	# TaskResult core fields
	assert result.get("kind") == "task"
	assert isinstance(result.get("id"), str)
	assert isinstance(result.get("contextId"), str)

	status = result.get("status")
	assert isinstance(status, dict)
	assert status.get("state") == "completed"
	assert isinstance(status.get("timestamp"), str)

	# Status message structure
	msg = status.get("message")
	assert isinstance(msg, dict)
	assert msg.get("role") == "agent"
	parts = msg.get("parts")
	assert isinstance(parts, list) and len(parts) > 0
	first_part = parts[0]
	assert first_part.get("kind") == "text"
	assert "Added" in (first_part.get("text") or "")

	# Artifacts exist with at least assistantResponse
	artifacts = result.get("artifacts")
	assert isinstance(artifacts, list)
	assert len(artifacts) >= 1
	assert isinstance(artifacts[0].get("parts"), list)

	# History includes the user message
	history = result.get("history")
	assert isinstance(history, list)
	assert history and history[0].get("role") == "user"
