"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, Field


# Request schemas
class CreativityRequestCreate(BaseModel):
    """Schema for creating a creativity request."""

    input_text: str = Field(..., description="The input text for creative processing")
    user_id: Optional[str] = Field(None, description="Optional user identifier")
    output_type: str = Field(
        default="full", description="Output type: 'simple' or 'full'"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional context and preferences"
    )


class CreativityRequestResponse(BaseModel):
    """Schema for creativity request response."""

    id: UUID
    status: str
    progress_percentage: float
    current_stage: Optional[str]
    created_at: datetime
    output_text: Optional[str] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


# Status schemas
class ProcessingStatusResponse(BaseModel):
    """Schema for processing status response."""

    request_id: UUID
    status: str
    progress_percentage: float
    current_stage: Optional[str]
    preparation_status: Optional[Dict[str, Any]]
    moment_agents_status: Optional[Dict[str, Any]]
    critique_agents_status: Optional[Dict[str, Any]]
    synthesis_status: Optional[Dict[str, Any]]
    memories_activated: Optional[Dict[str, Any]]
    updated_at: datetime


# Feedback schemas
class FeedbackCreate(BaseModel):
    """Schema for creating feedback."""

    request_id: UUID
    identity_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    novelty_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    coherence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    relevance_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    personalization_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    overall_rating: Optional[int] = Field(None, ge=1, le=5)
    feedback_text: Optional[str] = None
    feedback_metadata: Optional[Dict[str, Any]] = None


class FeedbackResponse(BaseModel):
    """Schema for feedback response."""

    id: UUID
    request_id: UUID
    identity_score: Optional[float]
    confidence_score: Optional[float]
    novelty_score: Optional[float]
    coherence_score: Optional[float]
    relevance_score: Optional[float]
    personalization_score: Optional[float]
    overall_rating: Optional[int]
    feedback_text: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# WebSocket message schemas
class WebSocketMessage(BaseModel):
    """Schema for WebSocket messages."""

    type: str  # "status_update", "progress", "completed", "error"
    request_id: UUID
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
