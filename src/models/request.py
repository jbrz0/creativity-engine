"""Request and processing status models."""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, Text, Enum, Float, Integer, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.database.session import Base


class ProcessingStatusEnum(str, PyEnum):
    """Processing status enumeration."""

    QUEUED = "queued"
    PREPARING = "preparing"
    PROCESSING_MOMENT = "processing_moment"
    PROCESSING_CRITIQUE = "processing_critique"
    PROCESSING_SYNTHESIS = "processing_synthesis"
    REFINING = "refining"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OutputType(str, PyEnum):
    """Output type enumeration."""

    SIMPLE = "simple"
    FULL = "full"


class CreativityRequest(Base):
    """Creativity request model."""

    __tablename__ = "creativity_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(String(255), nullable=True, index=True)  # Optional user identification
    input_text = Column(Text, nullable=False)
    input_metadata = Column(JSON, nullable=True)  # Additional context, preferences, etc.

    output_type = Column(
        Enum(OutputType), nullable=False, default=OutputType.FULL
    )  # Simple or full processing
    output_data = Column(JSON, nullable=True)  # Final output
    output_text = Column(Text, nullable=True)  # Final creative output text

    status = Column(
        Enum(ProcessingStatusEnum), nullable=False, default=ProcessingStatusEnum.QUEUED, index=True
    )
    progress_percentage = Column(Float, default=0.0)
    current_stage = Column(String(255), nullable=True)  # Increased for longer stage descriptions

    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    processing_logs = relationship("ProcessingLog", back_populates="request", cascade="all, delete-orphan")
    feedback = relationship("Feedback", back_populates="request", uselist=False)

    def __repr__(self) -> str:
        return f"<CreativityRequest(id={self.id}, status={self.status}, created_at={self.created_at})>"


class ProcessingLog(Base):
    """Processing log for tracking stage progression."""

    __tablename__ = "processing_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    request_id = Column(UUID(as_uuid=True), ForeignKey("creativity_requests.id"), nullable=False, index=True)

    stage = Column(String(255), nullable=False)  # Increased for longer stage descriptions
    status = Column(String(50), nullable=False)
    message = Column(Text, nullable=True)
    data = Column(JSON, nullable=True)  # Stage-specific data

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    request = relationship("CreativityRequest", back_populates="processing_logs")

    def __repr__(self) -> str:
        return f"<ProcessingLog(request_id={self.request_id}, stage={self.stage}, timestamp={self.timestamp})>"


class ProcessingStatus(Base):
    """Real-time processing status tracking."""

    __tablename__ = "processing_status"

    request_id = Column(
        UUID(as_uuid=True), ForeignKey("creativity_requests.id"), primary_key=True, index=True
    )

    # Agent statuses
    preparation_status = Column(JSON, nullable=True)
    moment_agents_status = Column(JSON, nullable=True)  # Novelty, Specialized, Mini-CAE, Idea CAE
    critique_agents_status = Column(JSON, nullable=True)  # All critique agents
    synthesis_status = Column(JSON, nullable=True)

    # Memory usage
    memories_activated = Column(JSON, nullable=True)
    semantic_matches = Column(JSON, nullable=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<ProcessingStatus(request_id={self.request_id})>"
