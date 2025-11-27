"""Feedback submission endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from src.database.session import get_db
from src.models.feedback import Feedback
from src.models.request import CreativityRequest
from src.api.schemas import FeedbackCreate, FeedbackResponse

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/feedback", response_model=FeedbackResponse, status_code=201)
async def create_feedback(
    feedback_data: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
):
    """Submit feedback for a creativity request.

    Args:
        feedback_data: Feedback data
        db: Database session

    Returns:
        Created feedback record
    """
    # Verify request exists
    result = await db.execute(
        select(CreativityRequest).where(CreativityRequest.id == feedback_data.request_id)
    )
    request = result.scalar_one_or_none()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    # Check if feedback already exists
    existing = await db.execute(
        select(Feedback).where(Feedback.request_id == feedback_data.request_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Feedback already exists for this request")

    # Create feedback
    feedback = Feedback(
        request_id=feedback_data.request_id,
        identity_score=feedback_data.identity_score,
        confidence_score=feedback_data.confidence_score,
        novelty_score=feedback_data.novelty_score,
        coherence_score=feedback_data.coherence_score,
        relevance_score=feedback_data.relevance_score,
        personalization_score=feedback_data.personalization_score,
        overall_rating=feedback_data.overall_rating,
        feedback_text=feedback_data.feedback_text,
        feedback_metadata=feedback_data.feedback_metadata,
    )

    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)

    logger.info(
        "Created feedback",
        feedback_id=str(feedback.id),
        request_id=str(feedback_data.request_id),
        overall_rating=feedback_data.overall_rating,
    )

    # TODO: Trigger RL training update

    return FeedbackResponse.model_validate(feedback)


@router.get("/feedback/{request_id}", response_model=FeedbackResponse)
async def get_feedback(
    request_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get feedback for a request.

    Args:
        request_id: Request ID
        db: Database session

    Returns:
        Feedback record
    """
    result = await db.execute(
        select(Feedback).where(Feedback.request_id == request_id)
    )
    feedback = result.scalar_one_or_none()

    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    return FeedbackResponse.model_validate(feedback)


@router.put("/feedback/{request_id}", response_model=FeedbackResponse)
async def update_feedback(
    request_id: UUID,
    feedback_data: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
):
    """Update existing feedback.

    Args:
        request_id: Request ID
        feedback_data: Updated feedback data
        db: Database session

    Returns:
        Updated feedback record
    """
    result = await db.execute(
        select(Feedback).where(Feedback.request_id == request_id)
    )
    feedback = result.scalar_one_or_none()

    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    # Update fields
    if feedback_data.identity_score is not None:
        feedback.identity_score = feedback_data.identity_score
    if feedback_data.confidence_score is not None:
        feedback.confidence_score = feedback_data.confidence_score
    if feedback_data.novelty_score is not None:
        feedback.novelty_score = feedback_data.novelty_score
    if feedback_data.coherence_score is not None:
        feedback.coherence_score = feedback_data.coherence_score
    if feedback_data.relevance_score is not None:
        feedback.relevance_score = feedback_data.relevance_score
    if feedback_data.personalization_score is not None:
        feedback.personalization_score = feedback_data.personalization_score
    if feedback_data.overall_rating is not None:
        feedback.overall_rating = feedback_data.overall_rating
    if feedback_data.feedback_text is not None:
        feedback.feedback_text = feedback_data.feedback_text
    if feedback_data.feedback_metadata is not None:
        feedback.feedback_metadata = feedback_data.feedback_metadata

    await db.commit()
    await db.refresh(feedback)

    logger.info("Updated feedback", feedback_id=str(feedback.id), request_id=str(request_id))

    return FeedbackResponse.model_validate(feedback)
