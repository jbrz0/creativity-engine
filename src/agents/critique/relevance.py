"""Relevance Critique Agent - Evaluates relevance to input and goals."""

from typing import Any, Dict, Optional
import json
import structlog

from src.agents.base import BaseAgent, AgentResponse

logger = structlog.get_logger(__name__)


class RelevanceCritiqueAgent(BaseAgent):
    """Agent specialized in evaluating relevance to input, goals, and context."""

    def __init__(self):
        super().__init__(
            name="RelevanceCritiqueAgent",
            temperature=0.4,
        )

    def _default_system_prompt(self) -> str:
        return """You are a Relevance Critique Agent in an advanced creativity engine. Your purpose is to evaluate how well creative outputs address the input, goals, and context.

Evaluation criteria:
- Input alignment: Does it address the original input?
- Goal fulfillment: Does it meet stated objectives?
- Context appropriateness: Is it suitable for the context?
- Audience fit: Does it match the target audience?
- Practical applicability: Can it be implemented/used?

When evaluating:
1. Assess relevance on a 0-1 scale
2. Identify aligned elements
3. Note divergences or gaps
4. Evaluate contextual fit
5. Suggest refinements

Format your response as JSON:
{
  "relevance_score": 0.85,
  "aligned_elements": ["element1", "element2"],
  "divergences": ["divergence1", "divergence2"],
  "context_fit": "Brief context evaluation",
  "suggestions": ["suggestion1", "suggestion2"],
  "confidence": 0.90,
  "reasoning": "Brief explanation"
}"""

    async def process(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """Evaluate relevance of creative output.

        Args:
            input_data: Must contain 'content' to evaluate
            context: Should contain 'original_input' and optionally 'goals'

        Returns:
            Agent response with relevance evaluation
        """
        content = input_data.get("content", "")
        original_input = context.get("original_input", "") if context else ""
        goals = context.get("goals", []) if context else []

        logger.info("RelevanceCritiqueAgent evaluating content", content_length=len(content))

        # Build prompt
        user_message = f"""Evaluate the relevance of this creative output to the original input and goals:

Content to evaluate: {content}

Original input: {original_input}"""

        if goals:
            user_message += f"\n\nGoals: {', '.join(goals)}"

        user_message += "\n\nProvide a comprehensive relevance evaluation with score, aligned elements, and suggestions."

        messages = [{"role": "user", "content": user_message}]

        # Generate completion
        response_text = await self._generate_completion(messages)

        # Parse JSON response
        try:
            response_data = json.loads(response_text)
            relevance_score = response_data.get("relevance_score", 0.7)
            aligned_elements = response_data.get("aligned_elements", [])
            divergences = response_data.get("divergences", [])
            context_fit = response_data.get("context_fit", "")
            suggestions = response_data.get("suggestions", [])
            confidence = response_data.get("confidence", 0.8)
            reasoning = response_data.get("reasoning", "")

            content_response = f"Relevance Score: {relevance_score:.2f}\n\n"
            if context_fit:
                content_response += f"Context Fit:\n{context_fit}\n\n"
            content_response += "Aligned Elements:\n" + "\n".join([f"- {e}" for e in aligned_elements])
            if divergences:
                content_response += "\n\nDivergences/Gaps:\n" + "\n".join(
                    [f"- {d}" for d in divergences]
                )
            if suggestions:
                content_response += "\n\nSuggestions:\n" + "\n".join([f"- {s}" for s in suggestions])

            return AgentResponse(
                content=content_response,
                confidence=confidence,
                metadata={
                    "relevance_score": relevance_score,
                    "aligned_elements": aligned_elements,
                    "divergences": divergences,
                    "context_fit": context_fit,
                    "suggestions": suggestions,
                },
                agent_name=self.name,
                reasoning=reasoning,
            )

        except json.JSONDecodeError:
            logger.warning("Failed to parse RelevanceCritiqueAgent JSON, using raw text")
            confidence = self._extract_confidence(response_text)

            return AgentResponse(
                content=response_text,
                confidence=confidence,
                metadata={"raw_response": True},
                agent_name=self.name,
                reasoning="Parsed from raw text",
            )
