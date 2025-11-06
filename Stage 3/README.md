# Reflective Assistant (Raven)

Raven is a FastAPI-based AI agent that turns natural language messages into todo and journal actions.  
It uses **Groq** for structured planning (strict JSON), **Postgres** for persistence, and supports **Telex-style A2A integrations** via JSON-RPC 2.0.

- **Health check:** `GET /` → `{ status: "ok" }`
- **Docs:** `/docs` (Swagger UI)

---

## Highlights

- **Autonomous reminders** — Background scheduler sends deadline notifications automatically.
- **Smart deadline tracking** — Reminders at 24h, 1h, deadline, and when overdue.
- LLM outputs strict JSON only — no prose allowed.
- Full CRUD support for todos and journals (with bulk actions).
- A2A endpoint ready for Telex integrations (sync or async).
- Async SQLAlchemy + Alembic migrations.
- Windows-friendly development with `uv` and `pytest`.

---

## Latest Updates

### 2025-11-06: Autonomous Task Reminder System

- **Automatic deadline reminders**: Background scheduler sends follow-ups via Telex when tasks are due
- **Smart timing**: Reminders at 24h before, 1h before, at deadline, and daily when overdue
- **Natural language**: LLM-generated casual, friendly reminder messages
- **Flexible reminders**: Support for both due dates and "remind me in X hours" syntax
- **Auto-captured push URLs**: User webhook endpoints stored automatically for autonomous operation
- **Quiet hours**: Configurable no-reminder periods (default: 10pm-8am)
- **Spam prevention**: Intelligent throttling and max reminder limits

### 2025-11-02

- Added async A2A mode (`A2A_ASYNC_ENABLED`).
- New filters for `todo.read`: status, limit, dueBefore/After, tags, and query.
- `ToolResults` now included in structured responses.
- Cleaner, more readable logs.

---

## Project Structure

```
app/
  main.py            # FastAPI app setup (includes reminder scheduler lifecycle)
  routes.py          # HTTP routes (tasks, journal, A2A)
  crud.py            # Async CRUD functions (tasks, journals, users, reminders)
  database.py        # Async DB connection (Postgres runtime, SQLite tests)
  schemas.py         # Pydantic models
  config.py          # Env-based app config (includes reminder settings)
  models/            # ORM models (Task, Journal, User)
  services/          # LLM, CRUD orchestration, A2A handling
  features/
    reminders/       # Autonomous reminder feature module
      service.py     # Background scheduler for autonomous reminders
  utils/             # Logging, LLM helpers, webhook sender
alembic/             # Migrations
tests/               # Unit tests (including reminder service tests)
docs/                # Documentation
  REMINDER_FEATURE.md   # Full reminder system documentation
  REMINDER_SETUP.md     # Quick setup guide
```

---

## How It Works

### 1. Text → Plan

Groq turns freeform text into JSON:

```json
{
  "actions": [
    {
      "type": "todo",
      "action": "create",
      "params": { "description": "buy milk" }
    }
  ]
}
```

The result is validated strictly — invalid output fails immediately.

### 3. Plan → Execution

`llm_service.execute_actions()` applies each action:

- Todo / Journal: create, read, update, delete.
- Dedupe todo.create (case-insensitive).
- Extracts `due_date` and `reminder_time` from natural language.
- Returns structured metadata and human-readable summaries.

### 4. Autonomous Reminders

Background scheduler monitors tasks (only in async mode when `A2A_ASYNC_ENABLED=true`):

- Checks every minute (configurable).
- Sends reminders at 24h, 1h before deadline, at deadline, and when overdue.
- Uses LLM to generate casual, context-aware messages.
- Automatically captures and stores user push URLs for webhook delivery.
- Respects quiet hours and prevents spam with intelligent throttling.

### 4. Telex A2A Endpoint

`POST /a2a/agent/{agent_name}`
Processes `params.message.parts` or `params.text`.

Behavior depends on async settings:

- **Sync**: returns final result immediately.
- **Async**: sends preview instantly and posts final result via webhook.

**Automatic push URL storage**: When a request includes `pushNotificationConfig.url`, the system stores it for the user, enabling autonomous reminders.

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

### Reminder Settings

