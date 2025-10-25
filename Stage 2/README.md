# Country Currency & Exchange API

A FastAPI service that fetches and caches country data along with computed GDP estimates. Includes endpoints for refresh, querying, deletion, status reporting, and generating a summary image.

**Live API:** [https://hng-production-8c0c.up.railway.app](https://hng-production-8c0c.up.railway.app)
**Swagger Docs:** [https://hng-production-8c0c.up.railway.app/docs](https://hng-production-8c0c.up.railway.app/docs)

---

## Tech Stack

* FastAPI, SQLAlchemy, Pydantic v2
* Pillow (for image generation)
* Requests (for HTTP calls)
* MySQL (primary database)
* SQLite (used automatically for local development if MySQL isn’t available)

---

## Features

* **POST /countries/refresh**
  Fetches country data and exchange rates, computes `estimated_gdp`, and updates the database atomically.
  Also generates `cache/summary.png` showing totals, top 5 countries by GDP, and the refresh timestamp.

* **GET /countries**
  Supports filtering, sorting, and pagination.

  * Filters: `region`, `currency` (case-insensitive)
  * Sorting: `gdp_desc`, `gdp_asc`, `population_desc`, `population_asc`, `name_asc`, `name_desc`
  * Pagination: `limit`, `offset`

* **GET /countries/{name}** – Fetch a country by name (case-insensitive)

* **DELETE /countries/{name}** – Delete a country record

* **GET /status** – Returns total countries and last refresh timestamp

* **GET /countries/image** – Serves the generated summary image

---

## Setup

1. **Install Python 3.11+**
2. **Create and activate a virtual environment:**

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. **Install dependencies:**

   ```powershell
   pip install -r requirements.txt
   ```
4. **Set up environment variables:**
   Copy `.env.example` to `.env`:

   ```powershell
   Copy-Item .env.example .env
   ```

**Key variables:**

* `DATABASE_URL`: Database connection string

  * Default (SQLite): `sqlite:///./dev.db`
  * MySQL: `mysql+mysqlconnector://user:pass@host:3306/dbname`
* `PORT`, `LOG_LEVEL`, `CONSOLE_LOG_LEVEL`
* `COUNTRY_API`, `EXCHANGE_API`
* Optional: `REDIS_URL` for rate limiting

**Notes:**

* In local development, the app falls back to SQLite if MySQL is unavailable.
* In production, set `DATABASE_URL` to a valid MySQL URL and ensure proper permissions.

---

## Run Locally

```powershell
uvicorn app.main:app --reload --port 8000
```

Local Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
Production Swagger UI: [https://hng-production-8c0c.up.railway.app/docs](https://hng-production-8c0c.up.railway.app/docs)

---

## Optional: Rate Limiting (Redis)

1. Start Redis (Docker example):

   ```powershell
   docker run -d --name redis -p 6379:6379 redis:7-alpine
   ```
2. Set `REDIS_URL` in `.env`:

   ```
   REDIS_URL=redis://localhost:6379/0
   ```
3. Restart the app.

**Defaults:**

* General endpoints – 60 req/min
* Refresh endpoint – 10 req/min
* Image endpoint – 30 req/min

If Redis isn’t available, rate limiting is disabled automatically.

---

## Tests

```powershell
pytest -q
```

---

## Error Responses

All errors return JSON:

* `404`: `{ "error": "Country not found" }`
* `400`: `{ "error": "Validation failed", "details": [...] }`
* `503`: `{ "error": "External data source unavailable" }`
* `500`: `{ "error": "Internal server error" }`

---

## Implementation Notes

* Refresh operations are transactional; failed API calls don’t alter the database.
* `estimated_gdp = population × random(1000–2000) ÷ exchange_rate`
* Countries without valid currency data store `exchange_rate = null` and `estimated_gdp = 0`.
* The summary image is saved as `cache/summary.png` after each refresh.
* Rate limiting (if enabled) uses `fastapi-limiter` with Redis.
