import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_countries_image_404_json():
    # Ensure no lingering cache file
    if os.path.exists("cache/summary.png"):
        os.remove("cache/summary.png")

    r = client.get("/countries/image")
    assert r.status_code == 404
    assert r.headers.get("content-type", "").startswith("application/json")
    body = r.json()
    assert body.get("error") == "Summary image not found"


def test_root_ok():
    r = client.get("/")
    assert r.status_code == 200
    assert "message" in r.json()
