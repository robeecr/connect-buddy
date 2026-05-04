from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)
FIXTURES = Path(__file__).parent / "fixtures"


def upload(filename: str, content_type: str = "application/octet-stream"):
    path = FIXTURES / filename
    with open(path, "rb") as f:
        return client.post(
            "/api/convert",
            files={"file": (filename, f, content_type)},
        )


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


# ── Valid JSON → 200 + FIT binary ─────────────────────────────────────────────

def test_convert_valid_cycling_json():
    r = upload("valid_cycling.json", "application/json")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/octet-stream"
    assert len(r.content) > 100
    # FIT magic bytes
    assert r.content[8:12] == b".FIT"


def test_convert_valid_running_json():
    r = upload("valid_running.json", "application/json")
    assert r.status_code == 200
    assert r.content[8:12] == b".FIT"


def test_convert_sets_content_disposition():
    r = upload("valid_cycling.json", "application/json")
    disposition = r.headers.get("content-disposition", "")
    assert "attachment" in disposition
    assert ".fit" in disposition.lower()


# ── Valid XML → 200 + FIT binary ──────────────────────────────────────────────

def test_convert_valid_xml():
    r = upload("valid_cycling.xml", "application/xml")
    assert r.status_code == 200
    assert r.content[8:12] == b".FIT"


# ── Invalid JSON → 422 with error detail ─────────────────────────────────────

def test_convert_invalid_missing_steps_returns_422():
    r = upload("invalid_missing_steps.json", "application/json")
    assert r.status_code == 422
    body = r.json()
    detail = body.get("detail", body)
    assert detail.get("error_type") == "validation"
    assert len(detail.get("errors", [])) > 0


def test_convert_invalid_bad_duration_returns_422():
    r = upload("invalid_bad_duration.json", "application/json")
    assert r.status_code == 422
    body = r.json()
    detail = body.get("detail", body)
    assert detail.get("error_type") == "validation"
    errors = detail.get("errors", [])
    assert any("value_s" in e.get("path", "") or "86400" in e.get("message", "") for e in errors)


def test_convert_malformed_json_returns_422():
    r = client.post(
        "/api/convert",
        files={"file": ("bad.json", b"{not valid json", "application/json")},
    )
    assert r.status_code == 422


# ── Unsupported extension → 415 ───────────────────────────────────────────────

def test_convert_csv_returns_415():
    r = client.post(
        "/api/convert",
        files={"file": ("workout.csv", b"a,b,c", "text/csv")},
    )
    assert r.status_code == 415


def test_convert_no_extension_returns_415():
    r = client.post(
        "/api/convert",
        files={"file": ("workout", b"{}", "application/octet-stream")},
    )
    assert r.status_code == 415


# ── Garmin Connect REST format ────────────────────────────────────────────────

def test_convert_garmin_connect_json_returns_fit():
    r = upload("garmin_connect_intervals.json", "application/json")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/octet-stream"
    assert r.content[8:12] == b".FIT"


def test_convert_garmin_connect_filename_uses_workout_name():
    r = upload("garmin_connect_intervals.json", "application/json")
    disposition = r.headers.get("content-disposition", "")
    assert "5K_Intervals" in disposition


def test_convert_garmin_connect_repeat_produces_valid_fit():
    # 3 repeats of (interval + recovery) + warmup + cooldown = 8 steps
    # Verifies repeat expansion doesn't crash encoding
    r = upload("garmin_connect_intervals.json", "application/json")
    assert r.status_code == 200
    assert len(r.content) > 100


# ── Download filename sanitisation ────────────────────────────────────────────

def test_filename_in_response_is_safe():
    r = upload("valid_cycling.json", "application/json")
    disposition = r.headers.get("content-disposition", "")
    # Should only contain safe characters
    import re
    match = re.search(r'filename="?([^"]+)"?', disposition)
    assert match
    fname = match.group(1)
    assert all(c.isalnum() or c in "-_." for c in fname), f"Unsafe filename: {fname}"
