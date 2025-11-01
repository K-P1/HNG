import os
import sys
import asyncio
import json
import types
from fastapi.testclient import TestClient

# Ensure project root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app import services
from app import database
from app import crud


def test_planner_create_and_list_tasks(monkeypatch):
    # Use sqlite memory or dev db per app.database default init
    asyncio.run(database.init_db_async())

    # Monkeypatch the planner to emit two actions: create and list
    def fake_plan_actions(message: str):
        return {
            "actions": [
                {"type": "create_task", "params": {"description": "Finish stage 3"}},
                {"type": "list_tasks", "params": {}},
            ]
        }

    monkeypatch.setattr(services.llm, "plan_actions", fake_plan_actions)

    result = asyncio.run(services.process_telex_message("u_test", "please add and list"))
    assert result["status"] == "ok"
    assert "Finish stage 3" in result["message"]
    assert "Here are your tasks" in result["message"]


def test_planner_update_and_delete_task(monkeypatch):
    asyncio.run(database.init_db_async())
    # seed a task
    t = asyncio.run(crud.create_task("u_test2", "Temp task"))

    def fake_plan_actions(message: str):
        return {
            "actions": [
                {"type": "update_task", "params": {"id": t.id, "status": "completed"}},
                {"type": "delete_task", "params": {"id": t.id}},
            ]
        }

    monkeypatch.setattr(services.llm, "plan_actions", fake_plan_actions)

    result = asyncio.run(services.process_telex_message("u_test2", "update then delete"))
    assert result["status"] == "ok"
    assert f"Updated task #{t.id}" in result["message"]
    assert f"Deleted task #{t.id}" in result["message"]


def test_planner_journal_flow(monkeypatch):
    asyncio.run(database.init_db_async())

    def fake_plan_actions(message: str):
        return {
            "actions": [
                {"type": "create_journal", "params": {"entry": "Today went well"}},
                {"type": "list_journals", "params": {"limit": 5}},
            ]
        }

    # Don't call external LLM for analyze_entry inside create_journal
    async def fake_analyze(entry: str):
        return ("positive", "Good day")

    monkeypatch.setattr(services.llm, "plan_actions", fake_plan_actions)
    # analyze_entry is sync in our impl; service wraps with to_thread. Patch llm function directly.
    monkeypatch.setattr(services.llm, "analyze_entry", lambda text: ("positive", "Good day"))

    result = asyncio.run(services.process_telex_message("u_j", "journal please"))
    assert result["status"] == "ok"
    assert "Journal saved" in result["message"] or "Journal saved" in result["message"].lower()
    assert "Your latest" in result["message"] or "No journal entries" in result["message"]
