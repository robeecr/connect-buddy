import json
from pathlib import Path

import pytest

from app.core.schema_validator import validate_json, validate_xml

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# ── Valid inputs ──────────────────────────────────────────────────────────────

def test_valid_cycling_passes():
    assert validate_json(load("valid_cycling.json")) == []


def test_valid_running_passes():
    assert validate_json(load("valid_running.json")) == []


def test_minimal_valid_passes():
    data = {
        "name": "Min",
        "sport": "running",
        "steps": [{"name": "Go", "intensity": "active", "duration": {"type": "open"}}],
    }
    assert validate_json(data) == []


# ── Required field errors ─────────────────────────────────────────────────────

def test_missing_steps_caught():
    errors = validate_json(load("invalid_missing_steps.json"))
    assert errors, "Expected at least one error"
    # jsonschema reports required violations with the field name in the message,
    # not in the path (path points to the parent object, not the missing key)
    all_text = " ".join(e["path"] + " " + e["message"] for e in errors)
    assert "steps" in all_text


def test_missing_name_caught():
    data = {
        "sport": "running",
        "steps": [{"name": "S", "intensity": "active", "duration": {"type": "open"}}],
    }
    errors = validate_json(data)
    assert any("name" in e["path"] or "name" in e["message"] for e in errors)


def test_missing_sport_caught():
    data = {
        "name": "Test",
        "steps": [{"name": "S", "intensity": "active", "duration": {"type": "open"}}],
    }
    errors = validate_json(data)
    assert errors


# ── Enum errors ────────────────────────────────────────────────────────────────

def test_invalid_sport_caught():
    data = {
        "name": "Test",
        "sport": "triathlon",
        "steps": [{"name": "S", "intensity": "active", "duration": {"type": "open"}}],
    }
    errors = validate_json(data)
    assert errors
    assert any("sport" in e["path"] or "triathlon" in e["message"] for e in errors)


def test_invalid_intensity_caught():
    data = {
        "name": "Test",
        "sport": "running",
        "steps": [{"name": "S", "intensity": "extreme", "duration": {"type": "open"}}],
    }
    errors = validate_json(data)
    assert errors


# ── Duration range errors ─────────────────────────────────────────────────────

def test_duration_over_max_caught():
    errors = validate_json(load("invalid_bad_duration.json"))
    assert errors
    # After expanding oneOf sub-errors the specific constraint message is surfaced
    all_text = " ".join(e["path"] + " " + e["message"] for e in errors)
    assert "value_s" in all_text or "86400" in all_text or "duration" in all_text


def test_duration_distance_negative_caught():
    data = {
        "name": "Test",
        "sport": "running",
        "steps": [{"name": "S", "intensity": "active", "duration": {"type": "distance", "value_m": -1}}],
    }
    errors = validate_json(data)
    assert errors


# ── Field length errors ────────────────────────────────────────────────────────

def test_name_too_long_caught():
    data = {
        "name": "A" * 17,
        "sport": "running",
        "steps": [{"name": "S", "intensity": "active", "duration": {"type": "open"}}],
    }
    errors = validate_json(data)
    assert errors


def test_step_name_too_long_caught():
    data = {
        "name": "Test",
        "sport": "running",
        "steps": [{"name": "A" * 17, "intensity": "active", "duration": {"type": "open"}}],
    }
    errors = validate_json(data)
    assert errors


# ── Target errors ──────────────────────────────────────────────────────────────

def test_hr_zone_out_of_range_caught():
    data = {
        "name": "Test",
        "sport": "running",
        "steps": [{
            "name": "S",
            "intensity": "active",
            "duration": {"type": "open"},
            "target": {"type": "heart_rate", "zone": 10},
        }],
    }
    errors = validate_json(data)
    assert errors


# ── XML validation ────────────────────────────────────────────────────────────

def test_valid_xml_passes():
    xml_bytes = (FIXTURES / "valid_cycling.xml").read_bytes()
    data, errors = validate_xml(xml_bytes)
    assert errors == []
    assert data is not None
    assert data["sport"] == "cycling"
    assert len(data["steps"]) == 4


def test_malformed_xml_caught():
    _, errors = validate_xml(b"<Workout><Name>Test</Name>")
    assert errors


def test_xml_invalid_sport_caught():
    xml = b"""<?xml version="1.0"?>
<Workout>
  <Name>Test</Name>
  <Sport>triathlon</Sport>
  <Steps><Step>
    <Name>S</Name><Intensity>active</Intensity>
    <Duration><Type>open</Type></Duration>
  </Step></Steps>
</Workout>"""
    _, errors = validate_xml(xml)
    assert errors


# ── Error format ──────────────────────────────────────────────────────────────

def test_error_has_required_keys():
    errors = validate_json(load("invalid_missing_steps.json"))
    for e in errors:
        assert "path" in e
        assert "message" in e
        assert "schema_path" in e
