"""Health check endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog

from src.database.session import get_db

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "creativity-engine"}


@router.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness check with database connectivity."""
    try:
        # Check database connection
        result = await db.execute(text("SELECT 1"))
        result.scalar()

        # TODO: Check Redis connection
        # TODO: Check RabbitMQ connection
        # TODO: Check Pinecone connection

        return {
            "status": "ready",
            "checks": {
                "database": "connected",
                "redis": "not_implemented",
                "rabbitmq": "not_implemented",
                "pinecone": "not_implemented",
            },
        }
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        return {"status": "not_ready", "error": str(e)}


@router.get("/health/live")
async def liveness_check():
    """Liveness check for Kubernetes."""
    return {"status": "alive"}
