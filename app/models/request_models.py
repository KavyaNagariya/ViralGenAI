"""
app/models/request_models.py
─────────────────────────────────────────────
Pydantic schemas for incoming API requests.
"""
from enum import Enum
from typing import List
from pydantic import BaseModel, Field, field_validator


class Platform(str, Enum):
    linkedin = "linkedin"
    instagram = "instagram"
    twitter = "twitter"
    facebook = "facebook"


class Persona(str, Enum):
    professional = "professional"
    witty = "witty"
    urgent = "urgent"


class GenerateRequest(BaseModel):
    brief: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Raw marketing brief, e.g. 'white sneakers'",
        examples=["white sneakers for runners"],
    )
    platforms: List[Platform] = Field(
        default=[Platform.instagram, Platform.linkedin],
        description="Target social platforms",
    )
    personas: List[Persona] = Field(
        default=[Persona.professional, Persona.witty, Persona.urgent],
        description="Brand voice personas to generate",
    )
    variants_count: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Number of copy variants per (platform × persona) combination",
    )

    @field_validator("platforms")
    @classmethod
    def at_least_one_platform(cls, v: List[Platform]) -> List[Platform]:
        if not v:
            raise ValueError("At least one platform must be specified.")
        return v

    @field_validator("personas")
    @classmethod
    def at_least_one_persona(cls, v: List[Persona]) -> List[Persona]:
        if not v:
            raise ValueError("At least one persona must be specified.")
        return v
