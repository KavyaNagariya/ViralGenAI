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
        # ── Load existing job for context ───────────────────
        doc = await job_store.get_job(job_id)
        previous_turns = []
        previous_refined = None
        if doc:
            previous_refined = doc.get("refined_prompt")
            previous_turns = doc.get("turns", [])
            # If turns are empty but we have legacy properties (historical job), migrate it
            if not previous_turns and (doc.get("refined_prompt") or doc.get("variants") or doc.get("image_url")):
                from app.models.response_models import CopyVariant, Telemetry
                t_variants = []
                for v in doc.get("variants", []):
                    t_variants.append(
                        CopyVariant(
                            platform=v["platform"],
                            persona=v["persona"],
                            copy_text=v["copy_text"],
                            char_count=v["char_count"],
                            variant_index=v.get("variant_index", 1),
                            image_url=v.get("image_url"),
                        )
                    )
                t_telemetry = None
                if doc.get("telemetry"):
                    t = doc["telemetry"]
                    t_telemetry = Telemetry(
                        llm_provider=t["llm_provider"],
                        model=t["model"],
                        image_model=t.get("image_model"),
                        total_duration_ms=t.get("total_duration_ms"),
                        created_at=t["created_at"],
                    )
                fallback_turn = {
                    "brief": doc.get("input", {}).get("brief") or "No Brief Provided",
                    "refined_prompt": doc.get("refined_prompt"),
                    "image_url": doc.get("image_url"),
                    "variants": [v.model_dump() for v in t_variants],
                    "telemetry": t_telemetry.model_dump() if t_telemetry else None,
                    "created_at": doc.get("created_at"),
                }
                previous_turns = [fallback_turn]
                await job_store._get_collection().update_one(
                    {"job_id": job_id},
                    {"$set": {"turns": previous_turns}}
                )

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
            previous_refined=previous_refined,
        )

        # ── Step 3: Persist refined prompt ──────────────────
        await job_store.update_refined_prompt(job_id, refined)
        await job_store.update_job_status(
            job_id,
            JobStatus.processing,
            "Prompt refined. Starting image generation.",
        )

        # ── Step 4: Platform-Specific Image Generation & Upload ──
        platform_images = {}
        unique_platforms = list(dict.fromkeys([p.value for p in request.platforms]))

        for i, p in enumerate(unique_platforms, start=1):
            await job_store.update_job_status(
                job_id,
                JobStatus.processing,
                f"Generating visual for platform '{p}' ({i}/{len(unique_platforms)}).",
            )
            logger.info({"event": "pipeline_step", "step": "image_generation", "job_id": job_id, "platform": p})
            img_bytes = await generate_image(
                refined_prompt=refined,
                platform=p,
            )
            validate_png(img_bytes)

            await job_store.update_job_status(
                job_id,
                JobStatus.processing,
                f"Uploading visual for platform '{p}' ({i}/{len(unique_platforms)}) to Cloudinary.",
            )
            logger.info({"event": "pipeline_step", "step": "cloudinary_upload", "job_id": job_id, "platform": p})
            url = await upload_image(job_id=job_id, image_bytes=img_bytes, platform=p)
            platform_images[p] = url

        first_image_url = platform_images.get(first_platform) or (next(iter(platform_images.values())) if platform_images else None)

        await job_store.update_job_status(
            job_id,
            JobStatus.processing,
            "All visuals generated and uploaded. Generating copy variants.",
        )

        # ── Step 5: Copy generation ───────────────────────────
        logger.info({"event": "pipeline_step", "step": "copy_generation", "job_id": job_id})
        variants, telemetry = await copy_generator.generate_copy(request, previous_turns=previous_turns)

        # Attach corresponding image_url to each variant
        for v in variants:
            v.image_url = platform_images.get(v.platform)

        # ── Step 6: Persist final result ──────────────────────
        await job_store.add_job_turn(
            job_id=job_id,
            brief=request.brief,
            refined_prompt=refined,
            image_url=first_image_url,
            variants=variants,
            telemetry=telemetry,
        )

        logger.info({
            "event": "pipeline_complete",
            "job_id": job_id,
            "variants": len(variants),
            "image_url": first_image_url,
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
