import os
import asyncio
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

# Ensure .env is loaded, then FORCE SQLite for tests regardless of .env
load_dotenv()
# Hard override: always use SQLite for tests to avoid asyncpg/event loop issues on Windows
os.environ["TEST_DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]


# Use a single event loop for all async tests to avoid cross-loop issues with asyncpg/SQLAlchemy
@pytest.fixture(scope="session")
def event_loop():
    # Use a selector event loop on Windows to avoid Proactor issues with aiosqlite/asyncpg
    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


# Initialize the database schema once per test session to avoid per-test engine churn
@pytest.fixture(scope="session", autouse=True)
def _init_db_once(event_loop):
    # Ensure a clean SQLite database file for each test session to avoid cross-test pollution
    try:
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test.db"))
        if os.path.exists(db_path):
            os.remove(db_path)
    except Exception:
        pass

    # Delay import until after environment and loop are configured
    from app import database
    event_loop.run_until_complete(database.init_db_async())
    yield


# Shared TestClient for convenience
@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c
