# Reflective Assistant

FastAPI-powered AI agent that classifies incoming messages as todos or journal entries, stores them in a database, and replies concisely. Groq is used as the agent brain (no fallbacks—misconfiguration fails fast).

**Live API:** [hng-production-2944.up.railway.app](hng-production-2944.up.railway.app)
**Swagger Docs:** [hng-production-2944.up.railway.app/docs](hng-production-2944.up.railway.app/docs)

## Features

- Groq-powered intent classification (todo | journal | unknown)
- Todo action extraction and journal summarization + sentiment
- REST API endpoints for Telex integration and data listing
- SQLAlchemy ORM with Alembic migrations (SQLite local; Postgres in deploy)
- Clean layering: routes → services → crud → models

## Project structure

```
app/
	main.py           # FastAPI app, CORS, lifespan, includes router
	routes.py         # Lean route handlers only
	services.py       # Business logic, calls LLM + CRUD
	crud.py           # DB read/write operations
	models.py         # ORM models only
	database.py       # Engine, SessionLocal, init_db
	schemas.py        # Pydantic request/response models
	utils/
		llm.py          # Groq-only helpers (fail fast)
alembic/
	env.py            # Migration config wired to DATABASE_URL and models.Base
	versions/         # Migration scripts
.env.example        # Template for env vars
pyproject.toml      # Project metadata and dependencies
requirements.txt    # Pinned runtime deps (optional with uv)
uv.lock             # uv lockfile
```

## Prerequisites

- Windows PowerShell
- Python 3.10+
- uv (package/dependency manager by Astral)
  - Optional installation (if uv isn’t installed):
    - powershell
    - iwr https://astral.sh/uv/install.ps1 | iex

If you plan to connect to MySQL asynchronously (recommended with the async SQLAlchemy setup in this repo) install `aiomysql` in your environment. For SQLite async support we use `aiosqlite`.

Example (within the project virtualenv):

```powershell
& .venv\Scripts\pip.exe install aiomysql aiosqlite
```

## Setup with uv

1. Create your `.env` from the example

```powershell
copy .env.example .env
```

Edit `.env` and set at minimum:

- `LLM_PROVIDER=groq`
- `GROQ_API_KEY=<your_groq_api_key>`
- `DATABASE_URL` (SQLite local default is fine; set Postgres in deploy)

2. Install dependencies and create the virtual environment

```powershell
uv sync
```

This will create `.venv` and install all dependencies from `pyproject.toml` / `uv.lock`.

3. Initialize/upgrade the database schema (Alembic)

This project uses an async SQLAlchemy engine. The included `alembic/env.py` supports async engines (it will convert common sync drivers to their async equivalents when possible, e.g. `+pymysql` → `+aiomysql`, `sqlite://` → `sqlite+aiosqlite://`). Make sure the matching async DB driver is installed in the environment where you run Alembic.

```powershell
# Uses DATABASE_URL from .env
uv run alembic upgrade head
```

4. Run the API

```powershell
uv run uvicorn app.main:app --reload --port 8000
```

Health check: http://127.0.0.1:8000/health

Interactive docs: http://127.0.0.1:8000/docs

- `DATABASE_URL` – default `sqlite:///./app.db`; when using the async setup set an async driver in the URL.
  Examples:

  - Async MySQL: `mysql+aiomysql://user:pass@host:3306/dbname`
  - Async SQLite (local file): `sqlite+aiosqlite:///./dev.db`
  - Postgres (sync): `postgresql+psycopg2://user:pass@host:5432/dbname` (you can also use an async Postgres driver such as `asyncpg` via `postgresql+asyncpg://...` if you migrate drivers)

- `GROQ_API_KEY` – required (no fallbacks)
- `LLM_PROVIDER` – must be `groq`
- `GROQ_MODEL` – default `llama-3.3-70b-versatile`
- `ENV`, `DEBUG` – optional app flags

## API

- GET `/health` → `{ "status": "ok" }`

- A2A (Agent-to-Agent) JSON-RPC endpoint — Telex integration

  The app exposes a JSON-RPC 2.0-compatible A2A endpoint that Telex (or
  another agent) can call. The default path is:

  ```text
  POST /a2a/agent/reflectiveAssistant
  ```

  This path is dynamic and controlled by the `A2A_AGENT_NAME` environment
  variable (fallback `AGENT_NAME`). To guarantee the exact path above, set
  `A2A_AGENT_NAME=reflectiveAssistant` in your `.env` (see `.env.example`).

  - Incoming request (example JSON-RPC 2.0 payload):

    ```json
    {
      "jsonrpc": "2.0",
      "id": "b9d4caa5ecf749e0a59ba5614d01f266",
      "method": "message/send",
      "params": {
        "message": {
          "role": "user",
          "parts": [
            {
              "kind": "text",
              "text": "hi i want to submit my project tomorrow"
            }
          ]
        }
      }
    }
    ```

  - Expected reply (JSON-RPC 2.0, Telex-friendly):

    ```json
    {
      "jsonrpc": "2.0",
      "id": "b9d4caa5ecf749e0a59ba5614d01f266",
      "result": {
        "messages": [
          {
            "role": "assistant",
            "content": "Got it — I’ve added that to your todo list and scheduled a reminder for tomorrow!"
          }
        ],
        "metadata": {
          "status": "ok",
          "task_id": 123
        }
      }
    }
    ```

  - Notes about the JSON-RPC contract and `id` handling:

    | Case                | What You Do                                                           |
    | ------------------- | --------------------------------------------------------------------- |
    | Telex sends an `id` | Echo it back exactly.                                                 |
    | No `id` in request  | Generate one (UUID).                                                  |
    | Never               | Return a response without an `"id"`. It breaks the JSON-RPC contract. |

  - The service will try to extract text from several common shapes
    (`params.message.parts`, `params.message.text`, `params.text`). Any
    internal fields (status, task_id, summary, sentiment) are included
    under `result.metadata` while the user-facing reply is in
    `result.messages[0].content`.

- GET `/tasks?user_id=u1` → list of tasks (TaskOut[])

- POST `/tasks/complete?task_id=1` → `{ status, task_id, status_after }`

- GET `/journal?user_id=u1` → list of journals (JournalOut[])

## Migrations (Alembic) with uv

All commands read `DATABASE_URL` from `.env`.

```powershell
# Apply latest migrations
uv run alembic upgrade head

# Create a new migration after model changes
uv run alembic revision --autogenerate -m "your message"

# If your local DB already has the schema and you want Alembic to match it
uv run alembic stamp head
```

Note: Alembic is fully configured in `alembic/`. An initial revision reflecting current models is included.

## Deployment (Postgres)

1. Set `DATABASE_URL` to your Postgres connection string in the deployment environment.

2. Run migrations on the target database:

```powershell
uv run alembic upgrade head
```

3. Start the API process (example with uvicorn):

```powershell
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Telex integration (high level)

- Expose your service via ngrok/Railway and configure Telex to POST to `/telex-agent`.
- The endpoint detects intent, stores data, and returns a concise reply.
- You can validate quickly with the interactive docs at `/docs`.

## Troubleshooting

- LLM error (503): ensure `LLM_PROVIDER=groq` and a valid `GROQ_API_KEY` are set.
- Alembic `ModuleNotFoundError: app`: run commands from the project root; we add the root to `sys.path` in `alembic/env.py`.
- SQLite locking on Windows: close any open DB viewers and retry; consider switching to Postgres sooner.
