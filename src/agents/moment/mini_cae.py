"""Mini-CAE Agent - Compact Creative Analysis and Enhancement."""

from typing import Any, Dict, Optional
import json
import structlog

from src.agents.base import BaseAgent, AgentResponse

logger = structlog.get_logger(__name__)


class MiniCAEAgent(BaseAgent):
    """Mini Creative Analysis and Enhancement Agent - focused, rapid improvements."""

    def __init__(self):
        super().__init__(
            name="MiniCAEAgent",
            temperature=0.6,
        )

    def _default_system_prompt(self) -> str:
        return """You are a Mini-CAE (Creative Analysis and Enhancement) Agent in an advanced creativity engine. Your purpose is to provide focused, rapid creative analysis and enhancement.

Core principles:
- Quick, actionable insights
- Focus on immediate improvements
- Identify key strengths and weaknesses
- Suggest specific enhancements
- Maintain creative momentum

When analyzing:
1. Identify core creative elements
2. Highlight strengths
3. Spot improvement opportunities
4. Suggest specific enhancements
5. Maintain original intent

Format your response as JSON:
{
  "strengths": ["strength1", "strength2"],
  "opportunities": ["opportunity1", "opportunity2"],
  "enhancements": ["enhancement1", "enhancement2"],
  "confidence": 0.85,
  "reasoning": "Brief explanation"
}"""

    async def process(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """Analyze and enhance creative content.

        Args:
            input_data: Must contain 'input_text' or 'content' key
            context: Optional context

        Returns:
            Agent response with analysis and enhancements
        """
        content = input_data.get("content") or input_data.get("input_text", "")

        logger.info("MiniCAEAgent processing content", content_length=len(content))

        # Build prompt
        user_message = f"""Analyze this creative content and suggest enhancements:

Content: {content}

Provide:
1. Key strengths of this content
2. Opportunities for improvement
3. Specific enhancement suggestions"""

        messages = [{"role": "user", "content": user_message}]

        # Generate completion
        response_text = await self._generate_completion(messages)

        # Parse JSON response
        try:
            response_data = json.loads(response_text)
            strengths = response_data.get("strengths", [])
            opportunities = response_data.get("opportunities", [])
            enhancements = response_data.get("enhancements", [])
            confidence = response_data.get("confidence", 0.7)
            reasoning = response_data.get("reasoning", "")

            content_response = "Creative Analysis:\n\n"
            content_response += "Strengths:\n" + "\n".join([f"- {s}" for s in strengths])
            content_response += "\n\nOpportunities:\n" + "\n".join([f"- {o}" for o in opportunities])
            content_response += "\n\nEnhancements:\n" + "\n".join([f"- {e}" for e in enhancements])

            return AgentResponse(
                content=content_response,
                confidence=confidence,
                metadata={
                    "strengths": strengths,
                    "opportunities": opportunities,
                    "enhancements": enhancements,
                },
                agent_name=self.name,
                reasoning=reasoning,
            )

        except json.JSONDecodeError:
            logger.warning("Failed to parse MiniCAEAgent JSON, using raw text")
            confidence = self._extract_confidence(response_text)

            return AgentResponse(
                content=response_text,
                confidence=confidence,
                metadata={"raw_response": True},
                agent_name=self.name,
                reasoning="Parsed from raw text",
            )
