# ViralGen AI 🚀

> Asynchronous multi-modal social media ad content generator.  
> Submit a brief → get brand-voice-optimized copy across LinkedIn, Instagram, Twitter/X, and Facebook.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI (Python 3.11+) |
| Primary LLM | Groq (llama-4-scout / llama-3.3-70b) |
| Fallback LLM | Google Gemini 2.5 Flash |
| Image Gen | Hugging Face FLUX.1-schnell *(Week 2)* |
| Image Storage | Cloudflare R2 *(Week 2)* |
| Task Queue | Celery + Upstash Redis *(Week 3)* |
| Database | MongoDB Atlas (Motor async driver) |

---

## Quick Start

### 1. Clone & install dependencies
```bash
git clone <repo-url>
cd viralgenai
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

Required keys for **Week 1**:
- `GROQ_API_KEY` — from [console.groq.com](https://console.groq.com)
- `MONGODB_URI` — from [MongoDB Atlas](https://cloud.mongodb.com)

### 3. Run the server
```bash
uvicorn app.main:app --reload
```

API docs available at: http://localhost:8000/docs

---

## API Reference

### `POST /api/v1/generate`
Submit a new generation job.

**Request body:**
```json
{
  "brief": "white sneakers for runners",
  "platforms": ["instagram", "linkedin", "twitter", "facebook"],
  "personas": ["professional", "witty", "urgent"],
  "variants_count": 1
}
```

**Response** (`202 Accepted`):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING",
  "message": "Job accepted. Poll /api/v1/status/{job_id} for updates."
}
```

---

### `GET /api/v1/status/{job_id}`
Poll the status of a generation job.

**Response** (on `SUCCESS`):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "SUCCESS",
  "progress_log": [
    { "status": "PENDING", "message": "Job created.", "timestamp": "..." },
    { "status": "PROCESSING", "message": "Copy generation started.", "timestamp": "..." },
    { "status": "SUCCESS", "message": "Generated 3 copy variants successfully.", "timestamp": "..." }
  ],
  "variants": [
    {
      "platform": "instagram",
      "persona": "witty",
      "copy": "Run wild. Look sharp. No compromise.",
      "char_count": 37,
      "variant_index": 1
    }
  ],
  "image_url": null,
  "telemetry": {
    "llm_provider": "groq",
    "model": "llama-4-scout-17b-16e-instruct",
    "total_duration_ms": 2400
  }
}
```

---

### `GET /health`
Health check.

```json
{ "status": "ok", "version": "0.1.0", "env": "development" }
```

---

## Running Tests
```bash
pytest
```

All tests use mocks — no real API quota is consumed.

---

## Project Structure
```
viralgenai/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Settings from .env
│   ├── logger.py            # JSON structured logger
│   ├── routers/
│   │   ├── generate.py      # POST /api/v1/generate
│   │   └── status.py        # GET /api/v1/status/{job_id}
│   ├── services/
│   │   ├── llm_client.py    # Groq → Gemini failover
│   │   ├── copy_generator.py# Platform × persona loop
│   │   └── job_store.py     # MongoDB CRUD
│   ├── prompts/
│   │   ├── personas.py      # System prompts: Professional/Witty/Urgent
│   │   └── platform_rules.py# Per-platform rules & char limits
│   └── models/
│       ├── request_models.py
│       └── response_models.py
└── tests/
    ├── test_llm_client.py
    ├── test_copy_generator.py
    └── test_routes.py
```

---

## Week Roadmap

| Week | Focus |
|---|---|
| ✅ Week 1 | FastAPI + Groq text engine + brand voice personas |
| 🔜 Week 2 | FLUX image generation + Prompt Refinement Agent + Cloudflare R2 |
| 🔜 Week 3 | Celery async queue + Upstash Redis |
| 🔜 Week 4 | MongoDB history + E2E polish + telemetry |
