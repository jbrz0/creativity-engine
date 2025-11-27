"""Feedback model for reinforcement learning."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, Text, Float, Integer, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.database.session import Base


class Feedback(Base):
    """User feedback for outputs."""

    __tablename__ = "feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    request_id = Column(
        UUID(as_uuid=True), ForeignKey("creativity_requests.id"), nullable=False, index=True, unique=True
    )

    # Identity scores - how well does the output maintain identity/voice
    identity_score = Column(Float, nullable=True)  # 0.0 to 1.0

    # Confidence scores - how confident/assured is the output
    confidence_score = Column(Float, nullable=True)  # 0.0 to 1.0

    # Detailed scores
    novelty_score = Column(Float, nullable=True)  # How novel/creative
    coherence_score = Column(Float, nullable=True)  # How coherent/logical
    relevance_score = Column(Float, nullable=True)  # How relevant to input
    personalization_score = Column(Float, nullable=True)  # How personalized

    # Overall rating
    overall_rating = Column(Integer, nullable=True)  # 1-5 stars

    # Text feedback
    feedback_text = Column(Text, nullable=True)
    feedback_metadata = Column(JSON, nullable=True)  # Additional structured feedback

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    request = relationship("CreativityRequest", back_populates="feedback")

    def __repr__(self) -> str:
        return f"<Feedback(request_id={self.request_id}, overall_rating={self.overall_rating})>"
