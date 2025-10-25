import os
import sys
import shutil
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from app import models
from app.services.fetch_data import refresh_data
from app.services.image_generator import generate_summary_image
from app.config import settings


class DummyResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def make_in_memory_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_refresh_data_inserts_and_updates(monkeypatch):
    # Prepare fake country data and exchange rates
    countries = [
        {"name": "Testland", "capital": "Test City", "region": "Test Region", "population": 1000, "flag": "http://flag", "currencies": [{"code": "TST"}]},
        {"name": "Nocurr", "capital": "None", "region": "Nowhere", "population": 500, "flag": None, "currencies": []},
    ]

    rates = {"TST": 2.0}

    def fake_get(url, timeout=10):
        if "restcountries" in url:
            return DummyResponse(countries)
        if "open.er-api" in url:
            return DummyResponse({"rates": rates})
        raise RuntimeError("Unexpected URL")

    monkeypatch.setattr("requests.get", fake_get)

    db = make_in_memory_db()
    success = refresh_data(db)
    assert success is True

    # Verify records
    all_countries = db.query(models.Country).all()
    assert len(all_countries) == 2

    t = db.query(models.Country).filter(models.Country.name == "Testland").first()
    assert t is not None
    assert t.currency_code == "TST"
    assert t.exchange_rate == 2.0
    assert t.estimated_gdp is not None

    n = db.query(models.Country).filter(models.Country.name == "Nocurr").first()
    assert n is not None
    assert n.currency_code is None
    assert n.exchange_rate is None
    assert n.estimated_gdp == 0 or n.estimated_gdp is None


def test_refresh_data_external_api_failure(monkeypatch):
    def broken_get(url, timeout=10):
        raise RuntimeError("api down")

    monkeypatch.setattr("requests.get", broken_get)
    db = make_in_memory_db()
    success = refresh_data(db)
    assert success is False


def test_image_generation_creates_file(tmp_path):
    # use simple objects with attributes
    class C:
        def __init__(self, name, estimated_gdp):
            self.name = name
            self.estimated_gdp = estimated_gdp

    top = [C("A", 1000), C("B", 900)]
    # generate image at project cache dir
    generate_summary_image(top, total=2, timestamp="now")
    summary_path = settings.BASE_DIR / "cache" / "summary.png"
    assert summary_path.exists()
    # cleanup
    if summary_path.exists():
        summary_path.unlink()
        cache_dir = summary_path.parent
        try:
            shutil.rmtree(cache_dir)
        except Exception:
            pass
