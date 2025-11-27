"""Task queue management for creativity request processing."""

from uuid import UUID
import structlog
from typing import Optional

logger = structlog.get_logger(__name__)


async def enqueue_request(request_id: UUID, priority: int = 5) -> None:
    """Enqueue a creativity request for processing.

    Args:
        request_id: Request ID to process
        priority: Priority level (1-10, higher = more priority)
    """
    logger.info("Enqueuing request for processing", request_id=str(request_id), priority=priority)

    # Import here to avoid circular imports
    from src.processing.tasks import process_creativity_request

    # Send task to Celery
    try:
        task = process_creativity_request.apply_async(
            args=[str(request_id)],
            priority=priority,
        )
        logger.info("Request enqueued successfully", request_id=str(request_id), task_id=task.id)
    except Exception as e:
        logger.error("Failed to enqueue request", request_id=str(request_id), error=str(e))
        raise
