from datetime import datetime

def test_me_success(monkeypatch, client):
	async def fake_fetch(timeout_seconds=None):
		return "Cats purr to communicate contentment."

	monkeypatch.setattr("app.routes.fetch_cat_fact", fake_fetch)

	resp = client.get("/me")
	assert resp.status_code == 200
	data = resp.json()
	assert data["status"] == "success"
	assert "fact" in data and data["fact"] == "Cats purr to communicate contentment."
	assert data["user"]["stack"] == "Python/FastAPI"

def test_me_fallback(monkeypatch, client):
	async def failing_fetch(timeout_seconds=None):
		return "Could not fetch a cat fact at this time."

	monkeypatch.setattr("app.routes.fetch_cat_fact", failing_fetch)

	resp = client.get("/me")
	assert resp.status_code == 200
	data = resp.json()
	assert data["status"] in ("error", "success")
	assert "fact" in data

def test_me_headers_and_timestamp(client, monkeypatch):
    async def fake_fetch(timeout_seconds=None):
        return "Cats have five toes on their front paws."

    monkeypatch.setattr("app.routes.fetch_cat_fact", fake_fetch)

    resp = client.get("/me")
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("application/json")

    data = resp.json()
    ts = data.get("timestamp")
    assert isinstance(ts, str)
    assert "T" in ts and ts.endswith("Z")
    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
