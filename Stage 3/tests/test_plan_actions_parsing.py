import sys
import os
import json
from dotenv import load_dotenv

# Ensure project root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()
_test_db = os.getenv("TEST_DATABASE_URL")
if _test_db:
	os.environ["DATABASE_URL"] = _test_db

from app.utils import llm


def test_extract_actions_strict_schema(monkeypatch):
	# Return strict schema from LLM with two todo.create actions
	sample = {
		"actions": [
			{"type": "todo", "action": "create", "params": {"description": "book flights"}},
			{"type": "todo", "action": "create", "params": {"description": "pack luggage"}},
		]
	}

	monkeypatch.setattr(llm, "_groq_chat", lambda *args, **kwargs: json.dumps(sample))

	plan = llm.extract_actions("book flights pack luggage")
	assert isinstance(plan, dict)
	actions = plan.get("actions")
	assert isinstance(actions, list)
	assert len(actions) == 2
	assert actions[0]["type"] == "todo" and actions[0]["action"] == "create"
	assert actions[0]["params"]["description"] == "book flights"
	assert actions[1]["type"] == "todo" and actions[1]["action"] == "create"
	assert actions[1]["params"]["description"] == "pack luggage"
