"""
app/config.py
─────────────────────────────────────────────
Loads all environment variables from .env and
exposes a typed Settings singleton used app-wide.
"""
import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ── LLM ─────────────────────────────────
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")

    # ── Groq model preference ────────────────
    groq_primary_model: str = os.getenv("GROQ_PRIMARY_MODEL", "llama-4-scout-17b-16e-instruct")
    groq_fallback_model: str = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.3-70b-versatile")

    # ── Gemini ───────────────────────────────
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # ── Hugging Face (Week 2) ────────────────
    huggingface_api_token: str = os.getenv("HUGGINGFACE_API_TOKEN", "")

    # ── Cloudflare R2 (Week 2) ───────────────
    r2_account_id: str = os.getenv("R2_ACCOUNT_ID", "")
    r2_access_key_id: str = os.getenv("R2_ACCESS_KEY_ID", "")
    r2_secret_access_key: str = os.getenv("R2_SECRET_ACCESS_KEY", "")
    r2_bucket_name: str = os.getenv("R2_BUCKET_NAME", "viralgenai-assets")
    r2_public_url: str = os.getenv("R2_PUBLIC_URL", "")

    # ── Redis / Celery (Week 3) ──────────────
    upstash_redis_url: str = os.getenv("UPSTASH_REDIS_URL", "")
    upstash_redis_token: str = os.getenv("UPSTASH_REDIS_TOKEN", "")
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "")

    # ── MongoDB ──────────────────────────────
    mongodb_uri: str = os.getenv("MONGODB_URI", "")
    mongodb_db_name: str = os.getenv("MONGODB_DB_NAME", "viralgenai")

    # ── App ──────────────────────────────────
    app_env: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
