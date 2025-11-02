# Reflective Assistant (Raven)

Raven is a FastAPI-based AI agent that turns natural language messages into todo and journal actions.  
It uses **Groq** for structured planning (strict JSON), **Postgres** for persistence, and supports **Telex-style A2A integrations** via JSON-RPC 2.0.

- **Health check:** `GET /` → `{ status: "ok" }`  
- **Docs:** `/docs` (Swagger UI)

---

## Highlights

- LLM outputs strict JSON only — no prose allowed.
- Full CRUD support for todos and journals (with bulk actions).
- A2A endpoint ready for Telex integrations (sync or async).
- Async SQLAlchemy + Alembic migrations.
- Windows-friendly development with `uv` and `pytest`.

---

## Latest Updates (2025-11-02)

- Added async A2A mode (`A2A_ASYNC_ENABLED`).
- New filters for `todo.read`: status, limit, dueBefore/After, tags, and query.
- `ToolResults` now included in structured responses.
- Cleaner, more readable logs.

---

## Project Structure

```

app/
main.py            # FastAPI app setup
routes.py          # HTTP routes (tasks, journal, A2A)
crud.py            # Async CRUD functions
database.py        # Async DB connection (Postgres runtime, SQLite tests)
schemas.py         # Pydantic models
config.py          # Env-based app config
models/            # ORM models (Task, Journal)
services/          # LLM, CRUD orchestration, A2A handling
utils/             # Logging, LLM helpers, webhook sender
alembic/             # Migrations
tests/               # Unit tests

````

---

## How It Works

### 1. Text → Plan
Groq turns freeform text into JSON:
```json
{
  "actions": [
    { "type": "todo", "action": "create", "params": { "description": "buy milk" } }
  ]
}
````

The result is validated strictly — invalid output fails immediately.

### 2. Plan → Execution

`llm_service.execute_actions()` applies each action:

* Todo / Journal: create, read, update, delete.
* Dedupe todo.create (case-insensitive).
* Returns structured metadata and human-readable summaries.

### 3. Telex A2A Endpoint

`POST /a2a/agent/{agent_name}`
Processes `params.message.parts` or `params.text`.

Behavior depends on async settings:

* **Sync**: returns final result immediately.
* **Async**: sends preview instantly and posts final result via webhook.

Responses follow **JSON-RPC 2.0** and always echo the incoming `id`.

---

## Environment Variables

| Variable              | Description                                           | Default                       |
| --------------------- | ----------------------------------------------------- | ----------------------------- |
| ENV                   | Environment                                           | development                   |
| DEBUG                 | Enable debug mode                                     | false                         |
| DATABASE_URL          | Async Postgres URL                                    | —                             |
| LLM_PROVIDER          | Must be `groq`                                        | —                             |
| GROQ_API_KEY          | Groq API key                                          | —                             |
| GROQ_MODEL            | Groq model name                                       | llama-3.3-70b-versatile       |
| A2A_AGENT_NAME        | Agent route name                                      | Raven                         |
| TELEX_LOG_PATH        | Raw JSONL log file                                    | logs/telex_traffic.jsonl      |
| TELEX_PRETTY_LOG_PATH | Pretty log file                                       | logs/telex_traffic_pretty.log |
| A2A_ASYNC_ENABLED     | Async control (`false` → sync, `true` → prefer async) | unset                         |

---

## Quick Start

### 1. Create environment file

```powershell
copy .env.example .env
```

Set:

```
LLM_PROVIDER=groq
GROQ_API_KEY=<your_groq_api_key>
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
```

### 2. Install dependencies

```powershell
uv sync
```

### 3. Run migrations

```powershell
uv run alembic upgrade head
```

### 4. Start the API

```powershell
uv run uvicorn app.main:app --reload --port 8000
```

Visit:

* [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
* [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## Example A2A Request

```json
{
  "jsonrpc": "2.0",
  "id": "123",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{ "kind": "text", "text": "add buy milk to my todo" }]
    },
    "user_id": "u1"
  }
}
```

### Sync Response

```json
{
  "jsonrpc": "2.0",
  "id": "123",
  "result": {
    "messages": [
      { "role": "assistant", "content": "Added 'buy milk' (id: 1)" }
    ],
    "metadata": {
      "status": "ok",
      "executed": [{ "type": "todo.create", "task_id": 1 }]
    }
  }
}
```

If `pushNotificationConfig.url` is set, the server sends a preview first and posts the final result asynchronously.

---

## Planning Schema

```json
{
  "actions": [
    { "type": "todo" | "journal", "action": "create" | "read" | "update" | "delete", "params": {} }
  ]
}
```

**Rules**

* `todo.create`: needs `description` (optional `due_date`).
* `journal.create`: needs `entry`.
* Bulk ops allowed for `update` / `delete` via `scope`: `all`, `pending`, `completed`.

---

## Database & Migrations

* Runtime: **Postgres** (`postgresql+asyncpg://...`)
* Tests: **SQLite** (auto-configured)
* Alembic migrations are async-compatible.

**Commands**

```powershell
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "changes"
uv run alembic stamp head
```

---

## Testing

```powershell
uv run pytest -q
```

Tests:

* Mock LLM calls
* Use SQLite
* Compatible with Windows async event loop

---

## Logging

* Pretty logs: `logs/telex_traffic_pretty.log`
* Raw logs: `logs/telex_traffic.jsonl`
* Paths configurable via env.

---

## Deployment

1. Set `DATABASE_URL` (Postgres)
2. Run `uv run alembic upgrade head`
3. Start the server:

   ```powershell
   uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

---

## Troubleshooting

| Issue                      | Fix                                                 |
| -------------------------- | --------------------------------------------------- |
| **DB init failed**         | Check `DATABASE_URL` and ensure Postgres driver     |
| **LLM errors**             | Ensure `LLM_PROVIDER=groq` and valid `GROQ_API_KEY` |
| **Alembic import error**   | Run from project root                               |
| **SQLite lock on Windows** | Close DB viewers; use Postgres for runtime          |
