# Reflective Assistant

FastAPI-powered AI agent that turns freeform messages into structured todo and journal actions. It plans with Groq (strict JSON only), executes against a Postgres database, and speaks JSON-RPC 2.0 for Telex-style A2A integrations.

• Health: GET / → { status: "ok" }
• Docs: /docs (Swagger UI)

## Highlights

- Strict JSON planning: the LLM must return a validated schema (no prose)
- End-to-end flows for todo and journal: create/read/update/delete, bulk ops
- Telex-ready A2A endpoint with optional async follow-up callbacks
- Async SQLAlchemy + Alembic; Postgres for the app, SQLite for tests
- Windows-friendly dev setup with uv and pytest

## What’s inside

```
app/
  main.py            # FastAPI app, CORS, async lifespan (startup DB init, graceful shutdown)
  routes.py          # HTTP routes: tasks, journal, A2A agent
  crud.py            # Async CRUD over SQLAlchemy models
  database.py        # Async engine/session setup; Postgres-only at runtime; SQLite in tests
  schemas.py         # Pydantic models for API IO
  config.py          # Pydantic settings (env-backed)
  models/
    models.py        # ORM models: Task, Journal
    a2a.py           # Pydantic types for A2A shapes (reference)
  services/
    common.py        # date parsing, list formatting helpers
    llm_service.py   # plan (strict) + execute actions, dedupe, bulk ops
    task_service.py  # thin layer over CRUD for tasks
    journal_service.py # thin layer over CRUD for journals
    telex_service.py # A2A orchestration: text extraction, preview, follow-up
  utils/
    llm.py           # Groq-only helpers; classification + planner (JSON only)
    telex_push.py    # Async follow-up sender (JSON-RPC aware)
    json_logger.py   # Pretty JSON log writer for A2A traffic
alembic/
  env.py             # Async migrations; converts common drivers to async variants
  versions/          # Migration scripts (initial schema included)
pyproject.toml       # Project metadata, dependencies, pytest opts
pytest.ini           # Async pytest config
tests/               # Unit tests for planner, executor, and A2A
```

## How it works (overview)

1. Text in → strict plan out

- `utils/llm.extract_actions(text)` asks Groq for JSON only: { actions: [{ type, action, params }] }.
- The schema is strictly validated. Any deviation raises and fails fast.

2. Execute plan

- `services.llm_service.execute_actions(user_id, actions, original_text)` applies each action:
  - Todo: create/read/update/delete (+ bulk via scope: all|pending|completed)
  - Journal: create/read/update/delete
  - Dedupe on todo.create within a user (case/space-insensitive)
  - Friendly, concise response text is assembled; structured metadata is returned

3. Telex-style A2A

- Route: POST `/a2a/agent/{agent_name}` extracts text from `params.message.parts` (and nested `data`), then falls back to `params.message.text` or `params.text`.
- If a `pushNotificationConfig.url` exists, the handler:
  - Immediately returns a preview message (e.g., planned steps)
  - Schedules a background follow-up POST to the provided URL with the final reply
- All A2A responses are strict JSON-RPC 2.0 and echo the incoming `id`.

## Environment variables

- ENV: app environment (default: development)
- DEBUG: bool flag (default: false)
- DATABASE_URL: required for the running app; must be Postgres with async driver. Examples:
  - postgresql+asyncpg://user:pass@host:5432/dbname
  - Note: the runtime app explicitly rejects non-Postgres URLs. Tests auto-switch to SQLite.
- LLM_PROVIDER: must be groq
- GROQ_API_KEY: required; the app fails fast if missing
- GROQ_MODEL: default llama-3.3-70b-versatile
- A2A_AGENT_NAME: default Raven (path is dynamic: /a2a/agent/{name})
- TELEX_LOG_PATH: optional JSONL raw log path (default: logs/telex_traffic.jsonl)
- TELEX_PRETTY_LOG_PATH: optional pretty log path (default: logs/telex_traffic_pretty.log)

