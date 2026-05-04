from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .api.preview import router as preview_router
from .api.push import router as push_router

app = FastAPI(
    title="Connect Buddy",
    description="Push structured workouts to Garmin Connect",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(preview_router)
app.include_router(push_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error_type": "server_error",
            "message": str(exc),
        },
    )


_frontend_dir = Path(__file__).parent.parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="static")
