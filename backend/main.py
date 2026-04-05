"""OSINT War Monitoring Dashboard - FastAPI Application."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import BASE_DIR, DATA_DIR, FRONTEND_URL, MEDIA_DIR
from database import init_db
from routers import config_router, news, telegram, ws, summary, x
from workers.scheduler import start_background_tasks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

_background_tasks = []

# ── Frontend paths ────────────────────────────────────────────────────────────
_FRONTEND_DIR = BASE_DIR / "static_frontend"
_ASSETS_DIR = _FRONTEND_DIR / "assets"
_PUBLIC_FILES: set = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    await init_db()

    # Ensure directories exist
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    # Discover frontend public files at startup
    global _PUBLIC_FILES
    if _FRONTEND_DIR.exists():
        _PUBLIC_FILES = {f.name for f in _FRONTEND_DIR.iterdir() if f.is_file()}
        logger.info(f"Frontend dir: {_FRONTEND_DIR}, files: {_PUBLIC_FILES}")
    else:
        logger.warning(f"Frontend dir NOT found: {_FRONTEND_DIR}")

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

# Mount /assets only if the build exists
if _ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(_ASSETS_DIR)), name="assets")

# Routers
app.include_router(news.router)
app.include_router(telegram.router)
app.include_router(summary.router)
app.include_router(config_router.router)
app.include_router(x.router)
app.include_router(ws.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "osint-dashboard"}


@app.get("/api/debug")
async def debug():
    """Diagnostic endpoint — shows whether frontend is found."""
    return {
        "frontend_dir": str(_FRONTEND_DIR),
        "exists": _FRONTEND_DIR.exists(),
        "index_exists": (_FRONTEND_DIR / "index.html").exists(),
        "base_dir": str(BASE_DIR),
        "public_files": list(_PUBLIC_FILES) if _PUBLIC_FILES else [],
    }


# ── SPA fallback: catch ANY 404 and serve index.html for non-API paths ───────
@app.exception_handler(StarletteHTTPException)
async def spa_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        path = request.url.path
        # Only serve SPA for non-API, non-static paths
        if not path.startswith(("/api/", "/media/", "/assets/", "/ws")):
            index = _FRONTEND_DIR / "index.html"
            if index.exists():
                # Serve a known public file (favicon, etc.)
                name = path.lstrip("/")
                if name in _PUBLIC_FILES:
                    return FileResponse(str(_FRONTEND_DIR / name))
                return FileResponse(str(index))
            return JSONResponse(
                {"error": "Frontend not built", "dir": str(_FRONTEND_DIR)},
                status_code=503,
            )
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
