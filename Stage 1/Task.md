# Backend Wizards — Stage 1: String Analyzer Service

Welcome to Stage 1!:

Build a RESTful API service that analyzes strings and stores their computed properties. The API should accept strings, compute a set of properties for each string, persist them, and expose endpoints for querying and managing analyzed strings.

## Required computed properties

For each analyzed string, compute and store:

- `length`: number of characters in the string
- `is_palindrome`: boolean, whether the string reads the same forwards and backwards (case-insensitive)
- `unique_characters`: count of distinct characters in the string
- `word_count`: number of whitespace-separated words
- `sha256_hash`: SHA-256 hash of the string (used as a unique id)
- `character_frequency_map`: object mapping each character to its occurrence count

## Endpoints

All responses should use JSON and appropriate HTTP status codes.

### 1- Create / Analyze String

POST /strings
Content-Type: application/json

Request body

```json
{ "value": "string to analyze" }
```

Success (201 Created)

```json
{
  "id": "sha256_hash_value",
  "value": "string to analyze",
  "properties": {
    "length": 16,
    "is_palindrome": false,
    "unique_characters": 12,
    "word_count": 3,
    "sha256_hash": "abc123...",
    "character_frequency_map": { "s": 2, "t": 3, "r": 2 }
  },
  "created_at": "2025-08-27T10:00:00Z"
}
```

Errors

- 409 Conflict — string already exists
- 400 Bad Request — invalid JSON or missing `value`
- 422 Unprocessable Entity — `value` has wrong type (must be string)

### 2- Get Specific String

GET /strings/{string_value}

Success (200 OK)

```json
{
  "id": "sha256_hash_value",
  "value": "requested string",
  "properties": {
    /* same as above */
  },
  "created_at": "2025-08-27T10:00:00Z"
}
```

Errors

- 404 Not Found — string not found

### 3- Get All Strings (with filtering)

GET /strings

Supported query parameters (all optional):

- `is_palindrome` (true/false)
- `min_length` (integer)
- `max_length` (integer)
- `word_count` (integer)
- `contains_character` (single character string)

Example request

/strings?is_palindrome=true&min_length=5&max_length=20&word_count=2&contains_character=a

Success (200 OK)

```json
{
  "data": [
    /* array of string objects */
  ],
  "count": 15,
  "filters_applied": {
    "is_palindrome": true,
    "min_length": 5,
    "max_length": 20,
    "word_count": 2,
    "contains_character": "a"
  }
}
```

Errors

- 400 Bad Request — invalid query parameter values or types

### 4- Natural Language Filtering

GET /strings/filter-by-natural-language?query=<url-encoded-query>

This endpoint should accept a natural language query, parse it into filter criteria, run the filter, and return results along with the interpreted query.

Example

Request:

GET /strings/filter-by-natural-language?query=all%20single%20word%20palindromic%20strings

Success (200 OK)

```json
{
  "data": [
    /* matching strings */
  ],
  "count": 3,
  "interpreted_query": {
    "original": "all single word palindromic strings",
    "parsed_filters": { "word_count": 1, "is_palindrome": true }
  }
}
```

Example natural-language → filter mappings to support (suggested):

- "all single word palindromic strings" → `word_count=1`, `is_palindrome=true`
- "strings longer than 10 characters" → `min_length=11`
- "palindromic strings that contain the first vowel" → `is_palindrome=true`, `contains_character=a` (or similar heuristic)
- "strings containing the letter z" → `contains_character=z`

Errors

- 400 Bad Request — unable to parse the natural language query
- 422 Unprocessable Entity — query parsed but filters conflict

### 5- Delete String

DELETE /strings/{string_value}

Success (204 No Content)

Errors

- 404 Not Found — string not found

## Implementation / Submission instructions

- You may implement this in any language or framework.
- Hosting: Vercel is not allowed for this cohort. Also avoid Render. Acceptable hosts include Railway, Heroku, AWS, PXXL App, etc.
- Include in your GitHub repository:
  - a clear `README.md` with setup and run instructions
  - list of dependencies and install steps
  - environment variables (if any) and how to set them
  - basic tests or API examples to validate endpoints

Submission process (use the Stage 1 bot in Slack)

1. Verify your server is reachable (test from multiple networks if possible).
2. Go to the `#stage-1-backend` Slack channel.
3. Run the command: `/stage-one-backend` and provide:
   - Your API base URL (e.g. `https://yourapp.domain.app`)
   - Your GitHub repo link
   - Your full name
   - Your email
   - Your stack

Note: Check the Thanos bot in Slack for success/error messages after submission attempts.

## Deadline

Wednesday, 22 Oct 2025 • 23:59 (GMT+1 / WAT)

Good luck, Backend Wizards!:
