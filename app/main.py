"""
app/main.py
─────────────────────────────────────────────
FastAPI application entry point.
Wires up routers, CORS, lifespan (DB connect/disconnect),
and the root health-check endpoint.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import generate, status
from app.services.job_store import init_db, close_db
from app.logger import get_logger
from app.config import settings

logger = get_logger(__name__)


# ── Lifespan: runs on startup and shutdown ─────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info({"event": "startup", "env": settings.app_env})
    init_db()
    yield
    close_db()
    logger.info({"event": "shutdown"})


# ── App factory ────────────────────────────────────────────
app = FastAPI(
    title="ViralGen AI",
    description=(
        "Asynchronous multi-modal social media ad content generator. "
        "Submit a brief, get brand-voice-optimized copy + AI image across "
        "LinkedIn, Instagram, Twitter/X, and Facebook."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS (open for dev) ────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────
app.include_router(generate.router)
app.include_router(status.router)


# ── Health check ───────────────────────────────────────────
@app.get("/health", tags=["meta"], summary="Health check")
async def health() -> dict:
    return {
        "status": "ok",
        "version": "0.1.0",
        "env": settings.app_env,
    }
