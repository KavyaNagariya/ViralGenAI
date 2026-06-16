"""
tests/test_cloudinary_storage.py
─────────────────────────────────────────────
Unit tests for Cloudinary image upload service.
Mocks cloudinary.uploader.upload — no real API calls.
"""
import re
import pytest
from io import BytesIO
from unittest.mock import patch, MagicMock
from PIL import Image

from app.services.cloudinary_storage import upload_image, _build_public_id


FAKE_JOB_ID = "abc123-def456-ghi789"
FAKE_URL = "https://res.cloudinary.com/demo/image/upload/viralgenai/2026/06/07/abc123.png"


def _make_valid_png_bytes() -> bytes:
    img = Image.new("RGB", (64, 64), color=(128, 64, 32))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── Public ID format ───────────────────────────────────────
def test_build_public_id_matches_date_pattern():
    """_build_public_id() must return a date-partitioned path."""
    public_id = _build_public_id(FAKE_JOB_ID)
    # Expected: viralgenai/YYYY/MM/DD/{job_id}
    pattern = r"^viralgenai/\d{4}/\d{2}/\d{2}/" + re.escape(FAKE_JOB_ID) + "$"
    assert re.match(pattern, public_id), (
        f"public_id '{public_id}' does not match expected pattern '{pattern}'"
    )


def test_build_public_id_contains_job_id():
    """Job ID must appear at the end of the public_id."""
    public_id = _build_public_id(FAKE_JOB_ID)
    assert public_id.endswith(FAKE_JOB_ID)


def test_build_public_id_with_platform():
    """_build_public_id() must append platform suffix if provided."""
    public_id = _build_public_id(FAKE_JOB_ID, platform="instagram")
    pattern = r"^viralgenai/\d{4}/\d{2}/\d{2}/" + re.escape(FAKE_JOB_ID) + "_instagram$"
    assert re.match(pattern, public_id)


# ── Successful upload ──────────────────────────────────────
@pytest.mark.asyncio
async def test_upload_image_returns_url():
    """upload_image() must return a non-empty URL string on success."""
    png_bytes = _make_valid_png_bytes()

    mock_result = {"secure_url": FAKE_URL}

    with patch("app.services.cloudinary_storage.cloudinary.uploader.upload", return_value=mock_result):
        url = await upload_image(FAKE_JOB_ID, png_bytes)

    assert isinstance(url, str)
    assert url == FAKE_URL
    assert url.startswith("https://")


@pytest.mark.asyncio
async def test_upload_image_calls_uploader_with_correct_args():
    """upload_image() must call cloudinary.uploader.upload with PNG format."""
    png_bytes = _make_valid_png_bytes()
    mock_result = {"secure_url": FAKE_URL}

    with patch(
        "app.services.cloudinary_storage.cloudinary.uploader.upload",
        return_value=mock_result,
    ) as mock_upload:
        await upload_image(FAKE_JOB_ID, png_bytes)

    assert mock_upload.called
    call_kwargs = mock_upload.call_args.kwargs
    assert call_kwargs.get("format") == "png"
    assert call_kwargs.get("resource_type") == "image"


# ── Upload failure ─────────────────────────────────────────
@pytest.mark.asyncio
async def test_upload_image_raises_on_cloudinary_error():
    """upload_image() must raise RuntimeError when Cloudinary SDK raises."""
    png_bytes = _make_valid_png_bytes()

    with patch(
        "app.services.cloudinary_storage.cloudinary.uploader.upload",
        side_effect=Exception("Cloudinary API error"),
    ):
        with pytest.raises(RuntimeError, match="Cloudinary upload failed"):
            await upload_image(FAKE_JOB_ID, png_bytes)


@pytest.mark.asyncio
async def test_upload_image_raises_when_no_url_in_response():
    """upload_image() must raise RuntimeError if Cloudinary returns no secure_url."""
    png_bytes = _make_valid_png_bytes()

    with patch(
        "app.services.cloudinary_storage.cloudinary.uploader.upload",
        return_value={"public_id": "something", "secure_url": ""},
    ):
        with pytest.raises(RuntimeError, match="no URL"):
            await upload_image(FAKE_JOB_ID, png_bytes)
