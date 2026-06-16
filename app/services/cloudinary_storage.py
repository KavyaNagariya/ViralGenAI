"""
app/services/cloudinary_storage.py
─────────────────────────────────────────────
Uploads generated images to Cloudinary and returns
a permanent public URL. Replaces Cloudflare R2 (free tier).

Image key pattern: viralgenai/{YYYY}/{MM}/{DD}/{job_id}
Cloudinary URL format: https://res.cloudinary.com/{cloud}/image/upload/.../{public_id}.png
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from io import BytesIO

import cloudinary
import cloudinary.uploader

from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)


def _configure_cloudinary() -> None:
    """Apply Cloudinary credentials from settings (idempotent)."""
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )


def _build_public_id(job_id: str, platform: Optional[str] = None) -> str:
    """
    Build a date-partitioned public_id for Cloudinary.
    Pattern: viralgenai/YYYY/MM/DD/{job_id}[_{platform}]
    """
    now = datetime.now(timezone.utc)
    folder = settings.cloudinary_folder  # default: "viralgenai"
    suffix = f"_{platform}" if platform else ""
    return f"{folder}/{now.year}/{now.month:02d}/{now.day:02d}/{job_id}{suffix}"


def _upload_to_cloudinary(image_bytes: bytes, public_id: str) -> str:
    """
    Synchronous Cloudinary upload. Runs inside run_in_executor.
    Returns the secure URL of the uploaded image.
    """
    _configure_cloudinary()

    result = cloudinary.uploader.upload(
        BytesIO(image_bytes),
        public_id=public_id,
        resource_type="image",
        format="png",
        overwrite=True,
    )

    secure_url: str = result.get("secure_url", "")
    if not secure_url:
        raise RuntimeError(
            f"Cloudinary upload succeeded but returned no URL. Full response: {result}"
        )
    return secure_url


async def upload_image(
    job_id: str,
    image_bytes: bytes,
    platform: Optional[str] = None,
) -> str:
    """
    Upload PNG image bytes to Cloudinary asynchronously.

    Args:
        job_id: UUID of the job — used as part of the public_id
        image_bytes: Validated PNG bytes from image_generator
        platform: Optional platform name to append to the public_id

    Returns:
        Permanent public HTTPS URL to the uploaded image

    Raises:
        RuntimeError: If the upload fails or returns no URL
    """
    public_id = _build_public_id(job_id, platform)

    logger.info({
        "event": "cloudinary_upload_start",
        "job_id": job_id,
        "public_id": public_id,
        "size_bytes": len(image_bytes),
    })

    loop = asyncio.get_event_loop()
    try:
        url: str = await loop.run_in_executor(
            None,
            lambda: _upload_to_cloudinary(image_bytes, public_id),
        )
    except Exception as exc:
        logger.error({
            "event": "cloudinary_upload_error",
            "job_id": job_id,
            "error": str(exc),
        })
        raise RuntimeError(f"Cloudinary upload failed: {exc}") from exc

    logger.info({
        "event": "cloudinary_upload_complete",
        "job_id": job_id,
        "url": url,
    })

    return url
