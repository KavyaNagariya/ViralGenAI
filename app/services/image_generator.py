"""
app/services/image_generator.py
─────────────────────────────────────────────
Calls Hugging Face FLUX.1-schnell via huggingface_hub SDK
to generate an image from a refined visual prompt.
Validates the result using Pillow before returning bytes.
"""
from __future__ import annotations

import asyncio
from io import BytesIO

from PIL import Image
from huggingface_hub import InferenceClient

from app.config import settings
from app.prompts.platform_rules import PLATFORM_SPECS
from app.logger import get_logger

logger = get_logger(__name__)

HF_MODEL = "black-forest-labs/FLUX.1-schnell"


def _get_platform_dimensions(platform: str) -> tuple[int, int]:
    """
    Return (width, height) for a given platform key.
    Falls back to 1024×1024 if platform is unknown.
    """
    spec = PLATFORM_SPECS.get(platform)
    if not spec:
        logger.warning({
            "event": "unknown_platform_dimension",
            "platform": platform,
            "fallback": "1024x1024",
        })
        return 1024, 1024

    # Parse "1080x1080" → (1080, 1080)
    try:
        w, h = spec.image_resolution.split("x")
        return int(w), int(h)
    except ValueError:
        return 1024, 1024


def _call_hf_inference(
    refined_prompt: str,
    width: int,
    height: int,
) -> bytes:
    """
    Synchronous call to HF InferenceClient.
    Runs inside run_in_executor to avoid blocking the event loop.
    Returns raw image bytes.
    """
    client = InferenceClient(
        model=HF_MODEL,
        token=settings.huggingface_api_token,
    )
    # text_to_image returns a PIL Image object
    pil_image: Image.Image = client.text_to_image(
        prompt=refined_prompt,
        width=width,
        height=height,
    )
    # Convert PIL Image → PNG bytes
    buffer = BytesIO()
    pil_image.save(buffer, format="PNG")
    return buffer.getvalue()


def validate_png(image_bytes: bytes) -> None:
    """
    Validates that image_bytes is a non-empty, valid PNG image.
    Raises ValueError with a descriptive message on failure.
    """
    if not image_bytes:
        raise ValueError("Image generation returned empty bytes — no image produced.")

    try:
        img = Image.open(BytesIO(image_bytes))
        img.verify()  # Raises on corrupt data
    except Exception as exc:
        raise ValueError(f"Image bytes failed PIL validation: {exc}") from exc

    # Re-open after verify (verify() leaves the file pointer in an unusable state)
    img2 = Image.open(BytesIO(image_bytes))
    if img2.format != "PNG":
        raise ValueError(
            f"Expected PNG format but received: {img2.format}. "
            "Check HuggingFace API response."
        )


async def generate_image(refined_prompt: str, platform: str) -> bytes:
    """
    Generate an image for the given refined prompt and platform.

    Args:
        refined_prompt: Output from the Prompt Refinement Agent
        platform: Target platform key — determines image resolution

    Returns:
        PNG image as raw bytes (validated)

    Raises:
        ValueError: If the returned image is empty or not a valid PNG
        RuntimeError: If the HF API call itself fails
    """
    width, height = _get_platform_dimensions(platform)

    logger.info({
        "event": "image_generation_start",
        "model": HF_MODEL,
        "platform": platform,
        "resolution": f"{width}x{height}",
        "prompt_preview": refined_prompt[:100],
    })

    loop = asyncio.get_event_loop()
    try:
        image_bytes: bytes = await loop.run_in_executor(
            None,
            lambda: _call_hf_inference(refined_prompt, width, height),
        )
    except Exception as exc:
        logger.error({
            "event": "image_generation_hf_error",
            "model": HF_MODEL,
            "error": str(exc),
        })
        raise RuntimeError(f"HuggingFace image generation failed: {exc}") from exc

    # Validate the result
    validate_png(image_bytes)

    logger.info({
        "event": "image_generation_complete",
        "size_bytes": len(image_bytes),
        "platform": platform,
    })

    return image_bytes
