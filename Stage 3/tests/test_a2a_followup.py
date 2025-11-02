import os
import sys
import time
from dotenv import load_dotenv
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()
_test_db = os.getenv("TEST_DATABASE_URL")
if _test_db:
	os.environ["DATABASE_URL"] = _test_db

# Force a local SQLite DB for tests to avoid external dependencies/asyncpg issues on Windows
os.environ["TEST_DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

# Ensure tests use the test database if configured
_TEST_DB = os.getenv("TEST_DATABASE_URL")
if _TEST_DB:
	os.environ["DATABASE_URL"] = _TEST_DB

from app.main import app
from app.services import llm_service
from app.utils.telex_push import send_telex_followup as real_send_telex_followup


def test_a2a_followup_posts_task_list(monkeypatch):
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

	client = TestClient(app)

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
