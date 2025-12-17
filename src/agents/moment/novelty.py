"""Novelty Agent - Generates novel and creative ideas."""

from typing import Any, Dict, Optional
import json
import structlog

from src.agents.base import BaseAgent, AgentResponse

logger = structlog.get_logger(__name__)


class NoveltyAgent(BaseAgent):
    """Agent specialized in generating novel and unexpected creative outputs."""

    def __init__(self):
        super().__init__(
            name="NoveltyAgent",
            temperature=0.9,  # Higher temperature for more creativity
        )

    def _default_system_prompt(self) -> str:
        return """You are a Novelty Agent in an advanced creativity engine. Your purpose is to generate highly novel, unexpected, and creative ideas.

Core principles:
- Push boundaries and explore unconventional combinations
- Break patterns and challenge assumptions
- Generate surprising connections and analogies
- Prioritize originality over convention
- Think laterally and divergently

When generating ideas:
1. Identify unexpected connections
2. Combine disparate concepts
3. Invert common assumptions
4. Explore metaphorical spaces
5. Generate multiple novel angles

Format your response as JSON:
{
  "ideas": ["idea1", "idea2", "idea3"],
  "novel_connections": ["connection1", "connection2"],
  "confidence": 0.85,
  "reasoning": "Brief explanation of your creative process"
}"""

    async def process(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """Generate novel creative ideas.

        Args:
            input_data: Must contain 'input_text' key
            context: Optional context including memories, preferences

        Returns:
            Agent response with novel ideas
        """
        input_text = input_data.get("input_text", "")
        memories = context.get("memories", []) if context else []
        
        # Check for creative config
        creative_config = context.get("creative_config") if context else None
        
        # Override sampling if present
        if creative_config and "sampling" in creative_config:
             sampling = creative_config["sampling"]
             temperature = sampling.get("temperature", self.temperature)
        else:
             temperature = self.temperature

        logger.info("NoveltyAgent processing input", input_length=len(input_text), temperature=temperature)

        # Build prompt
        user_message = f"""Generate highly novel and creative ideas based on this input:

Input: {input_text}"""

        if memories:
            memory_context = "\n".join([f"- {m.get('content', '')[:200]}" for m in memories[:5]])
            user_message += f"\n\nRelevant context/memories:\n{memory_context}"
            
        # Inject Seeds & Insights from creative control config
        if creative_config:
            seeds = creative_config.get("seeds", [])
            insights = creative_config.get("insights", "")
            
            if seeds:
                user_message += f"\n\nSerendipity Seeds (use these as random stimuli):\n" + ", ".join(seeds)
            if insights:
                user_message += f"\n\nGraph Insights:\n{insights}"
                
            speculation_level = creative_config["sliders"]["speculation"]
            if speculation_level > 60:
                user_message += "\n\nApply HIGH SPECULATION: Take wild creative risks. Ignore conventional constraints."
            
            # Stochastic walk instruction
            branches = creative_config["kernel"]["what_if_branches"]
            if branches > 1:
                user_message += f"\n\nExplore at least {branches} distinct 'What-if' scenarios or branches."

        user_message += "\n\nGenerate multiple novel ideas and unexpected connections."

        messages = [{"role": "user", "content": user_message}]

        # Generate completion
        response_text = await self._generate_completion(messages, temperature=temperature)

        # Parse JSON response
        try:
            response_data = json.loads(response_text)
            ideas = response_data.get("ideas", [])
            connections = response_data.get("novel_connections", [])
            confidence = response_data.get("confidence", 0.7)
            reasoning = response_data.get("reasoning", "")

            content = f"Novel Ideas:\n" + "\n".join([f"- {idea}" for idea in ideas])
            if connections:
                content += f"\n\nNovel Connections:\n" + "\n".join(
                    [f"- {conn}" for conn in connections]
                )

            return AgentResponse(
                content=content,
                confidence=confidence,
                metadata={
                    "ideas": ideas,
                    "novel_connections": connections,
                    "idea_count": len(ideas),
                },
                agent_name=self.name,
                reasoning=reasoning,
            )

        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            logger.warning("Failed to parse NoveltyAgent JSON, using raw text")
            confidence = self._extract_confidence(response_text)

            return AgentResponse(
                content=response_text,
                confidence=confidence,
                metadata={"raw_response": True},
                agent_name=self.name,
                reasoning="Parsed from raw text",
            )
