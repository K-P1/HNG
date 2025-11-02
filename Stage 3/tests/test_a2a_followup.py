import os
import time
from app.services import llm_service


def test_a2a_followup_posts_task_list(client, monkeypatch):
	# Patch planner to list tasks via strict schema
	async def fake_plan_actions(message: str):
		return {"actions": [{"type": "todo", "action": "read", "params": {}}]}

	monkeypatch.setattr(llm_service, "plan_actions", fake_plan_actions)

	# Patch send_telex_followup to capture background send
	recorded = []

	async def fake_send_telex(push_url, message, *args, **kwargs):
		recorded.append((push_url, message))
		return None

	# Patch where telex_service imports it (module-level import)
	import app.services.telex_service as telex_service
	monkeypatch.setattr(telex_service, "send_telex_followup", fake_send_telex)

	AGENT_NAME = os.getenv("A2A_AGENT_NAME", "Raven")

	payload = {
		"jsonrpc": "2.0",
		"id": "followup-test",
		"method": "message/send",
		"params": {
			"message": {
				"role": "user",
				"parts": [{"kind": "text", "text": "Please list my todos"}]
			},
			"user_id": "u_follow",
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
	assert messages and "Planned steps:" in messages[0]["content"]

	# Wait for the background follow-up to be invoked (give it up to 2s)
	deadline = time.time() + 2.0
	while time.time() < deadline and not recorded:
		time.sleep(0.05)

	assert recorded, "Expected follow-up to be sent via send_telex_followup"
	push_url, message = recorded[0]
	assert push_url == "http://example.test/push"
	assert isinstance(message, str) and len(message) > 0
