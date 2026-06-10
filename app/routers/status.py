"""
app/routers/status.py
─────────────────────────────────────────────
GET /api/v1/status/{job_id}

Returns the current state of a generation job including
status history, copy variants (when complete), and telemetry.
"""
from fastapi import APIRouter, HTTPException

from app.models.response_models import StatusResponse, JobStatus, StatusLogEntry, CopyVariant, Telemetry
from app.services import job_store
from app.logger import get_logger

router = APIRouter(prefix="/api/v1", tags=["status"])
logger = get_logger(__name__)


@router.get(
    "/status/{job_id}",
    response_model=StatusResponse,
    summary="Poll the status of a generation job",
    description=(
        "Returns job state (PENDING, PROCESSING, SUCCESS, FAILED), "
        "progress log entries, copy variants (on SUCCESS), and telemetry."
    ),
)
async def get_job_status(job_id: str) -> StatusResponse:
    doc = await job_store.get_job(job_id)

    if doc is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    logger.info({"event": "status_polled", "job_id": job_id, "status": doc["status"]})

    # ── Deserialize status_history ──────────────────────────
    progress_log = [
        StatusLogEntry(
            status=entry["status"],
            message=entry["message"],
            timestamp=entry["timestamp"],
        )
        for entry in doc.get("status_history", [])
    ]

    # ── Deserialize variants (only present on SUCCESS) ──────
    variants = None
    if doc.get("variants"):
        variants = [
            CopyVariant(
                platform=v["platform"],
                persona=v["persona"],
                copy_text=v["copy_text"],
                char_count=v["char_count"],
                variant_index=v.get("variant_index", 1),
            )
            for v in doc["variants"]
        ]

    # ── Deserialize telemetry ───────────────────────────────
    telemetry = None
    if doc.get("telemetry"):
        t = doc["telemetry"]
        telemetry = Telemetry(
            llm_provider=t["llm_provider"],
            model=t["model"],
            image_model=t.get("image_model"),
            total_duration_ms=t.get("total_duration_ms"),
            created_at=t["created_at"],
        )

    return StatusResponse(
        job_id=job_id,
        status=doc["status"],
        progress_log=progress_log,
        refined_prompt=doc.get("refined_prompt"),
        variants=variants,
        image_url=doc.get("image_url"),
        telemetry=telemetry,
        error=None if doc["status"] != JobStatus.failed.value else (
            doc.get("status_history", [{}])[-1].get("message", "Unknown error")
        ),
    )
