"""
tests/test_llm_client.py
─────────────────────────────────────────────
Unit tests for the LLM client failover logic.
All external API calls are mocked — no real quota used.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.llm_client import generate_text, LLMResponse
from groq import RateLimitError as GroqRateLimitError


SYSTEM_PROMPT = "You are a professional marketer."
USER_PROMPT = "Write copy for white sneakers on Instagram."
FAKE_COPY = "Step into comfort. Every stride, perfected."


# ── Groq success path ──────────────────────────────────────
@pytest.mark.asyncio
async def test_groq_primary_success():
    """Happy path: Groq primary model returns text on first call."""
    with patch("app.services.llm_client._call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = FAKE_COPY
        result = await generate_text(SYSTEM_PROMPT, USER_PROMPT)

    assert isinstance(result, LLMResponse)
    assert result.text == FAKE_COPY
    assert result.provider == "groq"
    assert mock_groq.call_count == 1


# ── Groq rate-limit → Groq fallback model success ─────────
@pytest.mark.asyncio
async def test_groq_rate_limit_triggers_fallback_model():
    """
    When the primary Groq model hits a rate limit,
    the fallback Groq model (llama-3.3-70b) should be tried next.
    """
    mock_error = GroqRateLimitError(
        message="Rate limit exceeded",
        response=MagicMock(status_code=429, headers={}),
        body={},
    )

    call_count = {"n": 0}

    async def side_effect(system_prompt, user_prompt, model):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise mock_error
        return FAKE_COPY

    with patch("app.services.llm_client._call_groq", side_effect=side_effect):
        result = await generate_text(SYSTEM_PROMPT, USER_PROMPT)

    assert result.text == FAKE_COPY
    assert result.provider == "groq"
    assert call_count["n"] == 2  # primary + fallback model


# ── Both Groq models fail → Gemini ─────────────────────────
@pytest.mark.asyncio
async def test_groq_failure_triggers_gemini_fallback():
    """
    When both Groq models fail, Gemini 2.5 Flash should be called.
    """
    mock_error = GroqRateLimitError(
        message="Rate limit exceeded",
        response=MagicMock(status_code=429, headers={}),
        body={},
    )

    with (
        patch("app.services.llm_client._call_groq", new_callable=AsyncMock, side_effect=mock_error),
        patch("app.services.llm_client._call_gemini", new_callable=AsyncMock, return_value=FAKE_COPY) as mock_gemini,
    ):
        result = await generate_text(SYSTEM_PROMPT, USER_PROMPT)

    assert result.text == FAKE_COPY
    assert result.provider == "gemini"
    assert mock_gemini.call_count == 1


# ── All providers fail → RuntimeError ──────────────────────
@pytest.mark.asyncio
async def test_all_providers_fail_raises_runtime_error():
    """If both Groq and Gemini fail, a RuntimeError must be raised."""
    mock_groq_error = GroqRateLimitError(
        message="Rate limit exceeded",
        response=MagicMock(status_code=429, headers={}),
        body={},
    )

    with (
        patch("app.services.llm_client._call_groq", new_callable=AsyncMock, side_effect=mock_groq_error),
        patch("app.services.llm_client._call_gemini", new_callable=AsyncMock, side_effect=Exception("Gemini down")),
    ):
        with pytest.raises(RuntimeError, match="All LLM providers failed"):
            await generate_text(SYSTEM_PROMPT, USER_PROMPT)


# ── Force provider test hook ───────────────────────────────
@pytest.mark.asyncio
async def test_force_provider_gemini():
    """The _force_provider='gemini' parameter routes directly to Gemini."""
    with patch("app.services.llm_client._call_gemini", new_callable=AsyncMock, return_value=FAKE_COPY) as mock_gemini:
        result = await generate_text(SYSTEM_PROMPT, USER_PROMPT, _force_provider="gemini")

    assert result.provider == "gemini"
    assert result.text == FAKE_COPY
    assert mock_gemini.call_count == 1
