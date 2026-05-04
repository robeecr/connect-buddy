from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response

from ..core.garmin_connect_parser import is_garmin_connect_format, parse_garmin_connect
from ..core.models import WorkoutDefinition
from ..core.schema_validator import validate_json, validate_xml
from ..core.workout_encoder import encode_workout

router = APIRouter(prefix="/api")

_SUPPORTED_EXTENSIONS = {".json", ".xml"}
_SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "workout.schema.json"


@router.post("/convert")
async def convert_workout(file: UploadFile) -> Response:
    filename = file.filename or ""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""

    if ext not in _SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail={
                "status": "error",
                "error_type": "unsupported_format",
                "message": f"File must be .json or .xml. Received: {ext or 'unknown'}",
            },
        )

    raw = await file.read()

    if ext == ".json":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "status": "error",
                    "error_type": "validation",
                    "errors": [{"path": "$", "message": f"Invalid JSON: {exc}", "schema_path": ""}],
                },
            )
        if is_garmin_connect_format(data):
            try:
                data = parse_garmin_connect(data)
            except Exception as exc:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "status": "error",
                        "error_type": "validation",
                        "errors": [{"path": "$", "message": f"Garmin Connect parse error: {exc}", "schema_path": ""}],
                    },
                )
        else:
            errors = validate_json(data)
            if errors:
                raise HTTPException(
                    status_code=422,
                    detail={"status": "error", "error_type": "validation", "errors": errors},
                )
        workout = WorkoutDefinition(**data)

    else:  # .xml
        data, errors = validate_xml(raw)
        if errors:
            raise HTTPException(
                status_code=422,
                detail={"status": "error", "error_type": "validation", "errors": errors},
            )
        workout = WorkoutDefinition(**data)

    try:
        fit_bytes = encode_workout(workout)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "error_type": "encoding_error",
                "message": f"FIT encoding failed: {exc}",
            },
        )

    safe_name = "".join(c if (c.isalnum() or c in "-_") else "_" for c in workout.name)
    download_name = f"workout_{safe_name}.fit"

    return Response(
        content=fit_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@router.get("/schema")
async def get_schema() -> JSONResponse:
    return JSONResponse(json.loads(_SCHEMA_PATH.read_text(encoding="utf-8")))


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}
