"""
app/routers/generate.py
─────────────────────────────────────────────
POST /api/v1/generate

Accepts a GenerateRequest, creates a PENDING job in MongoDB,
and offloads the full pipeline execution to Celery.
"""
import uuid

from fastapi import APIRouter

from app.models.request_models import GenerateRequest
from app.models.response_models import GenerateResponse, JobStatus
from app.services import job_store
from app.tasks import run_generation_pipeline_task
from app.logger import get_logger

router = APIRouter(prefix="/api/v1", tags=["generation"])
logger = get_logger(__name__)


@router.post(
    "/generate",
    response_model=GenerateResponse,
    status_code=202,
    summary="Submit a new ad content generation job",
    description=(
        "Accepts a marketing brief and generation parameters. "
        "Returns a job_id immediately with HTTP 202. "
        "Poll GET /api/v1/status/{job_id} to track progress and retrieve results."
    ),
)
async def submit_generation_job(
    request: GenerateRequest,
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

    request_data = {
        "brief": request.brief,
        "platforms": [p.value for p in request.platforms],
        "personas": [p.value for p in request.personas],
        "variants_count": request.variants_count,
    }

    # Persist PENDING job immediately — must complete before returning 202
    await job_store.create_job(
        job_id=job_id,
        request_data=request_data,
    )

    # Offload to Celery — delay serialization of GenerateRequest models as dicts
    run_generation_pipeline_task.delay(job_id, request_data)

    return GenerateResponse(
        job_id=job_id,
        status=JobStatus.pending,
        message=f"Job accepted. Poll /api/v1/status/{job_id} for updates.",
    )
