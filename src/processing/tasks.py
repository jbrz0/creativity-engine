"""Celery tasks for distributed processing."""

from uuid import UUID
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.processing.celery_app import celery_app
from src.processing.pipeline import CreativityPipeline
from src.database.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)


@celery_app.task(name="src.processing.tasks.process_creativity_request", bind=True)
def process_creativity_request(self, request_id: str):
    """Process a creativity request through the full pipeline.

    Args:
        request_id: Request ID to process
    """
    import asyncio

    logger.info("Celery task started", task_id=self.request.id, request_id=request_id)

    async def _process():
        async with AsyncSessionLocal() as db:
            pipeline = CreativityPipeline(db)
            try:
                result = await pipeline.process_request(UUID(request_id))
                logger.info("Processing completed", request_id=request_id)
                return result
            except Exception as e:
                logger.error(
                    "Processing failed",
                    request_id=request_id,
                    error=str(e),
                    exc_info=e,
                )
                raise

    # Run async function in event loop
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(_process())

    return result


@celery_app.task(name="src.processing.tasks.simple_output")
def simple_output(request_id: str):
    """Generate simple/quick output for a request.

    Args:
        request_id: Request ID
    """
    # This would use the simple processing path
    return process_creativity_request(request_id)
