"""Celery application for distributed task processing."""

from celery import Celery
from src.config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "creativity_engine",
    broker=settings.rabbitmq_url,
    backend=settings.redis_url,
    include=["src.processing.tasks"],
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.task_timeout,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
)

# Configure task routes
celery_app.conf.task_routes = {
    "src.processing.tasks.process_creativity_request": {"queue": "creativity_processing"},
    "src.processing.tasks.simple_output": {"queue": "quick_processing"},
}
