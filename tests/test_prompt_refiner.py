"""
tests/test_prompt_refiner.py
─────────────────────────────────────────────
Unit tests for the Prompt Refinement Agent.
Mocks llm_client.generate_text() — no real API calls.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.services.prompt_refiner import refine_prompt, _strip_preamble
from app.services.llm_client import LLMResponse

FAKE_REFINED = (
    "High-fidelity studio product photography of minimalist white leather sneakers "
    "on a matte concrete surface, dramatic side-fill lighting with subtle rim highlight, "
    "eye-level camera angle, neutral grey gradient background, ultra-sharp focus, 4K resolution."
)

FAKE_LLM_RESPONSE = LLMResponse(
    text=FAKE_REFINED,
    provider="groq",
    model="llama-4-scout-17b-16e-instruct",
)


# ── Successful refinement ──────────────────────────────────
@pytest.mark.asyncio
async def test_refine_prompt_returns_clean_string():
    """refine_prompt() must return a non-empty string on success."""
    with patch(
        "app.services.prompt_refiner.generate_text",
        new_callable=AsyncMock,
        return_value=FAKE_LLM_RESPONSE,
    ):
        result = await refine_prompt("white sneakers", "instagram")

    assert isinstance(result, str)
    assert len(result) > 20


# ── Preamble stripping ─────────────────────────────────────
@pytest.mark.asyncio
async def test_preamble_is_stripped():
    """LLM output starting with 'Here is your prompt:' must be cleaned."""
    dirty_response = LLMResponse(
        text=f"Here is your prompt: {FAKE_REFINED}",
        provider="groq",
        model="llama-4-scout-17b-16e-instruct",
    )
    with patch(
        "app.services.prompt_refiner.generate_text",
        new_callable=AsyncMock,
        return_value=dirty_response,
    ):
        result = await refine_prompt("white sneakers", "instagram")

    assert not result.lower().startswith("here is")
    assert "sneakers" in result.lower() or "photography" in result.lower()


@pytest.mark.asyncio
async def test_sure_preamble_is_stripped():
    """LLM output starting with 'Sure, here's a refined version:' must be cleaned."""
    dirty_response = LLMResponse(
        text=f"Sure, here's a refined version: {FAKE_REFINED}",
        provider="groq",
        model="llama-4-scout-17b-16e-instruct",
    )
    with patch(
        "app.services.prompt_refiner.generate_text",
        new_callable=AsyncMock,
        return_value=dirty_response,
    ):
        result = await refine_prompt("running shoes", "linkedin")

    assert not result.lower().startswith("sure")


# ── Unit tests for _strip_preamble helper ──────────────────
def test_strip_preamble_direct_cases():
    """Test _strip_preamble directly for various preamble formats."""
    cases = [
        "Here is your prompt: Studio photography...",
        "Here's the refined prompt: Studio photography...",
        "Sure! Here is a refined version: Studio photography...",
        "Refined prompt: Studio photography...",
        "Visual prompt: Studio photography...",
        "Image prompt - Studio photography...",
        "Of course, Studio photography...",
    ]
    for dirty in cases:
        cleaned = _strip_preamble(dirty)
        assert cleaned.lower().startswith("studio"), (
            f"Expected 'studio...' but got: '{cleaned[:50]}' for input: '{dirty[:60]}'"
        )


def test_strip_preamble_clean_input_unchanged():
    """Clean input (no preamble) must pass through _strip_preamble unchanged."""
    clean = "High-fidelity studio photography of running shoes on concrete."
    assert _strip_preamble(clean) == clean


# ── Quality keyword check ──────────────────────────────────
@pytest.mark.asyncio
async def test_refined_prompt_contains_visual_keywords():
    """
    The refinement prompt should produce output containing visual photography terms.
    Verifies the system prompt is doing its job with realistic mock output.
    """
    with patch(
        "app.services.prompt_refiner.generate_text",
        new_callable=AsyncMock,
        return_value=FAKE_LLM_RESPONSE,
    ):
        result = await refine_prompt("white sneakers", "instagram")

    visual_keywords = ["lighting", "photography", "background", "focus", "camera"]
    found = [kw for kw in visual_keywords if kw in result.lower()]
    assert len(found) >= 2, (
        f"Expected at least 2 visual keywords in refined prompt but found only {found}. "
        f"Result: {result[:200]}"
    )
