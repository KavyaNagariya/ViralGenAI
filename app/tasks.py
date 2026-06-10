"""
app/tasks.py
─────────────────────────────────────────────
Celery task definition for the async generation pipeline.
"""
import asyncio

from app.celery_app import celery_app
from app.models.request_models import GenerateRequest
from app.models.response_models import JobStatus
from app.services import job_store, copy_generator
from app.services.prompt_refiner import refine_prompt
from app.services.image_generator import generate_image, validate_png
from app.services.cloudinary_storage import upload_image
from app.logger import get_logger

logger = get_logger(__name__)


async def _run_generation_pipeline(job_id: str, request: GenerateRequest) -> None:
    """
    Full background generation pipeline — runs inside Celery worker.
    """
    # Initialize MongoDB client bound to the current running event loop
    job_store.init_db()
    first_platform = request.platforms[0].value

    try:
        # ── Step 1: Mark as PROCESSING ─────────────────────
        await job_store.update_job_status(
            job_id,
            JobStatus.processing,
            "Pipeline started — running Prompt Refinement Agent.",
        )

        # ── Step 2: Prompt Refinement ───────────────────────
        logger.info({"event": "pipeline_step", "step": "prompt_refinement", "job_id": job_id})
        refined = await refine_prompt(
            brief=request.brief,
            platform=first_platform,
        )

        # ── Step 3: Persist refined prompt ──────────────────
        await job_store.update_refined_prompt(job_id, refined)
        await job_store.update_job_status(
            job_id,
            JobStatus.processing,
            "Prompt refined. Starting image generation.",
        )

        # ── Step 4: Image generation ─────────────────────────
        logger.info({"event": "pipeline_step", "step": "image_generation", "job_id": job_id})
        image_bytes = await generate_image(
            refined_prompt=refined,
            platform=first_platform,
        )

        # ── Step 5: PNG validation ───────────────────────────
        validate_png(image_bytes)
        await job_store.update_job_status(
            job_id,
            JobStatus.processing,
            f"Image generated ({len(image_bytes):,} bytes). Uploading to Cloudinary.",
        )

        # ── Step 6: Upload to Cloudinary ─────────────────────
        logger.info({"event": "pipeline_step", "step": "cloudinary_upload", "job_id": job_id})
        image_url = await upload_image(job_id=job_id, image_bytes=image_bytes)
        await job_store.update_job_status(
            job_id,
            JobStatus.processing,
            "Image uploaded. Generating copy variants.",
        )

        # ── Step 7: Copy generation ───────────────────────────
        logger.info({"event": "pipeline_step", "step": "copy_generation", "job_id": job_id})
        variants, telemetry = await copy_generator.generate_copy(request)

        # ── Step 8: Persist final result ──────────────────────
        await job_store.update_job_result(
            job_id=job_id,
            variants=variants,
            telemetry=telemetry,
            image_url=image_url,
        )

        logger.info({
            "event": "pipeline_complete",
            "job_id": job_id,
            "variants": len(variants),
            "image_url": image_url,
        })

    except Exception as exc:
        logger.error({"event": "pipeline_error", "job_id": job_id, "error": str(exc)})
        try:
            await job_store.mark_job_failed(job_id, str(exc))
        except Exception as db_exc:
            logger.error({"event": "failed_to_mark_job_failed", "job_id": job_id, "error": str(db_exc)})
    finally:
        # Always close MongoDB connection pool at the end of the task
        job_store.close_db()


@celery_app.task(name="app.tasks.run_generation_pipeline_task")
def run_generation_pipeline_task(job_id: str, request_data: dict) -> None:
    """
    Celery task wrapper around the asynchronous pipeline.
    """
    request = GenerateRequest.model_validate(request_data)
    # Since we are running in a synchronous Celery task, run the async loop
    asyncio.run(_run_generation_pipeline(job_id, request))
