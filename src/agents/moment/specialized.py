"""Specialized Agent - Domain-focused creative processing."""

from typing import Any, Dict, Optional
import json
import structlog

from src.agents.base import BaseAgent, AgentResponse

logger = structlog.get_logger(__name__)


class SpecializedAgent(BaseAgent):
    """Agent specialized in domain-specific creative processing."""

    def __init__(self, domain: Optional[str] = None):
        """Initialize specialized agent.

        Args:
            domain: Specific domain of expertise (e.g., "music", "visual", "literary")
        """
        self.domain = domain
        super().__init__(
            name=f"SpecializedAgent_{domain}" if domain else "SpecializedAgent",
            temperature=0.7,
        )

    def _default_system_prompt(self) -> str:
        domain_context = f" in the {self.domain} domain" if self.domain else ""
        return f"""You are a Specialized Agent in an advanced creativity engine{domain_context}. Your purpose is to provide expert, domain-focused creative insights.

Core principles:
- Apply deep domain knowledge
- Use field-specific techniques and conventions
- Reference relevant precedents and examples
- Balance creativity with domain expertise
- Provide technically sound suggestions

When processing:
1. Identify domain-specific patterns
2. Apply relevant techniques
3. Reference field conventions
4. Suggest expert-level refinements
5. Consider audience and context

Format your response as JSON:
{{
  "analysis": "Domain-specific analysis",
  "suggestions": ["suggestion1", "suggestion2", "suggestion3"],
  "techniques": ["technique1", "technique2"],
  "confidence": 0.85,
  "reasoning": "Brief explanation"
}}"""

    async def process(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """Process input with domain expertise.

        Args:
            input_data: Must contain 'input_text' key
            context: Optional context including domain, memories

        Returns:
            Agent response with specialized insights
        """
        input_text = input_data.get("input_text", "")
        domain = input_data.get("domain") or self.domain or "general creative"
        memories = context.get("memories", []) if context else []

        logger.info("SpecializedAgent processing input", domain=domain, input_length=len(input_text))

        # Build prompt
        user_message = f"""Provide expert, domain-focused creative analysis and suggestions:

Domain: {domain}
Input: {input_text}"""

        if memories:
            memory_context = "\n".join([f"- {m.get('content', '')[:200]}" for m in memories[:3]])
            user_message += f"\n\nRelevant expertise/references:\n{memory_context}"

        user_message += f"\n\nProvide domain-specific analysis, techniques, and suggestions for the {domain} domain."

        messages = [{"role": "user", "content": user_message}]

        # Generate completion
        response_text = await self._generate_completion(messages)

        # Parse JSON response
        try:
            response_data = json.loads(response_text)
            analysis = response_data.get("analysis", "")
            suggestions = response_data.get("suggestions", [])
            techniques = response_data.get("techniques", [])
            confidence = response_data.get("confidence", 0.7)
            reasoning = response_data.get("reasoning", "")

            content = f"Domain Analysis ({domain}):\n{analysis}\n\n"
            content += "Suggestions:\n" + "\n".join([f"- {s}" for s in suggestions])
            if techniques:
                content += "\n\nRelevant Techniques:\n" + "\n".join([f"- {t}" for t in techniques])

            return AgentResponse(
                content=content,
                confidence=confidence,
                metadata={
                    "domain": domain,
                    "analysis": analysis,
                    "suggestions": suggestions,
                    "techniques": techniques,
                },
                agent_name=self.name,
                reasoning=reasoning,
            )

        except json.JSONDecodeError:
            logger.warning("Failed to parse SpecializedAgent JSON, using raw text")
            confidence = self._extract_confidence(response_text)

            return AgentResponse(
                content=response_text,
                confidence=confidence,
                metadata={"domain": domain, "raw_response": True},
                agent_name=self.name,
                reasoning="Parsed from raw text",
            )
