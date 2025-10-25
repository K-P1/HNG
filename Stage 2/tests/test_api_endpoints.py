import os
import sys
from typing import Callable, Iterator

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db
from app import models
from app.config import settings


def make_test_db():
    # Use StaticPool to keep a single in-memory DB across threads/requests
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


def override_get_db(SessionLocal) -> Callable[[], Iterator]:
    def _get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    return _get_db


def seed_countries(session):
    data = [
        models.Country(
            name="Alpha",
            capital="A",
            region="Africa",
            population=100,
            currency_code="AAA",
            exchange_rate=2.0,
            estimated_gdp=1000.0,
            flag_url=None,
        ),
        models.Country(
            name="Bravo",
            capital="B",
            region="Europe",
            population=200,
            currency_code="BBB",
            exchange_rate=1.5,
            estimated_gdp=500.0,
            flag_url=None,
        ),
        models.Country(
            name="Charlie",
            capital="C",
            region="africa",
            population=300,
            currency_code="bbb",
            exchange_rate=3.0,
            estimated_gdp=1500.0,
            flag_url=None,
        ),
    ]
    for c in data:
        session.add(c)
    session.commit()


def test_filters_sorts_and_pagination(monkeypatch):
    engine, SessionLocal = make_test_db()
    app.dependency_overrides[get_db] = override_get_db(SessionLocal)
    with SessionLocal() as s:
        seed_countries(s)

    client = TestClient(app)

    # Case-insensitive region filter
    r = client.get("/countries", params={"region": "AFRICA"})
    assert r.status_code == 200
    names = [c["name"] for c in r.json()]
    assert set(names) == {"Alpha", "Charlie"}

    # Case-insensitive currency filter
    r = client.get("/countries", params={"currency": "BBB"})
    assert r.status_code == 200
    names = [c["name"] for c in r.json()]
    assert set(names) == {"Bravo", "Charlie"}

    # Sorting by GDP desc
    r = client.get("/countries", params={"sort": "gdp_desc"})
    assert r.status_code == 200
    names = [c["name"] for c in r.json()]
    assert names[:3] == ["Charlie", "Alpha", "Bravo"]

    # Pagination limit/offset
    r = client.get("/countries", params={"sort": "name_asc", "limit": 1, "offset": 1})
    assert r.status_code == 200
    names = [c["name"] for c in r.json()]
    assert names == ["Bravo"]


def test_country_not_found_error_shape(monkeypatch):
    engine, SessionLocal = make_test_db()
    app.dependency_overrides[get_db] = override_get_db(SessionLocal)
    client = TestClient(app)

    r = client.get("/countries/does-not-exist")
    assert r.status_code == 404
    body = r.json()
    assert body.get("error") == "Country not found"


def test_refresh_failure_503_error_shape(monkeypatch):
    # Override DB
    engine, SessionLocal = make_test_db()
    app.dependency_overrides[get_db] = override_get_db(SessionLocal)

    # Force refresh_data to fail
    from app.routes import countries as routes_countries
    monkeypatch.setattr("app.services.fetch_data.refresh_data", lambda db: False)

    client = TestClient(app)
    r = client.post("/countries/refresh")
    assert r.status_code == 503
    assert r.json().get("error") == "External data source unavailable"


def test_refresh_success_generates_image(monkeypatch, tmp_path):
    # Override DB
    engine, SessionLocal = make_test_db()
    app.dependency_overrides[get_db] = override_get_db(SessionLocal)

    # Fake refresh success and ensure we don't rely on real external APIs
    monkeypatch.setattr("app.services.fetch_data.refresh_data", lambda db: True)

    # Seed at least one country so image generator has content
    with SessionLocal() as s:
        seed_countries(s)

    client = TestClient(app)
    r = client.post("/countries/refresh")
    assert r.status_code == 200
    # Image path should exist or at least be created by generator under project cache
    summary_path = settings.BASE_DIR / "cache" / "summary.png"
    assert summary_path.exists()
    # cleanup
    if summary_path.exists():
        summary_path.unlink()
        try:
            summary_path.parent.rmdir()
        except Exception:
            pass
