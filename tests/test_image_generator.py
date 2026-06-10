"""
tests/test_image_generator.py
─────────────────────────────────────────────
Unit tests for image generation and PNG validation.
Mocks huggingface_hub.InferenceClient — no real API calls.
"""
import pytest
from io import BytesIO
from unittest.mock import patch, MagicMock
from PIL import Image

from app.services.image_generator import generate_image, validate_png, _get_platform_dimensions


# ── Helpers ────────────────────────────────────────────────
def _make_valid_png_bytes(width: int = 64, height: int = 64) -> bytes:
    """Create a minimal valid in-memory PNG."""
    img = Image.new("RGB", (width, height), color=(255, 0, 0))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_jpeg_bytes() -> bytes:
    """Create JPEG bytes to test format rejection."""
    img = Image.new("RGB", (64, 64), color=(0, 0, 255))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ── Platform dimension lookup ──────────────────────────────
def test_instagram_dimensions():
    w, h = _get_platform_dimensions("instagram")
    assert w == 1080 and h == 1080


def test_linkedin_dimensions():
    w, h = _get_platform_dimensions("linkedin")
    assert w == 1200 and h == 628


def test_twitter_dimensions():
    w, h = _get_platform_dimensions("twitter")
    assert w == 1200 and h == 675


def test_unknown_platform_falls_back_to_square():
    w, h = _get_platform_dimensions("unknown_platform")
    assert w == 1024 and h == 1024


# ── PNG validation ─────────────────────────────────────────
def test_validate_png_passes_on_valid_png():
    """validate_png() must not raise for valid PNG bytes."""
    valid_png = _make_valid_png_bytes()
    validate_png(valid_png)  # should not raise


def test_validate_png_raises_on_empty_bytes():
    """validate_png() must raise ValueError on empty bytes."""
    with pytest.raises(ValueError, match="empty bytes"):
        validate_png(b"")


def test_validate_png_raises_on_jpeg_bytes():
    """validate_png() must raise ValueError if format is not PNG."""
    jpeg_bytes = _make_jpeg_bytes()
    with pytest.raises(ValueError):
        validate_png(jpeg_bytes)


def test_validate_png_raises_on_garbage_bytes():
    """validate_png() must raise ValueError on random garbage bytes."""
    with pytest.raises(ValueError):
        validate_png(b"\x00\x01\x02\x03\x04\x05")


# ── Image generation (mocked HF) ──────────────────────────
@pytest.mark.asyncio
async def test_generate_image_returns_bytes():
    """generate_image() must return non-empty bytes on a successful mocked HF call."""
    valid_png = _make_valid_png_bytes(1080, 1080)

    # InferenceClient.text_to_image returns a PIL Image object
    pil_image = Image.open(BytesIO(valid_png))

    mock_client = MagicMock()
    mock_client.text_to_image.return_value = pil_image

    with patch("app.services.image_generator.InferenceClient", return_value=mock_client):
        result = await generate_image(
            refined_prompt="High-fidelity studio photography of white sneakers.",
            platform="instagram",
        )

    assert isinstance(result, bytes)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_generate_image_raises_on_hf_error():
    """generate_image() must raise RuntimeError when HuggingFace SDK raises."""
    mock_client = MagicMock()
    mock_client.text_to_image.side_effect = Exception("HF API unavailable")

    with patch("app.services.image_generator.InferenceClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="HuggingFace image generation failed"):
            await generate_image("test prompt", "instagram")


@pytest.mark.asyncio
async def test_generate_image_uses_correct_platform_resolution():
    """generate_image() must call HF with the correct width/height for the platform."""
    valid_png = _make_valid_png_bytes(1200, 628)
    pil_image = Image.open(BytesIO(valid_png))

    mock_client = MagicMock()
    mock_client.text_to_image.return_value = pil_image

    with patch("app.services.image_generator.InferenceClient", return_value=mock_client):
        await generate_image("test prompt", "linkedin")

    call_kwargs = mock_client.text_to_image.call_args
    assert call_kwargs.kwargs.get("width") == 1200
    assert call_kwargs.kwargs.get("height") == 628
