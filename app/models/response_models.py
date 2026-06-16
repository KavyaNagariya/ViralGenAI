"""
app/models/response_models.py
─────────────────────────────────────────────
Pydantic schemas for all API responses and
the internal job document structure.
"""
from enum import Enum
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    pending = "PENDING"
    processing = "PROCESSING"
    success = "SUCCESS"
    failed = "FAILED"


class StatusLogEntry(BaseModel):
    status: JobStatus
    message: str
    timestamp: datetime


class CopyVariant(BaseModel):
    platform: str
    persona: str
    copy_text: str
    char_count: int
    variant_index: int = 1
    image_url: Optional[str] = None


class Telemetry(BaseModel):
    llm_provider: str
    model: str
    image_model: Optional[str] = None      # populated in Week 2
    total_duration_ms: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CampaignTurn(BaseModel):
    brief: str
    refined_prompt: Optional[str] = None
    image_url: Optional[str] = None
    variants: List[CopyVariant] = []
    telemetry: Optional[Telemetry] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Response: POST /api/v1/generate ────────────────────────
class GenerateResponse(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.pending
    message: str = "Job accepted. Poll /api/v1/status/{job_id} for updates."


# ── Response: GET /api/v1/status/{job_id} ──────────────────
class StatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress_log: List[StatusLogEntry] = []
    brief: Optional[str] = None
    refined_prompt: Optional[str] = None      # populated after Prompt Refinement Agent runs
    variants: Optional[List[CopyVariant]] = None
    image_url: Optional[str] = None           # populated after Cloudinary upload
    telemetry: Optional[Telemetry] = None
    turns: List[CampaignTurn] = []
    error: Optional[str] = None


# ── Internal MongoDB document shape ────────────────────────
class JobDocument(BaseModel):
    job_id: str
    status: JobStatus
    input: Dict[str, Any]
    refined_prompt: Optional[str] = None   # populated in Week 2
    variants: List[CopyVariant] = []
    image_url: Optional[str] = None
    telemetry: Optional[Telemetry] = None
    status_history: List[StatusLogEntry] = []
    turns: List[CampaignTurn] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
