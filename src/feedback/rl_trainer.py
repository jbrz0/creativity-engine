"""Reinforcement Learning Trainer for continuous improvement."""

from typing import List, Dict, Any, Optional
from uuid import UUID
import structlog
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.feedback import Feedback
from src.models.request import CreativityRequest
from src.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class RLTrainer:
    """Reinforcement learning trainer for continuous system improvement."""

    def __init__(self, db_session: AsyncSession):
        """Initialize RL trainer.

        Args:
            db_session: Database session
        """
        self.db = db_session
        self.training_buffer: List[Dict[str, Any]] = []

    async def collect_training_data(
        self,
        request_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """Collect training data from a completed request with feedback.

        Args:
            request_id: Request ID

        Returns:
            Training sample or None if feedback not available
        """
        # Get request
        request_result = await self.db.execute(
            select(CreativityRequest).where(CreativityRequest.id == request_id)
        )
        request = request_result.scalar_one_or_none()

        if not request:
            logger.warning("Request not found for training", request_id=str(request_id))
            return None

        # Get feedback
        feedback_result = await self.db.execute(
            select(Feedback).where(Feedback.request_id == request_id)
        )
        feedback = feedback_result.scalar_one_or_none()

        if not feedback:
            logger.debug("No feedback available for training", request_id=str(request_id))
            return None

        # Extract training sample
        training_sample = {
            "request_id": str(request_id),
            "input_text": request.input_text,
            "output_text": request.output_text,
            "output_type": request.output_type.value,
            "scores": {
                "identity": feedback.identity_score,
                "confidence": feedback.confidence_score,
                "novelty": feedback.novelty_score,
                "coherence": feedback.coherence_score,
                "relevance": feedback.relevance_score,
                "personalization": feedback.personalization_score,
                "overall": feedback.overall_rating / 5.0 if feedback.overall_rating else None,
            },
            "metadata": {
                "processing_time": (
                    (request.completed_at - request.started_at).total_seconds()
                    if request.completed_at and request.started_at
                    else None
                ),
                "output_data": request.output_data,
                "feedback_text": feedback.feedback_text,
            },
            "timestamp": datetime.utcnow(),
        }

        logger.info("Collected training sample", request_id=str(request_id))

        return training_sample

    async def add_to_buffer(self, request_id: UUID) -> None:
        """Add request to training buffer.

        Args:
            request_id: Request ID
        """
        sample = await self.collect_training_data(request_id)
        if sample:
            self.training_buffer.append(sample)

            # Trigger training if buffer is full
            if len(self.training_buffer) >= settings.training_batch_size:
                await self.train_batch()

    async def train_batch(self) -> Dict[str, Any]:
        """Train on current batch of samples.

        Returns:
            Training metrics
        """
        if not settings.enable_rl_training:
            logger.debug("RL training disabled")
            return {"status": "disabled"}

        if len(self.training_buffer) < settings.training_batch_size:
            logger.debug(
                "Insufficient training samples",
                current=len(self.training_buffer),
                required=settings.training_batch_size,
            )
            return {"status": "insufficient_data", "count": len(self.training_buffer)}

        logger.info("Starting batch training", batch_size=len(self.training_buffer))

        # TODO: Implement actual RL training
        # This is a placeholder for the RL training logic
        # In production, this would:
        # 1. Prepare training data
        # 2. Update model weights or fine-tune
        # 3. Evaluate improvements
        # 4. Store updated parameters

        # Calculate batch statistics
        scores = {
            "novelty": [],
            "coherence": [],
            "relevance": [],
            "personalization": [],
            "overall": [],
        }

        for sample in self.training_buffer:
            for key in scores.keys():
                score = sample["scores"].get(key)
                if score is not None:
                    scores[key].append(score)

        avg_scores = {
            key: sum(values) / len(values) if values else None
            for key, values in scores.items()
        }

        metrics = {
            "status": "completed",
            "batch_size": len(self.training_buffer),
            "average_scores": avg_scores,
            "timestamp": datetime.utcnow().isoformat(),
        }

        logger.info("Batch training completed", metrics=metrics)

        # Clear buffer
        self.training_buffer.clear()

        return metrics

    async def get_training_statistics(
        self,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Get training statistics for the past N days.

        Args:
            days: Number of days to look back

        Returns:
            Training statistics
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Get all feedback since cutoff
        result = await self.db.execute(
            select(Feedback).where(Feedback.created_at >= cutoff_date)
        )
        feedbacks = result.scalars().all()

        if not feedbacks:
            return {"status": "no_data", "days": days}

        # Calculate statistics
        total = len(feedbacks)
        scores = {
            "identity": [f.identity_score for f in feedbacks if f.identity_score is not None],
            "confidence": [
                f.confidence_score for f in feedbacks if f.confidence_score is not None
            ],
            "novelty": [f.novelty_score for f in feedbacks if f.novelty_score is not None],
            "coherence": [f.coherence_score for f in feedbacks if f.coherence_score is not None],
            "relevance": [f.relevance_score for f in feedbacks if f.relevance_score is not None],
            "personalization": [
                f.personalization_score for f in feedbacks if f.personalization_score is not None
            ],
            "overall": [
                f.overall_rating / 5.0 for f in feedbacks if f.overall_rating is not None
            ],
        }

        statistics = {
            "period_days": days,
            "total_feedback": total,
            "average_scores": {
                key: sum(values) / len(values) if values else None
                for key, values in scores.items()
            },
            "min_scores": {
                key: min(values) if values else None for key, values in scores.items()
            },
            "max_scores": {
                key: max(values) if values else None for key, values in scores.items()
            },
        }

        return statistics
