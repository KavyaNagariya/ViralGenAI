"""
app/celery_app.py
─────────────────────────────────────────────
Initializes the Celery application using settings.
"""
from celery import Celery
from app.config import settings

broker_url = settings.celery_broker_url
if broker_url.startswith("rediss://") and "ssl_cert_reqs" not in broker_url:
    if "?" in broker_url:
        broker_url += "&ssl_cert_reqs=CERT_REQUIRED"
    else:
        broker_url += "?ssl_cert_reqs=CERT_REQUIRED"

# Initialize Celery app
celery_app = Celery(
    "viralgenai",
    broker=broker_url,
    backend=broker_url,
)

# Celery Configurations
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)

# Automatically discover tasks in app.tasks
celery_app.autodiscover_tasks(["app"])
