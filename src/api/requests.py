"""Request submission and retrieval endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import structlog

from src.database.session import get_db
from src.models.request import CreativityRequest, ProcessingStatusEnum, OutputType
from src.api.schemas import CreativityRequestCreate, CreativityRequestResponse
from src.processing.queue import enqueue_request

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/requests", response_model=CreativityRequestResponse, status_code=201)
async def create_request(
    request_data: CreativityRequestCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new creativity request.

    Args:
        request_data: Request creation data
        db: Database session

    Returns:
        Created request details
    """
    try:
        # Validate output type
        output_type = OutputType.SIMPLE if request_data.output_type.lower() == "simple" else OutputType.FULL

        # Create request record
        request = CreativityRequest(
            user_id=request_data.user_id,
            input_text=request_data.input_text,
            input_metadata=request_data.metadata,
            output_type=output_type,
            status=ProcessingStatusEnum.QUEUED,
        )

        db.add(request)
        await db.commit()
        await db.refresh(request)

        logger.info(
            "Created creativity request",
            request_id=str(request.id),
            output_type=output_type,
            user_id=request_data.user_id,
        )

        # Enqueue for processing
        await enqueue_request(request.id)

        return CreativityRequestResponse.model_validate(request)

    except Exception as e:
        logger.error("Failed to create request", error=str(e))
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create request")


@router.get("/requests/{request_id}", response_model=CreativityRequestResponse)
async def get_request(
    request_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a creativity request by ID.

    Args:
        request_id: Request ID
        db: Database session

    Returns:
        Request details
    """
    result = await db.execute(
        select(CreativityRequest).where(CreativityRequest.id == request_id)
    )
    request = result.scalar_one_or_none()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    return CreativityRequestResponse.model_validate(request)


@router.get("/requests", response_model=List[CreativityRequestResponse])
async def list_requests(
    user_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List creativity requests with optional filtering.

    Args:
        user_id: Filter by user ID
        status: Filter by status
        limit: Maximum number of results
        offset: Result offset for pagination
        db: Database session

    Returns:
        List of requests
    """
    query = select(CreativityRequest).order_by(desc(CreativityRequest.created_at))

    if user_id:
        query = query.where(CreativityRequest.user_id == user_id)

    if status:
        try:
            status_enum = ProcessingStatusEnum(status)
            query = query.where(CreativityRequest.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    requests = result.scalars().all()

    return [CreativityRequestResponse.model_validate(req) for req in requests]


@router.delete("/requests/{request_id}", status_code=204)
async def cancel_request(
    request_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a creativity request.

    Args:
        request_id: Request ID
        db: Database session
    """
    result = await db.execute(
        select(CreativityRequest).where(CreativityRequest.id == request_id)
    )
    request = result.scalar_one_or_none()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    if request.status in [ProcessingStatusEnum.COMPLETED, ProcessingStatusEnum.FAILED]:
        raise HTTPException(status_code=400, detail="Cannot cancel completed or failed request")

    request.status = ProcessingStatusEnum.CANCELLED
    await db.commit()

    logger.info("Cancelled request", request_id=str(request_id))
