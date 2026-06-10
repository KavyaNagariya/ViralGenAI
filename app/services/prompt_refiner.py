"""
app/services/prompt_refiner.py
─────────────────────────────────────────────
Prompt Refinement Agent — converts a casual brief into
a rich, structured visual prompt for FLUX.1-schnell.
Reuses the Week 1 LLM client (Groq → Gemini failover).
"""
from __future__ import annotations

import re

from app.services.llm_client import generate_text
from app.prompts.refinement_prompt import (
    REFINEMENT_SYSTEM_PROMPT,
    build_refinement_user_prompt,
)
from app.logger import get_logger

logger = get_logger(__name__)

# Patterns that indicate the LLM added an unwanted preamble
_PREAMBLE_PATTERNS = [
    r"^here(?:'s| is) (?:your|the|a) (?:refined |updated |improved )?prompt[:\-]?\s*",
    r"^sure[,!]?\s*here(?:'s| is).*?:\s*",
    r"^(?:of course|certainly)[,!]?\s*",
    r"^refined prompt[:\-]?\s*",
    r"^visual prompt[:\-]?\s*",
    r"^image prompt[:\-]?\s*",
]

_PREAMBLE_RE = re.compile(
    "|".join(_PREAMBLE_PATTERNS),
    flags=re.IGNORECASE,
)


def _strip_preamble(text: str) -> str:
    """Remove common LLM preamble phrases from the beginning of the output."""
    cleaned = _PREAMBLE_RE.sub("", text.strip())
    # Also strip leading punctuation/whitespace that may remain
    return cleaned.lstrip(":-\n ").strip()


async def refine_prompt(brief: str, platform: str) -> str:
    """
    Run the Prompt Refinement Agent for a given brief and target platform.

    Args:
        brief: Raw user brief (e.g. "white sneakers for runners")
        platform: Target platform key (e.g. "instagram")

    Returns:
        A clean, rich visual prompt string ready for FLUX.1-schnell.
    """
    system_prompt = REFINEMENT_SYSTEM_PROMPT
    user_prompt = build_refinement_user_prompt(brief, platform)

    logger.info({
        "event": "prompt_refinement_start",
        "brief": brief[:80],
        "platform": platform,
    })

    llm_response = await generate_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )

    refined = _strip_preamble(llm_response.text)

    logger.info({
        "event": "prompt_refinement_complete",
        "provider": llm_response.provider,
        "model": llm_response.model,
        "refined_prompt_length": len(refined),
        "preview": refined[:120],
    })

    return refined
