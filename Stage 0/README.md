# Stage 0 — Profile Endpoint (FastAPI)

This is a simple FastAPI application that exposes a single endpoint:
**GET `/me`**, which returns my profile information along with a random cat fact fetched from the public [Cat Facts API](https://catfact.ninja/fact).

---

## Features

* **GET `/me`** — Returns:

  * `status`: always `"success"`
  * `user`: includes `email`, `name`, and `stack`
  * `timestamp`: current UTC time in ISO 8601 format
  * `fact`: random cat fact from the Cat Facts API
* Handles external API errors with a fallback fact (so the endpoint always responds)
* Clean modular structure:

  * `app/schemas.py` — Pydantic models
  * `app/services.py` — Cat Facts and helper logic
  * `app/routes.py` — Route definitions
  * `app/main.py` — Application entry point
* Basic logging
* Optional Redis integration for rate limiting (non-blocking if Redis is absent)
* Unit tests for success and fallback cases

---

## Requirements

* Python **3.11+**
* Dependencies listed in `requirements.txt`

---

## Setup

### 1. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

---

## Environment Variables

| Variable            | Description                        | Default                      |
| ------------------- | ---------------------------------- | ---------------------------- |
| `USER_EMAIL`        | Your email address                 | —                            |
| `USER_NAME`         | Your full name                     | —                            |
| `USER_STACK`        | Your backend stack                 | —                            |
| `CAT_FACTS_URL`     | Cat Facts API endpoint             | `https://catfact.ninja/fact` |
| `CAT_FACTS_TIMEOUT` | Timeout for API call (seconds)     | `2.0`                        |
| `REDIS_URL`         | Redis connection string (optional) | `redis://localhost:6379/0`   |

> Copy `.env.example` to `.env` and fill in your values for local development.

```powershell
Copy-Item .env.example .env
```

---

## Run Locally

Start the development server:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Then open [http://127.0.0.1:8000/me](http://127.0.0.1:8000/me)

---

## Example Response

```json
{
  "status": "success",
  "user": {
    "email": "hamedayokunle58@gmail.com",
    "name": "Hamed Ayokunle",
    "stack": "Python/FastAPI"
  },
  "timestamp": "2025-10-17T12:34:56.789Z",
  "fact": "Cats have five toes on their front paws, but only four on their back paws."
}
```

---

## Handling Failures

* If the Cat Facts API is slow or unavailable, a short fallback fact is returned.
* The `status` remains `"success"` to keep responses predictable.

---

## Deployment Notes (Railway Example)

When deploying, ensure the app binds to `0.0.0.0` and uses the provided `$PORT`.

**Build command:**

```bash
pip install -r requirements.txt
```

**Start command:**

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

> Confirm your Railway service type is **Web** and not **Unexposed**.
> After deployment, open your public URL and test `/me`.

**Live URL:**
[https://hng-production-345d.up.railway.app/me](https://hng-production-345d.up.railway.app/me)

---

## Run Tests

```powershell
pytest -q
```

Tests cover:

* Successful `/me` call with mocked external fact
* Fallback behavior on timeout or API failure

---

## Notes

* The `timestamp` updates dynamically with each request.
* Redis (if available) is used for rate-limiting; if not, the app logs a warning and runs normally.
* The response `Content-Type` is always `application/json`.

---

## Repository

GitHub Repository: [https://github.com/K-P1/HNG.git](https://github.com/K-P1/HNG.git)

---

