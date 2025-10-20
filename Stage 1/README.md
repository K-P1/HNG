# String Analyzer API

A RESTful API built with **FastAPI** that analyzes strings, computes their properties, and supports both structured and natural language filtering.

**Live URL:** [https://hng-production-2739.up.railway.app](https://hng-production-2739.up.railway.app)
**GitHub Repository:** [https://github.com/K-P1/HNG](https://github.com/K-P1/HNG.git)

---

## Features

* Analyze any string and retrieve detailed properties
* Filter results using query parameters or natural language
* Fast, lightweight in-memory storage
* Automatically computes:

  * Length
  * Palindrome status
  * Unique characters
  * Word count
  * SHA-256 hash
  * Character frequency map

---

## Tech Stack

* **Framework:** FastAPI
* **Server:** Uvicorn
* **Language:** Python 3.9+
* **Validation:** Pydantic
* **Testing:** Pytest, HTTPX

---

## Setup and Run

```bash
# Clone the repository
git clone https://github.com/K-P1/HNG.git
cd "Stage 1"

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate  # Windows
source venv/bin/activate # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn app.main:app --reload
```

**Local URL:** [http://localhost:8000](http://localhost:8000)
**Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Endpoints Overview

| Method | Endpoint                              | Description                             |
| ------ | ------------------------------------- | --------------------------------------- |
| GET    | `/health`                             | Health check                            |
| POST   | `/strings`                            | Analyze and store a string              |
| GET    | `/strings`                            | Get all strings (with optional filters) |
| GET    | `/strings/{string_value}`             | Get one by value                        |
| DELETE | `/strings/{string_value}`             | Delete a string                         |
| GET    | `/strings/filter-by-natural-language` | Query via natural language              |

---

### Natural Language Examples

| Example Query                       | Parsed Filters                     |
| ----------------------------------- | ---------------------------------- |
| `palindromic strings`               | `is_palindrome=true`               |
| `strings longer than 10 characters` | `min_length=11`                    |
| `single word palindromes`           | `word_count=1, is_palindrome=true` |
| `strings containing z`              | `contains_character=z`             |

---

## Computed Properties

| Property                  | Description                     |
| ------------------------- | ------------------------------- |
| `length`                  | Number of characters            |
| `is_palindrome`           | True if reads the same backward |
| `unique_characters`       | Number of distinct characters   |
| `word_count`              | Number of space-separated words |
| `sha256_hash`             | Unique hash identifier          |
| `character_frequency_map` | Frequency of each character     |

---

## Project Structure

```
app/
├── main.py          # FastAPI app
├── routes.py        # API endpoints
├── services.py      # Core logic
├── schemas.py       # Pydantic models
├── db.py            # In-memory storage
└── NLP.py           # Natural language parser
tests/
├── test_endpoints.py
├── test_nlp.py
└── test_services.py
```

---

## Testing

```bash
pytest -q
pytest --cov=app
```

---

## Deployment

Hosted on **Railway**
**Base URL:** [https://hng-production-2739.up.railway.app](https://hng-production-2739.up.railway.app)

Supported: **Railway**, **Heroku**, **AWS**, **PXXL App**
Not supported: **Vercel**, **Render**

---

## Notes

* Palindrome checks are case-insensitive
* Data resets on restart (in-memory)
* Natural language queries use regex-based parsing
* Best suited for testing, learning, and demos

---

### Author

**Hamed Ayokunle Suleiman (Kunle)**
Python Backend Engineer | FastAPI Developer
Built for **HNG Backend Wizards — Stage 1**
