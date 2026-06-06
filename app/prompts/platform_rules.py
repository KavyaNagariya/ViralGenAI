"""
app/prompts/platform_rules.py
─────────────────────────────────────────────
Per-platform copy length caps, formatting rules, and
audience context injected into every LLM user prompt.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformSpec:
    name: str
    max_chars: int
    aspect_ratio: str
    image_resolution: str
    audience_note: str
    style_note: str


PLATFORM_SPECS: dict[str, PlatformSpec] = {
    "linkedin": PlatformSpec(
        name="LinkedIn",
        max_chars=700,
        aspect_ratio="1.91:1",
        image_resolution="1200x628",
        audience_note="B2B professionals, decision-makers, industry leaders",
        style_note="Lead with a data point or insight. No hashtag spam. Max 3 hashtags.",
    ),
    "instagram": PlatformSpec(
        name="Instagram",
        max_chars=300,
        aspect_ratio="1:1",
        image_resolution="1080x1080",
        audience_note="Visual-first consumers, trend-aware millennial and Gen Z audience",
        style_note="Punchy opener within the first 10 words. Line breaks welcome. Up to 5 hashtags.",
    ),
    "twitter": PlatformSpec(
        name="Twitter/X",
        max_chars=280,
        aspect_ratio="16:9",
        image_resolution="1200x675",
        audience_note="Fast-scrolling, opinion-driven, real-time audience",
        style_note="No wasted words. One strong hook. Avoid threads format.",
    ),
    "facebook": PlatformSpec(
        name="Facebook",
        max_chars=500,
        aspect_ratio="1.91:1",
        image_resolution="1200x628",
        audience_note="Broad consumer demographic, community-oriented",
        style_note="Conversational tone. Can include a question to drive comments.",
    ),
}


def get_platform_user_instructions(platform: str, brief: str) -> str:
    """
    Build the platform-specific section of the LLM user prompt.
    Injected after the core brief to constrain length, audience, and style.
    """
    spec = PLATFORM_SPECS.get(platform)
    if not spec:
        raise ValueError(f"Unknown platform: {platform}")

    return f"""
--- PLATFORM CONTEXT ---
Platform      : {spec.name}
Target audience: {spec.audience_note}
Style guidance : {spec.style_note}
Hard limit     : Your output MUST be under {spec.max_chars} characters (including spaces).
                 Count carefully before responding.

--- USER BRIEF ---
{brief}
""".strip()
