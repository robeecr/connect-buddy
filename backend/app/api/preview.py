from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from ..core.garmin_connect_parser import is_garmin_connect_format, parse_garmin_connect
from ..core.models import (
    DurationCalories,
    DurationDistance,
    DurationHrGreaterThan,
    DurationHrLessThan,
    DurationOpen,
    DurationReps,
    DurationTime,
    RepeatBlock,
    TargetCadence,
    TargetHeartRateCustom,
    TargetHeartRateZone,
    TargetOpen,
    TargetPace,
    TargetPowerCustom,
    TargetPowerZone,
    TargetSpeed,
    WorkoutDefinition,
)
from ..core.schema_validator import validate_json, validate_xml

router = APIRouter(prefix="/api")

_SUPPORTED_EXTENSIONS = {".json", ".xml"}


def _fmt_duration(dur) -> str:
    if isinstance(dur, DurationTime):
        s = int(dur.value_s)
        return f"{s // 60}:{s % 60:02d}"
    if isinstance(dur, DurationDistance):
        m = dur.value_m
        return f"{m / 1000:.2f} km" if m >= 1000 else f"{int(m)} m"
    if isinstance(dur, DurationCalories):
        return f"{dur.value_kcal} kcal"
    if isinstance(dur, DurationHrLessThan):
        return f"HR < {dur.value_bpm} bpm"
    if isinstance(dur, DurationHrGreaterThan):
        return f"HR > {dur.value_bpm} bpm"
    if isinstance(dur, DurationReps):
        return f"{dur.value_reps} reps"
    return "Open"


def _pace_str(ms: float) -> str:
    if ms <= 0:
        return "–"
    secs = round(1000 / ms)
    return f"{secs // 60}:{secs % 60:02d}"


def _fmt_target(target) -> str:
    if target is None or isinstance(target, TargetOpen):
        return ""
    if isinstance(target, TargetPace):
        # high_ms = faster speed = lower sec/km (shown first)
        return f"{_pace_str(target.high_ms)}–{_pace_str(target.low_ms)} /km"
    if isinstance(target, TargetSpeed):
        lo = target.low_ms * 0.06
        hi = target.high_ms * 0.06
        return f"{lo:.2f}–{hi:.2f} km/min"
    if isinstance(target, TargetHeartRateZone):
        return f"HR Zone {target.zone}"
    if isinstance(target, TargetHeartRateCustom):
        return f"{target.low_bpm}–{target.high_bpm} bpm"
    if isinstance(target, TargetPowerZone):
        return f"Power Zone {target.zone}"
    if isinstance(target, TargetPowerCustom):
        return f"{target.low_watts}–{target.high_watts} W"
    if isinstance(target, TargetCadence):
        return f"{target.low_rpm}–{target.high_rpm} rpm"
    return ""


@router.post("/preview")
async def preview_workout(file: UploadFile) -> JSONResponse:
    filename = file.filename or ""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""

    if ext not in _SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail={"message": f"File must be .json or .xml. Received: {ext or 'unknown'}"},
        )

    raw = await file.read()

    if ext == ".json":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail={"message": f"Invalid JSON: {exc}"})
        if is_garmin_connect_format(data):
            try:
                data = parse_garmin_connect(data)
            except Exception as exc:
                raise HTTPException(status_code=422, detail={"message": f"Parse error: {exc}"})
        else:
            errors = validate_json(data)
            if errors:
                raise HTTPException(status_code=422, detail={"errors": errors})
    else:
        data, errors = validate_xml(raw)
        if errors:
            raise HTTPException(status_code=422, detail={"errors": errors})

    try:
        workout = WorkoutDefinition(**data)
    except ValidationError as exc:
        errors = [
            {"path": " → ".join(str(loc) for loc in e["loc"]), "message": e["msg"]}
            for e in exc.errors()
        ]
        raise HTTPException(status_code=422, detail={"errors": errors})

    items = []
    for item in workout.steps:
        if isinstance(item, RepeatBlock):
            items.append({
                "type": "repeat",
                "iterations": item.iterations,
                "steps": [
                    {
                        "name": s.name,
                        "intensity": s.intensity,
                        "duration": _fmt_duration(s.duration),
                        "target": _fmt_target(s.target),
                    }
                    for s in item.steps
                ],
            })
        else:
            items.append({
                "name": item.name,
                "intensity": item.intensity,
                "duration": _fmt_duration(item.duration),
                "target": _fmt_target(item.target),
            })

    return JSONResponse({"name": workout.name, "sport": workout.sport, "steps": items})
