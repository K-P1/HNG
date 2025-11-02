import os
import time
import pytest
from app.services import llm_service


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
	# Ensure we start with clean env for each test here
	for k in ["A2A_ASYNC_ENABLED"]:
		monkeypatch.delenv(k, raising=False)
	yield


def _patch_plan_to_read(monkeypatch):
	async def fake_plan_actions(message: str):
		return {"actions": [{"type": "todo", "action": "read", "params": {}}]}
	monkeypatch.setattr(llm_service, "plan_actions", fake_plan_actions)


# 1. A2A_ASYNC_ENABLED=false -> Always synchronous, single response

def test_async_env_false_forces_sync(client, monkeypatch):
	_patch_plan_to_read(monkeypatch)
	monkeypatch.setenv("A2A_ASYNC_ENABLED", "false")

	# record follow-up calls
	recorded = []
	import app.services.telex_service as telex_service
	async def fake_send_telex(push_url, message, *args, **kwargs):
		recorded.append((push_url, message))
		return None
	monkeypatch.setattr(telex_service, "send_telex_followup", fake_send_telex)

	agent = os.getenv("A2A_AGENT_NAME", "Raven")
	payload = {
		"jsonrpc": "2.0",
		"id": "envfalse",
		"method": "message/send",
		"params": {
			"message": {"role": "user", "parts": [{"kind": "text", "text": "List my tasks"}]},
			"user_id": "u_async1",
			"configuration": {"pushNotificationConfig": {"url": "http://example.test/cb"}}
		}
	}
	resp = client.post(f"/a2a/agent/{agent}", json=payload)
	body = resp.json()
	assert body.get("result", {}).get("status", {}).get("state") == "completed"
	# No background follow-up should be sent
	assert not recorded


# 2. A2A_ASYNC_ENABLED=true + push_url + no blocking -> Preview + webhook follow-up

def test_async_env_true_prefers_async_with_push(client, monkeypatch):
	_patch_plan_to_read(monkeypatch)
	monkeypatch.setenv("A2A_ASYNC_ENABLED", "true")

	recorded = []
	import app.services.telex_service as telex_service
	async def fake_send_telex(push_url, message, *args, **kwargs):
		recorded.append((push_url, message, kwargs.get("additional_parts")))
		return None
	monkeypatch.setattr(telex_service, "send_telex_followup", fake_send_telex)

	agent = os.getenv("A2A_AGENT_NAME", "Raven")
	payload = {
		"jsonrpc": "2.0",
		"id": "envtrue",
		"method": "message/send",
		"params": {
			"message": {"role": "user", "parts": [{"kind": "text", "text": "List my tasks"}]},
			"user_id": "u_async2",
			"configuration": {"pushNotificationConfig": {"url": "http://example.test/cb"}, "blocking": False}
		}
	}
	resp = client.post(f"/a2a/agent/{agent}", json=payload)
	body = resp.json()
	assert body.get("result", {}).get("status", {}).get("state") == "working"

	# Background follow-up should be sent
	deadline = time.time() + 2.0
	while time.time() < deadline and not recorded:
		time.sleep(0.05)
	assert recorded
	push_url, message, parts = recorded[0]
	assert push_url == "http://example.test/cb"
	assert isinstance(message, str)
	# Additional data parts may include ToolResults
	if parts:
		assert any(p.get("kind") == "data" for p in parts)


# 3. A2A_ASYNC_ENABLED unset + blocking=true -> Single final response

def test_async_env_unset_respects_blocking_true(client, monkeypatch):
	_patch_plan_to_read(monkeypatch)
	# Ensure unset
	monkeypatch.delenv("A2A_ASYNC_ENABLED", raising=False)

	agent = os.getenv("A2A_AGENT_NAME", "Raven")
	payload = {
		"jsonrpc": "2.0",
		"id": "unsetblock",
		"method": "message/send",
		"params": {
			"message": {"role": "user", "parts": [{"kind": "text", "text": "List my tasks"}]},
			"user_id": "u_async3",
			"configuration": {"pushNotificationConfig": {"url": "http://example.test/cb"}, "blocking": True}
		}
	}
	resp = client.post(f"/a2a/agent/{agent}", json=payload)
	body = resp.json()
	assert body.get("result", {}).get("status", {}).get("state") == "completed"
