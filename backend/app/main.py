# app/main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db, close_db
# ✅ FIX #1: Import models explicitly so SQLAlchemy registers them with Base.metadata
# Without this, init_db() creates zero tables and every query fails.
from app.models import models as _models  # noqa: F401

from app.routers import players_router, matches_router, leaderboard_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    logger.info("🔥 Tekken Tournament System starting up...")
    await init_db()
    logger.info("✅ Database initialized")
    yield
    logger.info("🛑 Shutting down...")
    await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Real-time Tekken Tournament Management System for college esports events.",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ─── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Global Exception Handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred.", "success": False}
    )


# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(players_router, prefix="/api")
app.include_router(matches_router, prefix="/api")
app.include_router(leaderboard_router, prefix="/api")


# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["System"])
async def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


# ─── Serve Frontend Static Files ──────────────────────────────────────────────

try:
    app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
except Exception:
    logger.warning("Frontend static files not found. API-only mode.")
