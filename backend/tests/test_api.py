from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


# ── Health ─────────────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── Schema endpoint ────────────────────────────────────────────────────────────

def test_schema_endpoint_returns_json():
    r = client.get("/api/schema")
    assert r.status_code == 200
    schema = r.json()
    assert schema.get("title") == "ConnectBuddyWorkout"
    assert "properties" in schema
