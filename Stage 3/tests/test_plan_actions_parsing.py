import sys
import os
import json

# Ensure project root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.utils import llm


def test_plan_actions_accepts_item_shape(monkeypatch):
    sample = {
        "actions": [
            {"type": "create", "item": {"description": "book flights"}},
            {"type": "create", "item": {"description": "pack luggage"}},
        ]
    }

    # Bypass external API by stubbing _groq_chat to return our JSON
    monkeypatch.setattr(llm, "_groq_chat", lambda *args, **kwargs: json.dumps(sample))

    plan = llm.plan_actions("book flights pack luggage")
    assert isinstance(plan, dict)
    actions = plan.get("actions")
    assert isinstance(actions, list)
    assert len(actions) == 2
    assert actions[0]["type"] == "create_task"
    assert actions[0]["params"]["description"] == "book flights"
    assert actions[1]["type"] == "create_task"
    assert actions[1]["params"]["description"] == "pack luggage"
