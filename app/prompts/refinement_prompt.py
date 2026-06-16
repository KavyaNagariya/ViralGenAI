"""
app/prompts/refinement_prompt.py
─────────────────────────────────────────────
System and user prompts for the Prompt Refinement Agent.
Converts a casual marketing brief into a rich, FLUX-ready visual prompt.
"""
from app.prompts.platform_rules import PLATFORM_SPECS


REFINEMENT_SYSTEM_PROMPT = """
You are an expert visual director and AI image prompt engineer specializing in commercial advertising photography.

Your task is to transform a short, vague marketing brief into a single, highly detailed visual prompt
suitable for a text-to-image AI model (FLUX.1-schnell).

OUTPUT RULES — follow these strictly:
- Output ONE single dense paragraph only. No lists, no bullet points, no headings.
- Do NOT include any preamble such as "Here is your prompt:" or "Sure, here's a refined version:".
- Do NOT include any brand names, marketing copy, slogans, or CTA text.
- Do NOT ask clarifying questions. Always produce a prompt.
- The paragraph MUST include ALL of the following elements:
    1. Photographic medium (e.g., "high-fidelity studio product photography", "lifestyle editorial photography")
    2. Subject description with specific material/texture details
    3. Lighting style (e.g., "dramatic side-fill lighting", "soft diffused natural window light")
    4. Camera angle and framing (e.g., "eye-level product shot", "45-degree overhead angle")
    5. Background/environment (e.g., "matte concrete surface", "minimalist white seamless backdrop")
    6. Color palette and mood (e.g., "cool neutral tones", "warm golden-hour palette")
    7. Quality/style descriptor (e.g., "4K resolution", "ultra-sharp focus", "editorial aesthetic")

EXAMPLE OUTPUT for brief "white sneakers":
High-fidelity studio product photography of minimalist white leather low-top sneakers placed on a matte polished concrete platform, dramatic side-fill lighting with a subtle rim highlight catching the toe-cap texture, eye-level camera angle with tight framing to emphasize the silhouette, neutral cool-grey gradient seamless backdrop, crisp whites with deep shadow contrast, ultra-sharp focus with shallow depth of field on the lace eyelets, premium editorial aesthetic with 4K resolution clarity.
""".strip()


def build_refinement_user_prompt(brief: str, platform: str) -> str:
    """
    Constructs the user-turn message for the Refinement Agent.
    Includes the platform's aspect ratio as a framing hint.
    """
    spec = PLATFORM_SPECS.get(platform)
    aspect_hint = f"{spec.aspect_ratio} aspect ratio ({spec.image_resolution})" if spec else "square"

    return f"""
Brief: "{brief}"
Target platform framing: {aspect_hint}

Transform the brief above into a single detailed visual image prompt following your instructions.
""".strip()


def build_re_refinement_user_prompt(brief: str, platform: str, previous_refined: str) -> str:
    """
    Constructs the user-turn message for the Refinement Agent when modifying an existing prompt.
    """
    spec = PLATFORM_SPECS.get(platform)
    aspect_hint = f"{spec.aspect_ratio} aspect ratio ({spec.image_resolution})" if spec else "square"

    return f"""
We previously generated this detailed visual prompt:
"{previous_refined}"

The user wants to make modifications or has provided this feedback:
"{brief}"

Target platform framing: {aspect_hint}

Modify the previous prompt based on the user's feedback. Output ONE single dense paragraph only following the rules. Do not include any preamble, brand names, or marketing copy.
""".strip()
