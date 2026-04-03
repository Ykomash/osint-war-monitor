"""OSINT War Monitoring Dashboard - FastAPI Application."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import BASE_DIR, DATA_DIR, FRONTEND_URL, MEDIA_DIR
from database import init_db
from routers import config_router, news, telegram, ws, summary
from workers.scheduler import start_background_tasks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

_background_tasks = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    await init_db()

    # Ensure directories exist
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    # Start background tasks
    global _background_tasks
    _background_tasks = start_background_tasks()
    logger.info("OSINT Dashboard started")

    yield

    # Shutdown
    for task in _background_tasks:
        task.cancel()
    logger.info("OSINT Dashboard stopped")


app = FastAPI(
    title="OSINT War Monitoring Dashboard",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins so the Railway public URL works without extra config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure media dir exists at import time (before StaticFiles tries to validate it)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# Static files for media
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

# Routers
app.include_router(news.router)
app.include_router(telegram.router)
app.include_router(summary.router)
app.include_router(config_router.router)
app.include_router(ws.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "osint-dashboard"}


# ── Serve React frontend (production build) ──────────────────────────────────
_FRONTEND_DIR = BASE_DIR / "static_frontend"
if _FRONTEND_DIR.exists():
    # Serve Vite's /assets bundle (JS/CSS/images)
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIR / "assets")), name="assets")

    from fastapi.responses import FileResponse as _FileResponse

    # Catch-all: any non-API path returns index.html so React Router works
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        index = _FRONTEND_DIR / "index.html"
        return _FileResponse(str(index))

    logger.info(f"Serving frontend from {_FRONTEND_DIR}")
