"""Idea CAE Agent - Comprehensive creative idea development and enhancement."""

from typing import Any, Dict, Optional
import json
import structlog

from src.agents.base import BaseAgent, AgentResponse

logger = structlog.get_logger(__name__)


class IdeaCAEAgent(BaseAgent):
    """Idea Creative Analysis and Enhancement Agent - comprehensive idea development."""

    def __init__(self):
        super().__init__(
            name="IdeaCAEAgent",
            temperature=0.75,
        )

    def _default_system_prompt(self) -> str:
        return """You are an Idea-CAE (Creative Analysis and Enhancement) Agent in an advanced creativity engine. Your purpose is to deeply develop and enhance creative ideas.

Core principles:
- Comprehensive idea exploration
- Multi-dimensional development
- Consider implications and variations
- Build depth and richness
- Maintain creative coherence

When developing ideas:
1. Expand the core concept
2. Explore multiple dimensions
3. Consider variations and alternatives
4. Develop supporting elements
5. Create implementation pathways

Format your response as JSON:
{
  "core_concept": "Refined core idea",
  "dimensions": ["dimension1", "dimension2", "dimension3"],
  "variations": ["variation1", "variation2"],
  "supporting_elements": ["element1", "element2"],
  "implementation": ["step1", "step2"],
  "confidence": 0.85,
  "reasoning": "Brief explanation"
}"""

    async def process(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """Develop and enhance creative ideas comprehensively.

        Args:
            input_data: Must contain 'idea' or 'input_text' key
            context: Optional context including previous agent outputs

        Returns:
            Agent response with developed idea
        """
        idea = input_data.get("idea") or input_data.get("input_text", "")
        previous_outputs = context.get("agent_outputs", []) if context else []

        logger.info("IdeaCAEAgent processing idea", idea_length=len(idea))

        # Build prompt
        user_message = f"""Comprehensively develop and enhance this creative idea:

Idea: {idea}"""

        if previous_outputs:
            context_text = "\n\n".join(
                [f"{out.get('agent', 'Agent')}: {out.get('content', '')[:300]}" for out in previous_outputs[:3]]
            )
            user_message += f"\n\nPrevious insights:\n{context_text}"

        user_message += "\n\nProvide comprehensive idea development including dimensions, variations, and implementation."

        messages = [{"role": "user", "content": user_message}]

        # Generate completion
        response_text = await self._generate_completion(messages)

        # Parse JSON response
        try:
            response_data = json.loads(response_text)
            core_concept = response_data.get("core_concept", "")
            dimensions = response_data.get("dimensions", [])
            variations = response_data.get("variations", [])
            supporting_elements = response_data.get("supporting_elements", [])
            implementation = response_data.get("implementation", [])
            confidence = response_data.get("confidence", 0.7)
            reasoning = response_data.get("reasoning", "")

            content = f"Core Concept:\n{core_concept}\n\n"
            content += "Dimensions:\n" + "\n".join([f"- {d}" for d in dimensions])
            if variations:
                content += "\n\nVariations:\n" + "\n".join([f"- {v}" for v in variations])
            if supporting_elements:
                content += "\n\nSupporting Elements:\n" + "\n".join([f"- {s}" for s in supporting_elements])
            if implementation:
                content += "\n\nImplementation Path:\n" + "\n".join([f"{i+1}. {step}" for i, step in enumerate(implementation)])

            return AgentResponse(
                content=content,
                confidence=confidence,
                metadata={
                    "core_concept": core_concept,
                    "dimensions": dimensions,
                    "variations": variations,
                    "supporting_elements": supporting_elements,
                    "implementation": implementation,
                },
                agent_name=self.name,
                reasoning=reasoning,
            )

        except json.JSONDecodeError:
            logger.warning("Failed to parse IdeaCAEAgent JSON, using raw text")
            confidence = self._extract_confidence(response_text)

            return AgentResponse(
                content=response_text,
                confidence=confidence,
                metadata={"raw_response": True},
                agent_name=self.name,
                reasoning="Parsed from raw text",
            )
