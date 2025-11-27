"""Critique Ensemble - Synthesizes critique from multiple agents."""

from typing import List, Dict, Any, Optional
import asyncio
import structlog

from src.agents.base import AgentResponse
from src.agents.critique.novelty import NoveltyCritiqueAgent
from src.agents.critique.coherence import CoherenceCritiqueAgent
from src.agents.critique.relevance import RelevanceCritiqueAgent
from src.agents.critique.personalized import PersonalizedCritiqueAgent
from src.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class CritiqueEnsemble:
    """Ensemble of critique agents that synthesizes feedback."""

    def __init__(self):
        """Initialize critique ensemble."""
        self.novelty_agent = NoveltyCritiqueAgent()
        self.coherence_agent = CoherenceCritiqueAgent()
        self.relevance_agent = RelevanceCritiqueAgent()
        self.personalized_agent = PersonalizedCritiqueAgent()

    async def evaluate(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Evaluate content using all critique agents.

        Args:
            content: Content to evaluate
            context: Optional context

        Returns:
            Synthesized critique with scores and feedback
        """
        logger.info("Critique ensemble evaluating content", content_length=len(content))

        # Run all agents in parallel
        input_data = {"content": content}

        results = await asyncio.gather(
            self.novelty_agent.process(input_data, context),
            self.coherence_agent.process(input_data, context),
            self.relevance_agent.process(input_data, context),
            self.personalized_agent.process(input_data, context),
            return_exceptions=True,
        )

        # Extract responses
        novelty_response = results[0] if not isinstance(results[0], Exception) else None
        coherence_response = results[1] if not isinstance(results[1], Exception) else None
        relevance_response = results[2] if not isinstance(results[2], Exception) else None
        personalized_response = results[3] if not isinstance(results[3], Exception) else None

        # Extract scores
        novelty_score = (
            novelty_response.metadata.get("novelty_score", 0.5) if novelty_response else 0.5
        )
        coherence_score = (
            coherence_response.metadata.get("coherence_score", 0.5) if coherence_response else 0.5
        )
        relevance_score = (
            relevance_response.metadata.get("relevance_score", 0.5) if relevance_response else 0.5
        )
        personalization_score = (
            personalized_response.metadata.get("personalization_score", 0.5)
            if personalized_response
            else 0.5
        )

        # Calculate weighted ensemble score
        weights = {
            "novelty": 0.3,
            "coherence": 0.25,
            "relevance": 0.3,
            "personalization": 0.15,
        }

        ensemble_score = (
            novelty_score * weights["novelty"]
            + coherence_score * weights["coherence"]
            + relevance_score * weights["relevance"]
            + personalization_score * weights["personalization"]
        )

        # Determine if refinement is needed
        needs_refinement = ensemble_score < settings.critique_ensemble_threshold

        # Synthesize feedback
        synthesis = {
            "ensemble_score": ensemble_score,
            "needs_refinement": needs_refinement,
            "scores": {
                "novelty": novelty_score,
                "coherence": coherence_score,
                "relevance": relevance_score,
                "personalization": personalization_score,
            },
            "agent_responses": {
                "novelty": novelty_response.content if novelty_response else None,
                "coherence": coherence_response.content if coherence_response else None,
                "relevance": relevance_response.content if relevance_response else None,
                "personalized": personalized_response.content if personalized_response else None,
            },
            "suggestions": self._extract_suggestions(
                novelty_response, coherence_response, relevance_response, personalized_response
            ),
        }

        logger.info(
            "Critique ensemble completed",
            ensemble_score=ensemble_score,
            needs_refinement=needs_refinement,
        )

        return synthesis

    def _extract_suggestions(self, *responses: Optional[AgentResponse]) -> List[str]:
        """Extract all suggestions from agent responses.

        Args:
            *responses: Agent responses

        Returns:
            Combined list of suggestions
        """
        all_suggestions = []

        for response in responses:
            if response and response.metadata:
                suggestions = response.metadata.get("suggestions", [])
                all_suggestions.extend(suggestions)

        # Deduplicate while preserving order
        seen = set()
        unique_suggestions = []
        for suggestion in all_suggestions:
            if suggestion not in seen:
                seen.add(suggestion)
                unique_suggestions.append(suggestion)

        return unique_suggestions[:10]  # Limit to top 10 suggestions
