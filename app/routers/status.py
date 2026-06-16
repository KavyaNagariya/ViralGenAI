"""
app/routers/status.py
─────────────────────────────────────────────
GET /api/v1/status/{job_id}

Returns the current state of a generation job including
status history, copy variants (when complete), and telemetry.
"""
from fastapi import APIRouter, HTTPException
from upstash_redis import Redis

from app.config import settings
from app.models.response_models import StatusResponse, JobStatus, StatusLogEntry, CopyVariant, Telemetry, CampaignTurn
from app.services import job_store
from app.logger import get_logger

router = APIRouter(prefix="/api/v1", tags=["status"])
logger = get_logger(__name__)



def _map_doc_to_response(doc: dict) -> StatusResponse:
    # ── Deserialize status_history ──────────────────────────
    progress_log = [
        StatusLogEntry(
            status=entry["status"],
            message=entry["message"],
            timestamp=entry["timestamp"],
        )
        for entry in doc.get("status_history", [])
    ]

    # ── Deserialize variants ────────────────────────────────
    variants = None
    if doc.get("variants"):
        variants = [
            CopyVariant(
                platform=v["platform"],
                persona=v["persona"],
                copy_text=v["copy_text"],
                char_count=v["char_count"],
                variant_index=v.get("variant_index", 1),
                image_url=v.get("image_url"),
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

    # ── Deserialize turns ───────────────────────────────────
    turns = []
    for turn_doc in doc.get("turns", []):
        t_variants = []
        if turn_doc.get("variants"):
            t_variants = [
                CopyVariant(
                    platform=v["platform"],
                    persona=v["persona"],
                    copy_text=v["copy_text"],
                    char_count=v["char_count"],
                    variant_index=v.get("variant_index", 1),
                    image_url=v.get("image_url"),
                )
                for v in turn_doc["variants"]
            ]
        t_telemetry = None
        if turn_doc.get("telemetry"):
            t = turn_doc["telemetry"]
            t_telemetry = Telemetry(
                llm_provider=t["llm_provider"],
                model=t["model"],
                image_model=t.get("image_model"),
                total_duration_ms=t.get("total_duration_ms"),
                created_at=t["created_at"],
            )
        turns.append(
            CampaignTurn(
                brief=turn_doc["brief"],
                refined_prompt=turn_doc.get("refined_prompt"),
                image_url=turn_doc.get("image_url"),
                variants=t_variants,
                telemetry=t_telemetry,
                created_at=turn_doc.get("created_at") or doc.get("created_at"),
            )
        )

    brief_val = doc.get("input", {}).get("brief")

    # If no turns are present, build a fallback turn from the top-level properties
    if not turns and brief_val:
        turns.append(
            CampaignTurn(
                brief=brief_val,
                refined_prompt=doc.get("refined_prompt"),
                image_url=doc.get("image_url"),
                variants=variants or [],
                telemetry=telemetry,
                created_at=doc.get("created_at"),
            )
        )

    # Expose the latest turn's results on the top-level for backward compatibility
    refined_prompt = doc.get("refined_prompt")
    image_url = doc.get("image_url")
    latest_variants = variants
    latest_telemetry = telemetry

    if turns:
        refined_prompt = turns[-1].refined_prompt
        image_url = turns[-1].image_url
        latest_variants = turns[-1].variants
        latest_telemetry = turns[-1].telemetry

    return StatusResponse(
        job_id=doc["job_id"],
        status=doc["status"],
        progress_log=progress_log,
        brief=brief_val,
        refined_prompt=refined_prompt,
        variants=latest_variants,
        image_url=image_url,
        telemetry=latest_telemetry,
        turns=turns,
        error=None if doc["status"] != JobStatus.failed.value else (
            doc.get("status_history", [{}])[-1].get("message", "Unknown error")
        ),
    )


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
    return _map_doc_to_response(doc)


@router.get(
    "/history",
    response_model=list[StatusResponse],
    summary="Get recent generation jobs",
    description="Returns the latest generation jobs sorted by created_at descending.",
)
async def get_history(limit: int = 20) -> list[StatusResponse]:
    docs = await job_store.get_recent_jobs(limit)
    return [_map_doc_to_response(doc) for doc in docs]


@router.delete(
    "/status/{job_id}",
    summary="Delete a campaign job",
    description="Deletes a campaign job from the database.",
)
async def delete_campaign(job_id: str):
    deleted = await job_store.delete_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return {"status": "ok", "message": f"Job '{job_id}' deleted successfully."}


@router.post(
    "/redis/clear",
    summary="Clear the Redis cache/broker data",
    description="Flushes all keys in the configured Redis database to free cache space.",
)
async def clear_redis():
    if not settings.upstash_redis_url or not settings.upstash_redis_token:
        logger.warning({"event": "redis_clear_skipped", "reason": "credentials_not_found"})
        raise HTTPException(status_code=400, detail="Upstash Redis credentials are not configured in environment.")

    try:
        redis_client = Redis(url=settings.upstash_redis_url, token=settings.upstash_redis_token)
        redis_client.flushdb()
        logger.info({"event": "redis_cleared"})
        return {"status": "ok", "message": "Redis database flushed successfully."}
    except Exception as exc:
        logger.error({"event": "redis_clear_failed", "error": str(exc)})
        raise HTTPException(status_code=500, detail=f"Failed to clear Redis cache: {exc}")
