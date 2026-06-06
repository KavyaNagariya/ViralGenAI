"""
tests/test_copy_generator.py
─────────────────────────────────────────────
Unit tests for the copy generation pipeline.
Mocks the LLM client so no real API calls are made.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.services.copy_generator import generate_copy, _strip_banned_phrases, _enforce_char_limit
from app.services.llm_client import LLMResponse
from app.models.request_models import GenerateRequest, Platform, Persona


FAKE_LLM_RESPONSE = LLMResponse(
    text="Your next run starts here. Engineered for speed, built for you.",
    provider="groq",
    model="llama-4-scout-17b-16e-instruct",
)


def _make_request(**kwargs) -> GenerateRequest:
    defaults = {
        "brief": "running shoes",
        "platforms": [Platform.instagram],
        "personas": [Persona.professional],
        "variants_count": 1,
    }
    defaults.update(kwargs)
    return GenerateRequest(**defaults)


# ── Correct variant count ──────────────────────────────────
@pytest.mark.asyncio
async def test_variant_count_matches_combinations():
    """
    Total variants = len(platforms) × len(personas) × variants_count.
    """
    request = _make_request(
        platforms=[Platform.instagram, Platform.linkedin],
        personas=[Persona.professional, Persona.witty],
        variants_count=2,
    )

    with patch("app.services.copy_generator.generate_text", new_callable=AsyncMock, return_value=FAKE_LLM_RESPONSE):
        variants, _ = await generate_copy(request)

    # 2 platforms × 2 personas × 2 variants = 8
    assert len(variants) == 8


# ── Persona / platform metadata on variants ────────────────
@pytest.mark.asyncio
async def test_variant_has_correct_metadata():
    """Each CopyVariant must carry the correct platform and persona labels."""
    request = _make_request(
        platforms=[Platform.twitter],
        personas=[Persona.urgent],
        variants_count=1,
    )

    with patch("app.services.copy_generator.generate_text", new_callable=AsyncMock, return_value=FAKE_LLM_RESPONSE):
        variants, _ = await generate_copy(request)

    assert variants[0].platform == "twitter"
    assert variants[0].persona == "urgent"
    assert variants[0].variant_index == 1


# ── Banned phrase stripping ────────────────────────────────
def test_banned_phrases_stripped():
    """_strip_banned_phrases must remove known banned phrases case-insensitively."""
    dirty = "Thrilled to share our new running shoes! Revolutionize your workflow today."
    cleaned = _strip_banned_phrases(dirty)
    assert "thrilled to share" not in cleaned.lower()
    assert "revolutionize your workflow" not in cleaned.lower()


# ── Character limit enforcement ────────────────────────────
def test_char_limit_enforced_twitter():
    """Twitter/X copy must not exceed 280 characters."""
    long_text = "A" * 300
    result = _enforce_char_limit(long_text, "twitter")
    assert len(result) <= 280


def test_char_limit_not_applied_when_within_bounds():
    """Short copy should pass through _enforce_char_limit unchanged."""
    short = "Great shoes. Shop now."
    result = _enforce_char_limit(short, "twitter")
    assert result == short


# ── Telemetry populated ────────────────────────────────────
@pytest.mark.asyncio
async def test_telemetry_provider_is_captured():
    """Telemetry must record which LLM provider was used."""
    request = _make_request()

    with patch("app.services.copy_generator.generate_text", new_callable=AsyncMock, return_value=FAKE_LLM_RESPONSE):
        _, telemetry = await generate_copy(request)

    assert telemetry.llm_provider == "groq"
    assert telemetry.model == "llama-4-scout-17b-16e-instruct"
    assert telemetry.total_duration_ms is not None


# ── LLM failure produces error variant, not crash ─────────
@pytest.mark.asyncio
async def test_llm_failure_produces_error_variant_not_crash():
    """If an LLM call throws, the pipeline continues and marks the variant as FAILED."""
    request = _make_request()

    with patch(
        "app.services.copy_generator.generate_text",
        new_callable=AsyncMock,
        side_effect=RuntimeError("All LLM providers failed"),
    ):
        variants, _ = await generate_copy(request)

    assert len(variants) == 1
    assert "GENERATION FAILED" in variants[0].copy_text
    assert variants[0].char_count == 0
