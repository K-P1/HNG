# Stage 2 backend task: Country Currency & Exchange API (Backend Task)

A small backend task to fetch country data from external APIs, cache it, compute an estimated GDP, and expose a few REST endpoints for querying and maintenance.

## Summary

- Fetch country metadata (name, capital, region, population, flag, currencies) from the Rest Countries API.
- Fetch exchange rates (base USD) from the Exchange Rates API.
- For each country, choose a currency code (first currency if multiple), match it to an exchange rate, compute an estimated GDP, and cache the result in a MySQL database.
- Provide endpoints for refresh, querying, deletion, status, and a generated summary image.

## External APIs

- Countries: https://restcountries.com/v2/all?fields=name,capital,region,population,flag,currencies
- Exchange rates: https://open.er-api.com/v6/latest/USD

## Endpoints

- POST /countries/refresh

  - Fetch countries + exchange rates, compute fields, and insert/update the DB. Also generate a summary image (cache/summary.png).

- GET /countries

  - Return all cached countries.
  - Support filters & sorting via query params:
    - ?region=Africa
    - ?currency=NGN
    - ?sort=gdp_desc (other options: gdp_asc, population_desc, name_asc, ...)

- GET /countries/:name

  - Return a single country by name (case-insensitive).

- DELETE /countries/:name

  - Delete a country record by name.

- GET /status

  - Return cache summary: total countries and last refresh timestamp.

- GET /countries/image
  - Serve the generated summary image. If it doesn't exist, return 404 with JSON error.

## Data model (Country)

- id — integer, auto-generated
- name — string, required
- capital — string, optional
- region — string, optional
- population — integer, required
- currency_code — string | null
- exchange_rate — number | null (rate relative to USD)
- estimated_gdp — number | null (computed)
- flag_url — string | null
- last_refreshed_at — timestamp (auto)

Notes on computed fields:

- estimated_gdp = population × random_multiplier ÷ exchange_rate
  - random_multiplier: integer randomly chosen from 1000 to 2000 for each country on each refresh
  - If exchange_rate is null, estimated_gdp should be null (or 0 when currency missing per rules below)

## Validation rules

- `name`, `population` are required. `currency_code` may be required by the endpoint if creating/updating directly.
- For invalid or missing required fields, return 400 Bad Request with a JSON body:

```json
{
  "error": "Validation failed",
  "details": { "currency_code": "is required" }
}
```

## Refresh behavior (POST /countries/refresh)

1. Fetch the countries list from Rest Countries API.
2. Fetch exchange rates (base USD) from the exchange rates API.
3. For each country:

   - If the `currencies` array has entries, use the first currency's `code` as `currency_code`.
   - If the `currencies` array is empty:
     - Do NOT call the exchange rate API for this country.
     - Set `currency_code` = null, `exchange_rate` = null, `estimated_gdp` = 0.
     - Still store/update the country record.
   - If `currency_code` is present but not found in the exchange rate response:
     - Set `exchange_rate` = null and `estimated_gdp` = null.
     - Still store/update the country record.
   - Otherwise compute `exchange_rate` and `estimated_gdp` using a fresh random multiplier (1000–2000).

4. Match existing countries by `name` (case-insensitive): update if exists, insert otherwise.
5. On successful refresh, update a global `last_refreshed_at` timestamp.

Error handling during refresh:

- If either external API fails or times out, abort the refresh, do not modify existing DB records, and return 503 Service Unavailable with:

```json
{
  "error": "External data source unavailable",
  "details": "Could not fetch data from [API name]"
}
```

## Image generation

- After a successful refresh, generate a summary image (e.g., `cache/summary.png`) containing:
  - Total number of countries
  - Top 5 countries by `estimated_gdp`
  - Timestamp of last refresh
- `GET /countries/image` should serve this file. If it doesn't exist, return 404 with:

```json
{ "error": "Summary image not found" }
```

## Error responses (consistent JSON)

- 404 Not Found

```json
{ "error": "Country not found" }
```

- 400 Bad Request

```json
{ "error": "Validation failed" }
```

- 500 Internal Server Error

```json
{ "error": "Internal server error" }
```

## Technical notes

- Use a relational database (MySQL) for persistence.
- The cache should only be updated when `POST /countries/refresh` is called.
- Store configuration values (DB credentials, port, etc.) in a `.env` file.
- All API responses must be JSON (except the image endpoint which returns an image MIME type).
- Include a `README.md` with setup and run instructions.

## Sample responses

GET /countries?region=Africa

```json
[
  {
    "id": 1,
    "name": "Nigeria",
    "capital": "Abuja",
    "region": "Africa",
    "population": 206139589,
    "currency_code": "NGN",
    "exchange_rate": 1600.23,
    "estimated_gdp": 25767448125.2,
    "flag_url": "https://flagcdn.com/ng.svg",
    "last_refreshed_at": "2025-10-22T18:00:00Z"
  }
]
```

GET /status

```json
{
  "total_countries": 250,
  "last_refreshed_at": "2025-10-22T18:00:00Z"
}
```

## Submission instructions

You may implement this in any language. When submitting, provide:

- Your API base URL (e.g., https://yourapp.domain.app)
- GitHub repository link
- Your full name and email
- Stack / language used
- Clear `README.md` with:
  - Setup and run instructions
  - Dependencies and installation steps
  - Environment variables required
  - Any tests and how to run them

Notes on hosting:

- Vercel and Render are not allowed for this cohort. Use other providers such as Railway, Heroku, AWS, PXXL App, etc.

Submission process (Slack):

1. Verify your server works from external networks if possible.
2. In the `#stage-2-backend` Slack channel, run the `/stage-two-backend` command and submit the requested URLs and info.
3. Confirm the Thanos bot feedback (error or success) after attempts.

Deadline: Wednesday, 29th Oct 2025 | 11:59pm GMT+1 (WAT)

Good luck!
