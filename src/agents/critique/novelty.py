"""Novelty Critique Agent - Evaluates novelty and originality."""

from typing import Any, Dict, Optional
import json
import structlog

from src.agents.base import BaseAgent, AgentResponse

logger = structlog.get_logger(__name__)


class NoveltyCritiqueAgent(BaseAgent):
    """Agent specialized in evaluating novelty and originality of creative outputs."""

    def __init__(self):
        super().__init__(
            name="NoveltyCritiqueAgent",
            temperature=0.5,  # Lower temperature for consistent evaluation
        )

    def _default_system_prompt(self) -> str:
        return """You are a Novelty Critique Agent in an advanced creativity engine. Your purpose is to evaluate the novelty, originality, and uniqueness of creative outputs.

Evaluation criteria:
- Originality: How unique and unprecedented is the idea?
- Unexpectedness: Does it surprise or challenge expectations?
- Pattern breaking: Does it deviate from conventional approaches?
- Fresh perspective: Does it offer new viewpoints?
- Innovation: Does it introduce new combinations or concepts?

When evaluating:
1. Assess originality on a 0-1 scale
2. Identify novel elements
3. Compare against common patterns
4. Note unexpected aspects
5. Provide constructive feedback

Format your response as JSON:
{
  "novelty_score": 0.85,
  "novel_elements": ["element1", "element2"],
  "conventional_aspects": ["aspect1", "aspect2"],
  "suggestions": ["suggestion1", "suggestion2"],
  "confidence": 0.90,
  "reasoning": "Brief explanation"
}"""

    async def process(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """Evaluate novelty of creative output.

        Args:
            input_data: Must contain 'content' to evaluate
            context: Optional context including original input

        Returns:
            Agent response with novelty evaluation
        """
        content = input_data.get("content", "")
        original_input = context.get("original_input", "") if context else ""

        logger.info("NoveltyCritiqueAgent evaluating content", content_length=len(content))

        # Build prompt
        user_message = f"""Evaluate the novelty and originality of this creative output:

Content to evaluate: {content}"""

        if original_input:
            user_message += f"\n\nOriginal input: {original_input}"

        user_message += "\n\nProvide a comprehensive novelty evaluation with score, novel elements, and suggestions."

        messages = [{"role": "user", "content": user_message}]

        # Generate completion
        response_text = await self._generate_completion(messages)

        # Parse JSON response
        try:
            response_data = json.loads(response_text)
            novelty_score = response_data.get("novelty_score", 0.7)
            novel_elements = response_data.get("novel_elements", [])
            conventional_aspects = response_data.get("conventional_aspects", [])
            suggestions = response_data.get("suggestions", [])
            confidence = response_data.get("confidence", 0.8)
            reasoning = response_data.get("reasoning", "")

            content_response = f"Novelty Score: {novelty_score:.2f}\n\n"
            content_response += "Novel Elements:\n" + "\n".join([f"- {e}" for e in novel_elements])
            if conventional_aspects:
                content_response += "\n\nConventional Aspects:\n" + "\n".join(
                    [f"- {a}" for a in conventional_aspects]
                )
            if suggestions:
                content_response += "\n\nSuggestions for Enhancement:\n" + "\n".join(
                    [f"- {s}" for s in suggestions]
                )

            return AgentResponse(
                content=content_response,
                confidence=confidence,
                metadata={
                    "novelty_score": novelty_score,
                    "novel_elements": novel_elements,
                    "conventional_aspects": conventional_aspects,
                    "suggestions": suggestions,
                },
                agent_name=self.name,
                reasoning=reasoning,
            )

        except json.JSONDecodeError:
            logger.warning("Failed to parse NoveltyCritiqueAgent JSON, using raw text")
            confidence = self._extract_confidence(response_text)

            return AgentResponse(
                content=response_text,
                confidence=confidence,
                metadata={"raw_response": True},
                agent_name=self.name,
                reasoning="Parsed from raw text",
            )