| Variable                        | Description                           | Default |
| ------------------------------- | ------------------------------------- | ------- |
| REMINDER_CHECK_INTERVAL_MINUTES | How often to check for reminders      | 1       |
| REMINDER_ADVANCE_HOURS          | When to remind before due (comma-sep) | 24,1    |
| REMINDER_QUIET_HOURS_START      | No reminders after this hour (24h)    | 22      |
| REMINDER_QUIET_HOURS_END        | No reminders before this hour (24h)   | 8       |
| REMINDER_MAX_OVERDUE_REMINDERS  | Max reminders for overdue tasks       | 5       |
| REMINDER_OVERDUE_INTERVAL_HOURS | Hours between overdue reminders       | 24      |

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
# or
pip install -e .
```

### 3. Run migrations

```powershell
uv run alembic upgrade head
```

This creates:

- Task, Journal, and User tables
- Reminder fields (reminder_time, last_reminder_sent, reminder_enabled)

### 4. Start the API

```powershell
uv run uvicorn app.main:app --reload --port 8000
```

You should see:

```
INFO [main] Startup: starting reminder scheduler...
INFO [reminder_service] Reminder scheduler started (checking every 1 minutes)
```

Or if `A2A_ASYNC_ENABLED` is not set:

```
INFO [main] Reminder scheduler disabled (A2A_ASYNC_ENABLED not set)
```

Visit:

- [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

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

- `todo.create`: needs `description` (optional `due`, `reminder`).
- `journal.create`: needs `entry`.
- Bulk ops allowed for `update` / `delete` via `scope`: `all`, `pending`, `completed`.

**Reminder Examples**

- `"Add task to submit report by Friday 3pm"` → Creates task with `due_date`
- `"Remind me to call John in 2 hours"` → Creates task with `reminder_time`
- `"Add task due Monday, remind me Friday"` → Creates task with both fields

---

## Autonomous Reminders

The system includes a background scheduler that automatically sends deadline reminders.

### How It Works

1. **Automatic monitoring**: Scheduler checks tasks every minute (only runs when `A2A_ASYNC_ENABLED=true`)
2. **Smart timing**: Sends reminders at 24h before, 1h before, at deadline, and when overdue
3. **Natural language**: LLM generates casual, friendly messages like:
   - "Hey! Your task 'Submit report' is due in 1 hour."
   - "Reminder: 'Team meeting' is due now."
   - "Heads up - 'Review code' was due 2 days ago."
4. **Zero config**: Push URLs captured automatically from Telex requests

### Features

- **Quiet hours**: No reminders 10pm-8am (configurable)
- **Spam prevention**: Won't send multiple reminders within 30 minutes
- **Max reminders**: Stops after 5 overdue reminders per task
- **Fallback**: Uses templates if LLM unavailable

### Usage

Tasks automatically get reminders if they have a `due_date` or `reminder_time`:

```
"Add task to submit proposal by Friday 2pm"
"Remind me to call Sarah in 3 hours"
```

See full documentation: `docs/REMINDER_FEATURE.md`

---

## Database & Migrations

- Runtime: **Postgres** (`postgresql+asyncpg://...`)
- Tests: **SQLite** (auto-configured)
- Alembic migrations are async-compatible.

**Schema includes:**

- `tasks`: Core task table with reminder fields (reminder_time, last_reminder_sent, reminder_enabled)
- `journals`: Journal entries
- `users`: Stores push URLs for autonomous reminders

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
# or test specific modules
pytest tests/test_reminder_service.py -v
```

Tests:

- Mock LLM calls
- Use SQLite
- Compatible with Windows async event loop
- Includes reminder service unit tests (time context, quiet hours, message generation)

---

## Logging

- Pretty logs: `logs/telex_traffic_pretty.log`
- Raw logs: `logs/telex_traffic.jsonl`
- Paths configurable via env.

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

| Issue                      | Fix                                                                                          |
| -------------------------- | -------------------------------------------------------------------------------------------- |
| **DB init failed**         | Check `DATABASE_URL` and ensure Postgres driver                                              |
| **LLM errors**             | Ensure `LLM_PROVIDER=groq` and valid `GROQ_API_KEY`                                          |
| **Alembic import error**   | Run from project root                                                                        |
| **SQLite lock on Windows** | Close DB viewers; use Postgres for runtime                                                   |
| **Reminders not sending**  | Check scheduler logs; verify user has push_url stored; ensure task has reminder_enabled=true |
| **Scheduler won't start**  | Verify `apscheduler` installed: `pip install -e .`                                           |

---

## Documentation

- **Main README**: This file
- **Reminder System**: `docs/REMINDER_FEATURE.md` - Complete feature documentation
- **Setup Guide**: `docs/REMINDER_SETUP.md` - Quick start for reminders
- **API Docs**: `/docs` endpoint (Swagger UI)
