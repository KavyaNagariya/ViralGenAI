"""
app/routers/generate.py
─────────────────────────────────────────────
POST /api/v1/generate

Accepts a GenerateRequest, creates a PENDING job in MongoDB,
offloads copy generation to a FastAPI BackgroundTask (Week 1).
Returns job_id + HTTP 202 within < 200ms.

NOTE: In Week 3, the BackgroundTask will be replaced by a Celery task.
"""
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.models.request_models import GenerateRequest
from app.models.response_models import GenerateResponse, JobStatus
from app.services import job_store, copy_generator
from app.logger import get_logger

router = APIRouter(prefix="/api/v1", tags=["generation"])
logger = get_logger(__name__)


async def _run_generation_pipeline(job_id: str, request: GenerateRequest) -> None:
    """
    Background task: runs copy generation and persists result to MongoDB.
    Runs after the 202 response has already been sent to the client.
    """
    try:
        await job_store.update_job_status(
            job_id,
            JobStatus.processing,
            "Copy generation started.",
        )

        variants, telemetry = await copy_generator.generate_copy(request)

        await job_store.update_job_result(
            job_id=job_id,
            variants=variants,
            telemetry=telemetry,
            image_url=None,  # Populated in Week 2
        )

    except Exception as e:
        logger.error({"event": "pipeline_error", "job_id": job_id, "error": str(e)})
        await job_store.mark_job_failed(job_id, str(e))


@router.post(
    "/generate",
    response_model=GenerateResponse,
    status_code=202,
    summary="Submit a new ad content generation job",
    description=(
        "Accepts a marketing brief and generation parameters. "
        "Returns a job_id immediately with HTTP 202. "
        "Poll GET /api/v1/status/{job_id} to track progress."
    ),
)
async def submit_generation_job(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
) -> GenerateResponse:
    job_id = str(uuid.uuid4())

    logger.info({
        "event": "job_submitted",
        "job_id": job_id,
        "brief": request.brief[:60],
        "platforms": [p.value for p in request.platforms],
        "personas": [p.value for p in request.personas],
        "variants_count": request.variants_count,
    })

    # Persist PENDING job immediately before returning
    await job_store.create_job(
        job_id=job_id,
        request_data={
            "brief": request.brief,
            "platforms": [p.value for p in request.platforms],
            "personas": [p.value for p in request.personas],
            "variants_count": request.variants_count,
        },
    )

    # Offload heavy work — response returns before this runs
    background_tasks.add_task(_run_generation_pipeline, job_id, request)

    return GenerateResponse(
        job_id=job_id,
        status=JobStatus.pending,
        message=f"Job accepted. Poll /api/v1/status/{job_id} for updates.",
    )
