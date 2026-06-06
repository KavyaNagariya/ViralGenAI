"""
app/services/llm_client.py
─────────────────────────────────────────────
Unified async LLM client with automatic failover:
  Primary  → Groq  (llama-4-scout  →  llama-3.3-70b)
  Fallback → Google Gemini 2.5 Flash

Returns both the generated text and the provider that was used.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from groq import AsyncGroq, RateLimitError as GroqRateLimitError, APIError as GroqAPIError
import google.generativeai as genai

from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LLMResponse:
    text: str
    provider: str   # "groq" | "gemini"
    model: str


# ── Groq ───────────────────────────────────────────────────
async def _call_groq(
    system_prompt: str,
    user_prompt: str,
    model: str,
) -> str:
    client = AsyncGroq(api_key=settings.groq_api_key)
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.8,
        max_tokens=600,
    )
    return response.choices[0].message.content.strip()


# ── Gemini ─────────────────────────────────────────────────
async def _call_gemini(system_prompt: str, user_prompt: str) -> str:
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=system_prompt,
    )
    # Gemini SDK is synchronous — run in executor to avoid blocking the loop
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: model.generate_content(user_prompt),
    )
    return response.text.strip()


# ── Public interface ────────────────────────────────────────
async def generate_text(
    system_prompt: str,
    user_prompt: str,
    _force_provider: Optional[str] = None,   # test hook
) -> LLMResponse:
    """
    Generate text using Groq (primary) with Gemini as fallback.

    Strategy:
      1. Try Groq primary model (llama-4-scout)
      2. On RateLimitError → retry with Groq fallback model (llama-3.3-70b)
      3. On any remaining Groq failure → switch to Gemini 2.5 Flash
      4. If Gemini also fails → raise RuntimeError
    """
    # ── Test hook: force a specific provider ────────────────
    if _force_provider == "gemini":
        text = await _call_gemini(system_prompt, user_prompt)
        return LLMResponse(text=text, provider="gemini", model=settings.gemini_model)

    if _force_provider == "groq":
        text = await _call_groq(system_prompt, user_prompt, settings.groq_primary_model)
        return LLMResponse(text=text, provider="groq", model=settings.groq_primary_model)

    # ── Step 1: Groq primary ────────────────────────────────
    try:
        text = await _call_groq(system_prompt, user_prompt, settings.groq_primary_model)
        logger.info({
            "event": "llm_success",
            "provider": "groq",
            "model": settings.groq_primary_model,
        })
        return LLMResponse(text=text, provider="groq", model=settings.groq_primary_model)

    except GroqRateLimitError:
        logger.warning({
            "event": "groq_rate_limit",
            "model": settings.groq_primary_model,
            "action": "retry_with_fallback_groq_model",
        })

        # ── Step 2: Groq fallback model ─────────────────────
        try:
            text = await _call_groq(system_prompt, user_prompt, settings.groq_fallback_model)
            logger.info({
                "event": "llm_success",
                "provider": "groq",
                "model": settings.groq_fallback_model,
            })
            return LLMResponse(text=text, provider="groq", model=settings.groq_fallback_model)

        except (GroqRateLimitError, GroqAPIError) as e:
            logger.warning({
                "event": "groq_fallback_failed",
                "error": str(e),
                "action": "switching_to_gemini",
            })

    except GroqAPIError as e:
        logger.warning({
            "event": "groq_api_error",
            "error": str(e),
            "action": "switching_to_gemini",
        })

    # ── Step 3: Gemini fallback ─────────────────────────────
    try:
        text = await _call_gemini(system_prompt, user_prompt)
        logger.info({
            "event": "llm_success",
            "provider": "gemini",
            "model": settings.gemini_model,
        })
        return LLMResponse(text=text, provider="gemini", model=settings.gemini_model)

    except Exception as e:
        logger.error({
            "event": "llm_all_providers_failed",
            "error": str(e),
        })
        raise RuntimeError(f"All LLM providers failed. Last error: {e}") from e
