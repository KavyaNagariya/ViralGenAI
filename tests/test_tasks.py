"""
tests/test_tasks.py
─────────────────────────────────────────────
Unit tests for the Celery task runner.
Mocks all external calls (DB, LLMs, HuggingFace, Cloudinary)
and verifies the task executes the pipeline sequentially.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.tasks import run_generation_pipeline_task
from app.models.response_models import CopyVariant, Telemetry

FAKE_JOB_ID = "test-job-task-123"
FAKE_VARIANT = CopyVariant(
    platform="instagram",
    persona="professional",
    copy_text="Step into performance. Every mile, reimagined.",
    char_count=47,
    variant_index=1,
)
FAKE_TELEMETRY = Telemetry(
    llm_provider="gemini",
    model="gemini-2.5-flash",
    total_duration_ms=1000,
    created_at=datetime.now(timezone.utc),
)


@patch("app.tasks.job_store.update_job_status", new_callable=AsyncMock)
@patch("app.tasks.job_store.update_refined_prompt", new_callable=AsyncMock)
@patch("app.tasks.job_store.add_job_turn", new_callable=AsyncMock)
@patch("app.tasks.job_store.mark_job_failed", new_callable=AsyncMock)
@patch("app.tasks.refine_prompt", new_callable=AsyncMock, return_value="Refined visual prompt.")
@patch("app.tasks.generate_image", new_callable=AsyncMock, return_value=b"\x89PNG\r\n\x1a\nfake")
@patch("app.tasks.validate_png")
@patch("app.tasks.upload_image", new_callable=AsyncMock, return_value="https://cloudinary.com/test.png")
@patch("app.tasks.copy_generator.generate_copy", new_callable=AsyncMock, return_value=([FAKE_VARIANT], FAKE_TELEMETRY))
def test_celery_task_success(
    mock_generate_copy,
    mock_upload_image,
    mock_validate_png,
    mock_generate_image,
    mock_refine_prompt,
    mock_mark_failed,
    mock_add_turn,
    mock_update_refined,
    mock_update_status,
):
    request_data = {
        "brief": "white sneakers",
        "platforms": ["instagram"],
        "personas": ["professional"],
        "variants_count": 1,
    }

    # Run Celery task synchronously
    run_generation_pipeline_task(FAKE_JOB_ID, request_data)

    # Assert correct sequential operations
    mock_update_status.assert_any_call(
        FAKE_JOB_ID,
        mock_update_status.call_args_list[0][0][1],
        "Pipeline started — running Prompt Refinement Agent."
    )
    mock_refine_prompt.assert_called_once_with(brief="white sneakers", platform="instagram", previous_refined=None)
    mock_update_refined.assert_called_once_with(FAKE_JOB_ID, "Refined visual prompt.")
    mock_generate_image.assert_called_once_with(refined_prompt="Refined visual prompt.", platform="instagram")
    mock_validate_png.assert_called_once_with(b"\x89PNG\r\n\x1a\nfake")
    mock_upload_image.assert_called_once_with(job_id=FAKE_JOB_ID, image_bytes=b"\x89PNG\r\n\x1a\nfake", platform="instagram")
    mock_generate_copy.assert_called_once()
    mock_add_turn.assert_called_once_with(
        job_id=FAKE_JOB_ID,
        brief="white sneakers",
        refined_prompt="Refined visual prompt.",
        image_url="https://cloudinary.com/test.png",
        variants=[FAKE_VARIANT],
        telemetry=FAKE_TELEMETRY,
    )
    mock_mark_failed.assert_not_called()


@patch("app.tasks.job_store.update_job_status", new_callable=AsyncMock)
@patch("app.tasks.job_store.update_refined_prompt", new_callable=AsyncMock)
@patch("app.tasks.job_store.add_job_turn", new_callable=AsyncMock)
@patch("app.tasks.job_store.mark_job_failed", new_callable=AsyncMock)
@patch("app.tasks.refine_prompt", new_callable=AsyncMock, return_value="Refined prompt.")
@patch("app.tasks.generate_image", new_callable=AsyncMock, return_value=b"\x89PNG\r\n\x1a\nfake")
@patch("app.tasks.validate_png")
@patch("app.tasks.upload_image", new_callable=AsyncMock, side_effect=["url_insta", "url_twit"])
@patch("app.tasks.copy_generator.generate_copy", new_callable=AsyncMock)
def test_celery_task_multiple_platforms(
    mock_generate_copy,
    mock_upload_image,
    mock_validate_png,
    mock_generate_image,
    mock_refine_prompt,
    mock_mark_failed,
    mock_add_turn,
    mock_update_refined,
    mock_update_status,
):
    request_data = {
        "brief": "cool shoes",
        "platforms": ["instagram", "twitter"],
        "personas": ["witty"],
        "variants_count": 1,
    }

    # Variants returned by mock copy generator
    mock_variants = [
        CopyVariant(platform="instagram", persona="witty", copy_text="Insta copy", char_count=10, variant_index=1),
        CopyVariant(platform="twitter", persona="witty", copy_text="Twitter copy", char_count=12, variant_index=1),
    ]
    mock_generate_copy.return_value = (mock_variants, FAKE_TELEMETRY)

    run_generation_pipeline_task(FAKE_JOB_ID, request_data)

    # Should call generate_image and upload_image for both platforms
    assert mock_generate_image.call_count == 2
    mock_generate_image.assert_any_call(refined_prompt="Refined prompt.", platform="instagram")
    mock_generate_image.assert_any_call(refined_prompt="Refined prompt.", platform="twitter")

    assert mock_upload_image.call_count == 2
    mock_upload_image.assert_any_call(job_id=FAKE_JOB_ID, image_bytes=b"\x89PNG\r\n\x1a\nfake", platform="instagram")
    mock_upload_image.assert_any_call(job_id=FAKE_JOB_ID, image_bytes=b"\x89PNG\r\n\x1a\nfake", platform="twitter")

    # Verify variants have platform-specific URLs attached
    mock_add_turn.assert_called_once()
    called_args = mock_add_turn.call_args.kwargs
    variants_saved = called_args["variants"]
    assert len(variants_saved) == 2
    assert variants_saved[0].image_url == "url_insta"
    assert variants_saved[1].image_url == "url_twit"
    assert called_args["image_url"] == "url_insta"
    assert called_args["brief"] == "cool shoes"


@patch("app.tasks.job_store.update_job_status", new_callable=AsyncMock)
@patch("app.tasks.job_store.mark_job_failed", new_callable=AsyncMock)
@patch("app.tasks.refine_prompt", new_callable=AsyncMock, side_effect=ValueError("LLM Error"))
def test_celery_task_failure_propagation(
    mock_refine_prompt,
    mock_mark_failed,
    mock_update_status,
):
    request_data = {
        "brief": "white sneakers",
        "platforms": ["instagram"],
        "personas": ["professional"],
        "variants_count": 1,
    }

    # Run Celery task synchronously
    run_generation_pipeline_task(FAKE_JOB_ID, request_data)

    # Check status updates and error marks
    mock_update_status.assert_called_once()
    mock_refine_prompt.assert_called_once_with(brief="white sneakers", platform="instagram", previous_refined=None)
    mock_mark_failed.assert_called_once_with(FAKE_JOB_ID, "LLM Error")
