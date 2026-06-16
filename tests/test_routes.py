"""
tests/test_routes.py
─────────────────────────────────────────────
Integration tests for the FastAPI routes.
Uses httpx AsyncClient + mocked services — no DB or LLM calls.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.response_models import JobStatus, CopyVariant, Telemetry
from datetime import datetime, timezone


FAKE_JOB_ID = "test-job-1234-abcd"
FAKE_VARIANT = CopyVariant(
    platform="instagram",
    persona="professional",
    copy_text="Step into performance. Every mile, reimagined.",
    char_count=47,
    variant_index=1,
)
FAKE_TELEMETRY = Telemetry(
    llm_provider="groq",
    model="llama-4-scout-17b-16e-instruct",
    total_duration_ms=1500,
    created_at=datetime.now(timezone.utc),
)


# ── POST /api/v1/generate ──────────────────────────────────
@pytest.mark.asyncio
async def test_generate_returns_202_with_job_id():
    """POST /generate must return HTTP 202 and a job_id immediately."""
    with (
        patch("app.routers.generate.job_store.create_job", new_callable=AsyncMock),
        patch("app.routers.generate.run_generation_pipeline_task.delay") as mock_delay,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/generate",
                json={
                    "brief": "white sneakers",
                    "platforms": ["instagram"],
                    "personas": ["professional"],
                    "variants_count": 1,
                },
            )

    assert response.status_code == 202
    body = response.json()
    assert "job_id" in body
    assert body["status"] == "PENDING"
    assert "message" in body
    mock_delay.assert_called_once()


@pytest.mark.asyncio
async def test_generate_invalid_brief_returns_422():
    """Brief shorter than 3 chars should return HTTP 422 validation error."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/generate",
            json={"brief": "ab"},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_generate_empty_platforms_returns_422():
    """Submitting an empty platforms list should return HTTP 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/generate",
            json={"brief": "white sneakers", "platforms": [], "personas": ["witty"]},
        )
    assert response.status_code == 422


# ── GET /api/v1/status/{job_id} ────────────────────────────
@pytest.mark.asyncio
async def test_status_returns_pending_job():
    """GET /status returns correct PENDING job structure."""
    fake_doc = {
        "job_id": FAKE_JOB_ID,
        "status": "PENDING",
        "status_history": [
            {"status": "PENDING", "message": "Job created.", "timestamp": datetime.now(timezone.utc)}
        ],
        "variants": None,
        "image_url": None,
        "telemetry": None,
    }

    with patch("app.routers.status.job_store.get_job", new_callable=AsyncMock, return_value=fake_doc):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/status/{FAKE_JOB_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == FAKE_JOB_ID
    assert body["status"] == "PENDING"
    assert len(body["progress_log"]) == 1


@pytest.mark.asyncio
async def test_status_404_for_unknown_job():
    """GET /status with an unknown job_id must return 404."""
    with patch("app.routers.status.job_store.get_job", new_callable=AsyncMock, return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/status/nonexistent-job-id")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_status_success_returns_variants():
    """A SUCCESS job must include variants and telemetry in the response."""
    fake_doc = {
        "job_id": FAKE_JOB_ID,
        "status": "SUCCESS",
        "status_history": [
            {"status": "PENDING", "message": "Job created.", "timestamp": datetime.now(timezone.utc)},
            {"status": "SUCCESS", "message": "Generated 1 variants.", "timestamp": datetime.now(timezone.utc)},
        ],
        "variants": [FAKE_VARIANT.model_dump()],
        "image_url": None,
        "telemetry": FAKE_TELEMETRY.model_dump(),
    }

    with patch("app.routers.status.job_store.get_job", new_callable=AsyncMock, return_value=fake_doc):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/status/{FAKE_JOB_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SUCCESS"
    assert len(body["variants"]) == 1
    assert body["variants"][0]["platform"] == "instagram"
    assert body["telemetry"]["llm_provider"] == "groq"


# ── GET /health ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_health_check():
    """GET /health must return 200 with status ok."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ── DELETE /api/v1/status/{job_id} ──────────────────────────
@pytest.mark.asyncio
async def test_delete_campaign_success():
    """DELETE /status/{job_id} must return success message on deletion."""
    with patch("app.routers.status.job_store.delete_job", new_callable=AsyncMock, return_value=True):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete(f"/api/v1/status/{FAKE_JOB_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "deleted successfully" in body["message"]


@pytest.mark.asyncio
async def test_delete_campaign_404():
    """DELETE /status/{job_id} must return 404 if campaign is not found."""
    with patch("app.routers.status.job_store.delete_job", new_callable=AsyncMock, return_value=False):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/api/v1/status/nonexistent-id")

    assert response.status_code == 404


# ── POST /api/v1/redis/clear ──────────────────────────────
@pytest.mark.asyncio
async def test_clear_redis_success():
    """POST /redis/clear must call flushdb and return success message."""
    mock_redis = MagicMock()
    with (
        patch("app.routers.status.settings", MagicMock(upstash_redis_url="http://redis", upstash_redis_token="token")),
        patch("app.routers.status.Redis", return_value=mock_redis),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/redis/clear")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    mock_redis.flushdb.assert_called_once()


# ── POST /api/v1/generate (Refinement) ──────────────────────
@pytest.mark.asyncio
async def test_generate_refinement_success():
    """POST /generate with job_id should verify job exists, update status, and return 202."""
    fake_job_doc = {
        "job_id": FAKE_JOB_ID,
        "status": "SUCCESS",
        "input": {"brief": "original brief"},
    }
    with (
        patch("app.routers.generate.job_store.get_job", new_callable=AsyncMock, return_value=fake_job_doc),
        patch("app.routers.generate.job_store.update_job_status", new_callable=AsyncMock) as mock_update_status,
        patch("app.routers.generate.run_generation_pipeline_task.delay") as mock_delay,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/generate",
                json={
                    "job_id": FAKE_JOB_ID,
                    "brief": "make the image futuristic",
                    "platforms": ["instagram"],
                    "personas": ["professional"],
                    "variants_count": 1,
                },
            )

    assert response.status_code == 202
    body = response.json()
    assert body["job_id"] == FAKE_JOB_ID
    assert body["status"] == "PENDING"
    mock_update_status.assert_called_once_with(
        job_id=FAKE_JOB_ID,
        status=JobStatus.pending,
        message="Refining campaign with instruction: make the image futuristic",
    )
    mock_delay.assert_called_once()


@pytest.mark.asyncio
async def test_generate_refinement_404_if_not_found():
    """POST /generate with non-existent job_id should return 404."""
    with patch("app.routers.generate.job_store.get_job", new_callable=AsyncMock, return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/generate",
                json={
                    "job_id": "nonexistent-job-id",
                    "brief": "make the image futuristic",
                    "platforms": ["instagram"],
                    "personas": ["professional"],
                    "variants_count": 1,
                },
            )

    assert response.status_code == 404

