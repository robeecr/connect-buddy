from __future__ import annotations

import asyncio
import hashlib
import logging
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, HTTPException
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)
from pydantic import BaseModel

from ..core.garmin_connect_parser import is_garmin_connect_format, parse_garmin_connect
from ..core.models import WorkoutDefinition
from ..core.schema_validator import validate_json
from ..core.workout_to_garmin import to_garmin_connect

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

_pool = ThreadPoolExecutor(max_workers=4)
_TOKEN_DIR = Path(tempfile.gettempdir()) / "connect_buddy_tokens"

_RATE_LIMIT_MSG = (
    "Garmin has temporarily blocked login attempts from this server due to too many "
    "requests. Please wait 15–30 minutes and try again — or try from a different network."
)


def _token_path(email: str) -> str:
    key = hashlib.sha256(email.lower().encode()).hexdigest()[:24]
    return str(_TOKEN_DIR / key)


def _is_rate_limited(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "rate limit" in msg or "too many" in msg


class PushRequest(BaseModel):
    email: str
    password: str
    workout: dict


class PreviewRequest(BaseModel):
    workout: dict



@router.post("/preview-push")
async def preview_push(req: PreviewRequest) -> dict:
    """Return the exact Garmin Connect payload that would be sent, without authenticating."""
    data = req.workout

    if is_garmin_connect_format(data):
        try:
            data = parse_garmin_connect(data)
        except Exception as exc:
            raise HTTPException(status_code=422, detail={"status": "error", "message": str(exc)})

    errors = validate_json(data)
    if errors:
        raise HTTPException(status_code=422, detail={"status": "error", "errors": errors})

    gc_payload = to_garmin_connect(WorkoutDefinition(**data))
    return {"status": "ok", "payload": gc_payload}


@router.post("/push")
async def push_workout(req: PushRequest) -> dict:
    data = req.workout

    if is_garmin_connect_format(data):
        # Normalise through our internal model so the upload payload has the
        # correct format (ExecutableStepDTO type tag, endCondition fields, IDs).
        try:
            data = parse_garmin_connect(data)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail={"status": "error", "error_type": "validation",
                        "errors": [{"path": "$", "message": str(exc), "schema_path": ""}]},
            )

    errors = validate_json(data)
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"status": "error", "error_type": "validation", "errors": errors},
        )
    gc_payload = to_garmin_connect(WorkoutDefinition(**data))

    try:
        result = await asyncio.get_running_loop().run_in_executor(
            _pool, _push_sync, req.email, req.password, gc_payload
        )
    except Exception as exc:
        exc_type = type(exc).__name__
        exc_msg = str(exc)
        logger.error("Push failed [%s]: %s", exc_type, exc_msg)

        # Check rate limit first regardless of exception type — the garminconnect
        # library sometimes wraps Garmin's 429 as GarminConnectAuthenticationError.
        if _is_rate_limited(exc):
            raise HTTPException(status_code=429, detail={
                "status": "error",
                "error_type": "rate_limit",
                "message": _RATE_LIMIT_MSG,
            })

        if isinstance(exc, GarminConnectTooManyRequestsError):
            raise HTTPException(status_code=429, detail={
                "status": "error",
                "error_type": "rate_limit",
                "message": _RATE_LIMIT_MSG,
            })

        if isinstance(exc, GarminConnectAuthenticationError):
            raise HTTPException(status_code=401, detail={
                "status": "error",
                "error_type": "auth",
                "message": "Invalid Garmin credentials. Check your email and password.",
            })

        if isinstance(exc, GarminConnectConnectionError):
            raise HTTPException(status_code=502, detail={
                "status": "error",
                "error_type": "connection",
                "message": "Could not reach Garmin Connect. Please try again later.",
            })

        raise HTTPException(status_code=500, detail={
            "status": "error",
            "error_type": "server_error",
            "message": "An unexpected error occurred. Please try again.",
        })

    workout_id = result.get("workoutId") if isinstance(result, dict) else None
    workout_name = (
        result.get("workoutName") if isinstance(result, dict)
        else gc_payload.get("workoutName", "Workout")
    )

    return {"status": "ok", "workout_id": workout_id, "workout_name": workout_name}


def _push_sync(email: str, password: str, workout: dict) -> dict:
    _TOKEN_DIR.mkdir(exist_ok=True)
    # retry_attempts=1 avoids hammering Garmin's login endpoint when it rejects us,
    # which accelerates the rate-limit ban.
    api = Garmin(email, password, retry_attempts=1)
    api.login(tokenstore=_token_path(email))
    return api.upload_workout(workout)
