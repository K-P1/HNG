import os
import sys
import json
import pytest

# Ensure project root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# env and event loop policy are handled in conftest.py

from app import database, crud
from app.services import llm_service


def _set_plan(monkeypatch, actions):
	async def fake_plan_actions(message: str):
		return {"actions": actions}
	monkeypatch.setattr(llm_service, "plan_actions", fake_plan_actions)


@pytest.mark.asyncio
async def test_planner_create_and_list_tasks(monkeypatch):
	_set_plan(monkeypatch, [
		{"type": "todo", "action": "create", "params": {"description": "Finish stage 3"}},
		{"type": "todo", "action": "read", "params": {}},
	])

	res = await llm_service.execute_actions("u_test", [
		{"type": "todo", "action": "create", "params": {"description": "Finish stage 3"}},
		{"type": "todo", "action": "read", "params": {}},
	], "please add and list")

	assert res["status"] == "ok"
	assert "Finish stage 3" in res["message"]
	assert "Here are your tasks" in res["message"]


@pytest.mark.asyncio
async def test_planner_update_and_delete_task(monkeypatch):
	t = await crud.create_task("u_test2", "Temp task")

	actions = [
		{"type": "todo", "action": "update", "params": {"id": t.id, "status": "completed"}},
		{"type": "todo", "action": "delete", "params": {"id": t.id}},
	]
	res = await llm_service.execute_actions("u_test2", actions, "update then delete")

	assert res["status"] == "ok"
	assert f"Updated task #{t.id}" in res["message"]
	assert f"Deleted task #{t.id}" in res["message"]


@pytest.mark.asyncio
async def test_planner_update_delete_task_by_description(monkeypatch):
	_ = await crud.create_task("u_desc", "Finish stage 3")
	_ = await crud.create_task("u_desc", "Some other task")

	actions = [
		{"type": "todo", "action": "update", "params": {"description": "Finish stage 3", "status": "completed"}},
		{"type": "todo", "action": "delete", "params": {"description": "Finish stage 3"}},
	]
	res = await llm_service.execute_actions("u_desc", actions, "complete and remove by name")
	assert res["status"] == "ok"
	assert "Updated task #" in res["message"]
	assert "Deleted task #" in res["message"]


@pytest.mark.asyncio
async def test_planner_journal_flow(monkeypatch):

	actions = [
		{"type": "journal", "action": "create", "params": {"entry": "Today went well"}},
		{"type": "journal", "action": "read", "params": {"limit": 5}},
	]

	res = await llm_service.execute_actions("u_j", actions, "journal please")
	assert res["status"] == "ok"
	assert "Journal saved" in res["message"] or "Journal saved" in res["message"].lower()
	assert "Your latest" in res["message"] or "No journal entries" in res["message"]


@pytest.mark.asyncio
async def test_planner_update_delete_journal_by_text(monkeypatch):
	_ = await crud.create_journal("u_j2", "Finish stage 3 reflections", "Summary", "neutral")

	actions = [
		{"type": "journal", "action": "update", "params": {"entry": "Finish stage 3", "summary": "Updated"}},
		{"type": "journal", "action": "delete", "params": {"entry": "Finish stage 3"}},
	]
	res = await llm_service.execute_actions("u_j2", actions, "update journal and delete by text")
	assert res["status"] == "ok"
	assert "Updated journal #" in res["message"]
	assert "Deleted journal #" in res["message"]
