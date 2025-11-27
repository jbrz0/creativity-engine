"""Coherence Critique Agent - Evaluates logical consistency and flow."""

from typing import Any, Dict, Optional
import json
import structlog

from src.agents.base import BaseAgent, AgentResponse

logger = structlog.get_logger(__name__)


class CoherenceCritiqueAgent(BaseAgent):
    """Agent specialized in evaluating coherence, consistency, and logical flow."""

    def __init__(self):
        super().__init__(
            name="CoherenceCritiqueAgent",
            temperature=0.4,
        )

    def _default_system_prompt(self) -> str:
        return """You are a Coherence Critique Agent in an advanced creativity engine. Your purpose is to evaluate the logical consistency, flow, and internal coherence of creative outputs.

Evaluation criteria:
- Internal consistency: Do all parts work together?
- Logical flow: Is the progression natural and sensible?
- Structural integrity: Is the organization sound?
- Clarity: Is the message clear and understandable?
- Unity: Do elements support a cohesive whole?

When evaluating:
1. Assess coherence on a 0-1 scale
2. Identify strong connections
3. Spot inconsistencies or gaps
4. Evaluate flow and structure
5. Suggest improvements

Format your response as JSON:
{
  "coherence_score": 0.85,
  "strengths": ["strength1", "strength2"],
  "inconsistencies": ["issue1", "issue2"],
  "flow_assessment": "Brief flow evaluation",
  "suggestions": ["suggestion1", "suggestion2"],
  "confidence": 0.90,
  "reasoning": "Brief explanation"
}"""

    async def process(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """Evaluate coherence of creative output.

        Args:
            input_data: Must contain 'content' to evaluate
            context: Optional context

        Returns:
            Agent response with coherence evaluation
        """
        content = input_data.get("content", "")

        logger.info("CoherenceCritiqueAgent evaluating content", content_length=len(content))

        # Build prompt
        user_message = f"""Evaluate the coherence, consistency, and logical flow of this creative output:

Content to evaluate: {content}

Provide a comprehensive coherence evaluation with score, strengths, inconsistencies, and suggestions."""

        messages = [{"role": "user", "content": user_message}]

        # Generate completion
        response_text = await self._generate_completion(messages)

        # Parse JSON response
        try:
            response_data = json.loads(response_text)
            coherence_score = response_data.get("coherence_score", 0.7)
            strengths = response_data.get("strengths", [])
            inconsistencies = response_data.get("inconsistencies", [])
            flow_assessment = response_data.get("flow_assessment", "")
            suggestions = response_data.get("suggestions", [])
            confidence = response_data.get("confidence", 0.8)
            reasoning = response_data.get("reasoning", "")

            content_response = f"Coherence Score: {coherence_score:.2f}\n\n"
            if flow_assessment:
                content_response += f"Flow Assessment:\n{flow_assessment}\n\n"
            content_response += "Strengths:\n" + "\n".join([f"- {s}" for s in strengths])
            if inconsistencies:
                content_response += "\n\nAreas for Improvement:\n" + "\n".join(
                    [f"- {i}" for i in inconsistencies]
                )
            if suggestions:
                content_response += "\n\nSuggestions:\n" + "\n".join([f"- {s}" for s in suggestions])

            return AgentResponse(
                content=content_response,
                confidence=confidence,
                metadata={
                    "coherence_score": coherence_score,
                    "strengths": strengths,
                    "inconsistencies": inconsistencies,
                    "flow_assessment": flow_assessment,
                    "suggestions": suggestions,
                },
                agent_name=self.name,
                reasoning=reasoning,
            )

        except json.JSONDecodeError:
            logger.warning("Failed to parse CoherenceCritiqueAgent JSON, using raw text")
            confidence = self._extract_confidence(response_text)

            return AgentResponse(
                content=response_text,
                confidence=confidence,
                metadata={"raw_response": True},
                agent_name=self.name,
                reasoning="Parsed from raw text",
            )
