"""
app/services/job_store.py
─────────────────────────────────────────────
Async MongoDB CRUD for job documents using Motor.
All operations target the 'jobs' collection in the configured DB.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import certifi
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings
from app.models.response_models import (
    JobStatus,
    StatusLogEntry,
    CopyVariant,
    Telemetry,
)
from app.logger import get_logger

logger = get_logger(__name__)

# ── MongoDB client (module-level singleton, initialized on startup) ──
_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


def init_db() -> None:
    """Call once at app startup to establish the Motor connection."""
    global _client, _db
    _client = AsyncIOMotorClient(
        settings.mongodb_uri,
        tlsCAFile=certifi.where(),      # Fixes SSL handshake on Windows/Python 3.12
        serverSelectionTimeoutMS=30000,
    )
    _db = _client[settings.mongodb_db_name]
    logger.info({"event": "mongodb_connected", "db": settings.mongodb_db_name})


def close_db() -> None:
    """Call on app shutdown to close the Motor connection."""
    global _client
    if _client:
        _client.close()
        logger.info({"event": "mongodb_disconnected"})


def _get_collection():
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db["jobs"]


# ── CRUD operations ────────────────────────────────────────

async def create_job(job_id: str, request_data: dict) -> None:
    """Insert a new PENDING job document."""
    now = datetime.now(timezone.utc)
    doc = {
        "job_id": job_id,
        "status": JobStatus.pending.value,
        "input": request_data,
        "refined_prompt": None,
        "variants": [],
        "image_url": None,
        "telemetry": None,
        "status_history": [
            {
                "status": JobStatus.pending.value,
                "message": "Job created and queued.",
                "timestamp": now,
            }
        ],
        "created_at": now,
        "completed_at": None,
    }
    await _get_collection().insert_one(doc)
    logger.info({"event": "job_created", "job_id": job_id})


async def update_job_status(
    job_id: str,
    status: JobStatus,
    message: str,
) -> None:
    """Append a status log entry and update the top-level status field."""
    now = datetime.now(timezone.utc)
    await _get_collection().update_one(
        {"job_id": job_id},
        {
            "$set": {"status": status.value},
            "$push": {
                "status_history": {
                    "status": status.value,
                    "message": message,
                    "timestamp": now,
                }
            },
        },
    )
    logger.info({"event": "job_status_updated", "job_id": job_id, "status": status.value})


async def update_refined_prompt(job_id: str, refined_prompt: str) -> None:
    """Persist the Prompt Refinement Agent output to the job document."""
    await _get_collection().update_one(
        {"job_id": job_id},
        {"$set": {"refined_prompt": refined_prompt}},
    )
    logger.info({"event": "refined_prompt_saved", "job_id": job_id, "length": len(refined_prompt)})


async def update_job_result(
    job_id: str,
    variants: list[CopyVariant],
    telemetry: Telemetry,
    image_url: Optional[str] = None,
) -> None:
    """Write the final result payload to the job document."""
    now = datetime.now(timezone.utc)
    await _get_collection().update_one(
        {"job_id": job_id},
        {
            "$set": {
                "status": JobStatus.success.value,
                "variants": [v.model_dump() for v in variants],
                "image_url": image_url,
                "telemetry": telemetry.model_dump(),
                "completed_at": now,
            },
            "$push": {
                "status_history": {
                    "status": JobStatus.success.value,
                    "message": f"Generated {len(variants)} copy variants successfully.",
                    "timestamp": now,
                }
            },
        },
    )
    logger.info({"event": "job_result_saved", "job_id": job_id, "variants": len(variants)})


async def mark_job_failed(job_id: str, error: str) -> None:
    """Mark a job as FAILED with an error message."""
    now = datetime.now(timezone.utc)
    await _get_collection().update_one(
        {"job_id": job_id},
        {
            "$set": {
                "status": JobStatus.failed.value,
                "completed_at": now,
            },
            "$push": {
                "status_history": {
                    "status": JobStatus.failed.value,
                    "message": f"Job failed: {error}",
                    "timestamp": now,
                }
            },
        },
    )
    logger.error({"event": "job_marked_failed", "job_id": job_id, "error": error})


async def get_job(job_id: str) -> Optional[dict]:
    """Retrieve a job document by job_id. Returns None if not found."""
    doc = await _get_collection().find_one({"job_id": job_id}, {"_id": 0})
    return doc