## Prerequisites

- Windows PowerShell
- Python 3.10+
- uv (dependency manager by Astral)

Install uv if needed:

```powershell
iwr https://astral.sh/uv/install.ps1 | iex
```

## Quick start (dev)

1. Create your environment file

```powershell
copy .env.example .env
```

Edit `.env` and set at minimum:

- LLM_PROVIDER=groq
- GROQ_API_KEY=<your_groq_api_key>
- DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname

2. Install dependencies

```powershell
uv sync
```

3. Apply migrations

```powershell
uv run alembic upgrade head
```

4. Run the API

```powershell
uv run uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000/ and http://127.0.0.1:8000/docs

## API surface

- GET `/` → `{ "status": "ok", "message": "..." }`

- GET `/tasks?user_id=u1` → TaskOut[]

- POST `/tasks/complete?task_id=1` → `{ status, task_id, status_after }`

- GET `/journal?user_id=u1&limit=20` → JournalOut[]

- POST `/a2a/agent/{agent_name}` → JSON-RPC 2.0

  - Request (minimal):

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

  - Response (no push URL provided):

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

  - Response when `pushNotificationConfig.url` is set:
    - Immediate reply contains a preview (e.g., "Planned steps: todo")
    - Final result is POSTed asynchronously to the provided URL as a JSON-RPC message

Contract notes:

- Always echo the incoming `id` in the response.
- Never omit the `id` field (JSON-RPC contract).
- Text is constructed from `params.message.parts` (including nested `data.text`) and fallbacks.

## Planning schema (strict)

The LLM must return only JSON with this shape:

```json
{
  "actions": [
    { "type": "todo" | "journal", "action": "create" | "read" | "update" | "delete", "params": {}}
  ]
}
```

Rules enforced in `utils.llm`:

- For `todo.create`: params.description is required (string). Optional: due or due_date (string).
- For `journal.create`: params.entry is required (string).
- For bulk task ops: `update`/`delete` can include `scope` in { all, pending, completed }.
- For `update`/`delete`: provide `id` if available; otherwise a discriminating field (e.g., description).

## Database and migrations

- Runtime app: Postgres required. Use `postgresql+asyncpg://...`.
- Tests: SQLite is auto-used; pooling disabled for stability on Windows.
- Migrations are async-aware and convert common sync URLs to async ones when possible.

Alembic commands (use PowerShell):

```powershell
uv run alembic upgrade head          # Apply latest
uv run alembic revision --autogenerate -m "changes"  # Generate after model edits
uv run alembic stamp head            # Mark current DB state as up-to-date
```

## Development and testing

- Run tests (LLM calls are monkeypatched in unit tests):

```powershell
uv run pytest -q
```

Notes:

- Tests force SQLite (`sqlite+aiosqlite:///./test.db`) and set a Windows-friendly event loop policy.
- You can safely run tests without a Postgres instance or a Groq API key.

## Logging

- App logs: `app.log` (rolling append)
- Telex traffic (pretty): `logs/telex_traffic_pretty.log` (redacts tokens; includes summarized and raw payloads)
- Configure paths with `TELEX_LOG_PATH` and `TELEX_PRETTY_LOG_PATH`

## Deployment

1. Set `DATABASE_URL=postgresql+asyncpg://...` in the environment
2. Run migrations: `uv run alembic upgrade head`
3. Start the server:

```powershell
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Troubleshooting

- Database init failed at startup
  - Ensure `DATABASE_URL` is set and uses Postgres with async driver (postgresql+asyncpg)
- LLM errors
  - Set `LLM_PROVIDER=groq` and provide a valid `GROQ_API_KEY`
- Alembic cannot import `app`
  - Run from project root; `alembic/env.py` adds the root to `sys.path`
- Windows + SQLite locks
  - Close DB viewers and retry; for the app itself, prefer Postgres.

## License

MIT (see LICENSE if present)
