import io
import json
import struct
from pathlib import Path

from app.core.models import WorkoutDefinition
from app.core.workout_encoder import encode_workout

FIXTURES = Path(__file__).parent / "fixtures"
FIXED_TS = 1_325_376_000_000  # 2012-01-01 00:00:00 UTC in Unix milliseconds (deterministic)


def load(name: str) -> WorkoutDefinition:
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return WorkoutDefinition(**data)


# ── Determinism ────────────────────────────────────────────────────────────────

def test_determinism_cycling():
    w = load("valid_cycling.json")
    assert encode_workout(w, timestamp=FIXED_TS) == encode_workout(w, timestamp=FIXED_TS)


def test_determinism_running():
    w = load("valid_running.json")
    assert encode_workout(w, timestamp=FIXED_TS) == encode_workout(w, timestamp=FIXED_TS)


def test_different_timestamps_differ():
    w = load("valid_cycling.json")
    b1 = encode_workout(w, timestamp=FIXED_TS)
    b2 = encode_workout(w, timestamp=FIXED_TS + 1000)  # 1 second apart
    assert b1 != b2


# ── Output type & size ─────────────────────────────────────────────────────────

def test_returns_bytes_or_bytearray():
    result = encode_workout(load("valid_cycling.json"), timestamp=FIXED_TS)
    assert isinstance(result, (bytes, bytearray))


def test_output_non_empty():
    result = encode_workout(load("valid_cycling.json"), timestamp=FIXED_TS)
    assert len(result) > 12  # at minimum > smallest valid FIT header


def test_running_output_non_empty():
    result = encode_workout(load("valid_running.json"), timestamp=FIXED_TS)
    assert len(result) > 12


# ── FIT binary structure ───────────────────────────────────────────────────────

def test_fit_header_length_byte():
    result = bytes(encode_workout(load("valid_cycling.json"), timestamp=FIXED_TS))
    # FIT protocol 1.0 uses 12-byte header; protocol 2.0 uses 14-byte header
    assert result[0] in (12, 14), f"Expected FIT header length 12 or 14, got {result[0]}"


def test_fit_header_data_type():
    result = bytes(encode_workout(load("valid_cycling.json"), timestamp=FIXED_TS))
    # Bytes 8-11 are ASCII ".FIT"
    assert result[8:12] == b".FIT", f"FIT header magic missing, got {result[8:12]!r}"


def test_fit_file_length():
    """FIT header byte[0] + data_size (bytes 4-7 LE uint32) + 2-byte CRC = total file length."""
    result = bytes(encode_workout(load("valid_cycling.json"), timestamp=FIXED_TS))
    header_len = result[0]
    data_size  = struct.unpack_from("<I", result, 4)[0]
    expected   = header_len + data_size + 2  # +2 for file CRC
    assert len(result) == expected, (
        f"File length mismatch: got {len(result)}, expected {expected}"
    )


# ── Round-trip decode ──────────────────────────────────────────────────────────

def test_roundtrip_cycling():
    original = load("valid_cycling.json")
    fit_bytes = bytes(encode_workout(original, timestamp=FIXED_TS))
    _assert_roundtrip(fit_bytes, original)


def test_roundtrip_running():
    original = load("valid_running.json")
    fit_bytes = bytes(encode_workout(original, timestamp=FIXED_TS))
    _assert_roundtrip(fit_bytes, original)


def _assert_roundtrip(fit_bytes: bytes, original: WorkoutDefinition):
    from garmin_fit_sdk import Decoder, Stream

    stream = Stream.from_bytes_io(io.BytesIO(fit_bytes))
    decoder = Decoder(stream)
    messages, errors = decoder.read()

    assert not errors, f"FIT decode errors: {errors}"
    assert "workout_mesgs" in messages, "No workout message in decoded FIT"
    assert "workout_step_mesgs" in messages, "No workout_step messages in decoded FIT"

    wkt = messages["workout_mesgs"][0]
    decoded_name = wkt.get("wkt_name") or wkt.get("workout_name") or wkt.get("name")
    assert decoded_name == original.name, f"Workout name mismatch: decoded={decoded_name!r}, expected={original.name!r}"
    assert len(messages["workout_step_mesgs"]) == len(original.steps), (
        f"Step count mismatch: decoded {len(messages['workout_step_mesgs'])}, "
        f"expected {len(original.steps)}"
    )


# ── Step count in workout message ──────────────────────────────────────────────

def test_num_valid_steps_field():
    """num_valid_steps in workout message must equal actual step count."""
    from garmin_fit_sdk import Decoder, Stream

    original = load("valid_cycling.json")
    fit_bytes = bytes(encode_workout(original, timestamp=FIXED_TS))

    stream = Stream.from_bytes_io(io.BytesIO(fit_bytes))
    decoder = Decoder(stream)
    messages, _ = decoder.read()

    wkt = messages["workout_mesgs"][0]
    assert wkt.get("num_valid_steps") == len(original.steps)
