"""Personalized Critique Agent - Evaluates personalization and user fit."""

from typing import Any, Dict, Optional
import json
import structlog

from src.agents.base import BaseAgent, AgentResponse

logger = structlog.get_logger(__name__)


class PersonalizedCritiqueAgent(BaseAgent):
    """Agent specialized in evaluating personalization and user-specific fit."""

    def __init__(self):
        super().__init__(
            name="PersonalizedCritiqueAgent",
            temperature=0.5,
        )

    def _default_system_prompt(self) -> str:
        return """You are a Personalized Critique Agent in an advanced creativity engine. Your purpose is to evaluate how well creative outputs match user preferences, style, and identity.

Evaluation criteria:
- Style match: Does it align with user's preferred style?
- Identity preservation: Does it maintain user's voice/identity?
- Preference alignment: Does it match stated preferences?
- Tone appropriateness: Is the tone suitable for the user?
- Personal resonance: Will it resonate with the user?

When evaluating:
1. Assess personalization on a 0-1 scale
2. Identify style-matched elements
3. Note style mismatches
4. Evaluate identity preservation
5. Suggest personalized refinements

Format your response as JSON:
{
  "personalization_score": 0.85,
  "style_matches": ["match1", "match2"],
  "style_mismatches": ["mismatch1", "mismatch2"],
  "identity_assessment": "Brief identity evaluation",
  "suggestions": ["suggestion1", "suggestion2"],
  "confidence": 0.90,
  "reasoning": "Brief explanation"
}"""

    async def process(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """Evaluate personalization of creative output.

        Args:
            input_data: Must contain 'content' to evaluate
            context: Should contain 'user_preferences', 'user_style', etc.

        Returns:
            Agent response with personalization evaluation
        """
        content = input_data.get("content", "")
        user_preferences = context.get("user_preferences", {}) if context else {}
        user_style = context.get("user_style", "") if context else ""
        user_history = context.get("user_history", []) if context else []

        logger.info("PersonalizedCritiqueAgent evaluating content", content_length=len(content))

        # Build prompt
        user_message = f"""Evaluate the personalization and user-fit of this creative output:

Content to evaluate: {content}"""

        if user_preferences:
            pref_str = "\n".join([f"- {k}: {v}" for k, v in user_preferences.items()])
            user_message += f"\n\nUser preferences:\n{pref_str}"

        if user_style:
            user_message += f"\n\nUser style: {user_style}"

        if user_history:
            history_str = "\n".join([f"- {h[:200]}" for h in user_history[:3]])
            user_message += f"\n\nUser history (examples):\n{history_str}"

        user_message += "\n\nProvide a comprehensive personalization evaluation with score and suggestions."

        messages = [{"role": "user", "content": user_message}]

        # Generate completion
        response_text = await self._generate_completion(messages)

        # Parse JSON response
        try:
            response_data = json.loads(response_text)
            personalization_score = response_data.get("personalization_score", 0.7)
            style_matches = response_data.get("style_matches", [])
            style_mismatches = response_data.get("style_mismatches", [])
            identity_assessment = response_data.get("identity_assessment", "")
            suggestions = response_data.get("suggestions", [])
            confidence = response_data.get("confidence", 0.8)
            reasoning = response_data.get("reasoning", "")

            content_response = f"Personalization Score: {personalization_score:.2f}\n\n"
            if identity_assessment:
                content_response += f"Identity Assessment:\n{identity_assessment}\n\n"
            content_response += "Style Matches:\n" + "\n".join([f"- {m}" for m in style_matches])
            if style_mismatches:
                content_response += "\n\nStyle Mismatches:\n" + "\n".join(
                    [f"- {m}" for m in style_mismatches]
                )
            if suggestions:
                content_response += "\n\nPersonalization Suggestions:\n" + "\n".join(
                    [f"- {s}" for s in suggestions]
                )

            return AgentResponse(
                content=content_response,
                confidence=confidence,
                metadata={
                    "personalization_score": personalization_score,
                    "style_matches": style_matches,
                    "style_mismatches": style_mismatches,
                    "identity_assessment": identity_assessment,
                    "suggestions": suggestions,
                },
                agent_name=self.name,
                reasoning=reasoning,
            )

        except json.JSONDecodeError:
            logger.warning("Failed to parse PersonalizedCritiqueAgent JSON, using raw text")
            confidence = self._extract_confidence(response_text)

            return AgentResponse(
                content=response_text,
                confidence=confidence,
                metadata={"raw_response": True},
                agent_name=self.name,
                reasoning="Parsed from raw text",
            )
