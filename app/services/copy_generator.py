"""
app/services/copy_generator.py
─────────────────────────────────────────────
Orchestrates the (platform × persona × variants_count) copy generation loop.
Validates output: strips banned phrases, enforces char limits, counts emojis.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

from app.models.request_models import GenerateRequest
from app.models.response_models import CopyVariant, Telemetry
from app.prompts.personas import get_persona_system_prompt, BANNED_PHRASES
from app.prompts.platform_rules import get_platform_user_instructions, PLATFORM_SPECS
from app.services.llm_client import generate_text, LLMResponse
from app.logger import get_logger

logger = get_logger(__name__)


def _count_emojis(text: str) -> int:
    """Count emoji characters in a string."""
    return sum(
        1 for char in text
        if unicodedata.category(char) in ("So", "Sm") or ord(char) > 0x1F300
    )


def _strip_banned_phrases(text: str) -> str:
    """
    Remove any banned phrases from generated copy (case-insensitive).
    Logs a warning whenever a phrase is found and stripped.
    """
    cleaned = text
    for phrase in BANNED_PHRASES:
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        if pattern.search(cleaned):
            logger.warning({
                "event": "banned_phrase_detected",
                "phrase": phrase,
                "action": "stripped",
            })
            cleaned = pattern.sub("", cleaned).strip()
    return cleaned


def _enforce_char_limit(text: str, platform: str) -> str:
    """Hard-truncate copy at the platform character limit if LLM overruns."""
    spec = PLATFORM_SPECS.get(platform)
    if not spec:
        return text
    if len(text) <= spec.max_chars:
        return text

    logger.warning({
        "event": "char_limit_exceeded",
        "platform": platform,
        "original_len": len(text),
        "limit": spec.max_chars,
        "action": "truncated",
    })
    # Truncate at the last word boundary before the limit
    truncated = text[: spec.max_chars]
    last_space = truncated.rfind(" ")
    return truncated[:last_space].rstrip() + "…" if last_space > 0 else truncated


async def generate_copy(
    request: GenerateRequest,
    previous_turns: list[dict] = [],
) -> tuple[list[CopyVariant], Telemetry]:
    """
    Core copy generation pipeline.

    Iterates over every (platform × persona × variant_index) combination,
    calls the LLM, post-processes output, and returns structured variants.

    Returns:
        (variants, telemetry)
    """
    start_time = datetime.now(timezone.utc)
    variants: list[CopyVariant] = []
    provider_used = "groq"
    model_used = "unknown"

    for platform in request.platforms:
        for persona in request.personas:
            for idx in range(1, request.variants_count + 1):
                system_prompt = get_persona_system_prompt(persona.value)

                # Look for matching previous copy variant in the history
                previous_copy_text = None
                if previous_turns:
                    for turn in reversed(previous_turns):
                        for var in turn.get("variants", []):
                            if (
                                var.get("platform") == platform.value
                                and var.get("persona") == persona.value
                                and var.get("variant_index") == idx
                            ):
                                previous_copy_text = var.get("copy_text")
                                break
                        if previous_copy_text:
                            break

                if previous_copy_text:
                    user_prompt = f"""
We previously generated this copy:
"{previous_copy_text}"

The user wants to make modifications or has provided this feedback:
"{request.brief}"

Rewrite the copy based on the user's feedback. Maintain the target platform specifications and persona tone.
""".strip()
                else:
                    user_prompt = get_platform_user_instructions(platform.value, request.brief)

                logger.info({
                    "event": "generating_variant",
                    "platform": platform.value,
                    "persona": persona.value,
                    "variant_index": idx,
                    "is_refinement": previous_copy_text is not None,
                })

                try:
                    llm_response: LLMResponse = await generate_text(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                    )
                    provider_used = llm_response.provider
                    model_used = llm_response.model

                    # ── Post-process ───────────────────────
                    copy = _strip_banned_phrases(llm_response.text)
                    copy = _enforce_char_limit(copy, platform.value)

                    emoji_count = _count_emojis(copy)
                    if emoji_count > 2:
                        logger.warning({
                            "event": "emoji_limit_exceeded",
                            "count": emoji_count,
                            "platform": platform.value,
                            "persona": persona.value,
                        })

                    variants.append(CopyVariant(
                        platform=platform.value,
                        persona=persona.value,
                        copy_text=copy,
                        char_count=len(copy),
                        variant_index=idx,
                    ))

                except Exception as e:
                    logger.error({
                        "event": "variant_generation_failed",
                        "platform": platform.value,
                        "persona": persona.value,
                        "variant_index": idx,
                        "error": str(e),
                    })
                    # Continue generating remaining variants even if one fails
                    variants.append(CopyVariant(
                        platform=platform.value,
                        persona=persona.value,
                        copy_text=f"[GENERATION FAILED: {str(e)[:100]}]",
                        char_count=0,
                        variant_index=idx,
                    ))

    duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

    telemetry = Telemetry(
        llm_provider=provider_used,
        model=model_used,
        total_duration_ms=duration_ms,
        created_at=start_time,
    )

    logger.info({
        "event": "copy_generation_complete",
        "total_variants": len(variants),
        "duration_ms": duration_ms,
        "provider": provider_used,
    })

    return variants, telemetry
