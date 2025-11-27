"""Analogy Engine - Generate and manage creative analogies and metaphors."""

from typing import List, Dict, Any, Optional
import json
import structlog

from src.utils.openrouter import get_openrouter_client
from src.models.memory import Memory

logger = structlog.get_logger(__name__)


class AnalogyEngine:
    """Generates and evaluates creative analogies and metaphors."""

    def __init__(self):
        """Initialize analogy engine."""
        self.client = None

    async def _ensure_client(self):
        """Ensure OpenRouter client is initialized."""
        if self.client is None:
            self.client = await get_openrouter_client()
        return self.client

    async def generate_analogies(
        self,
        concept: str,
        context: Optional[str] = None,
        count: int = 5,
    ) -> List[Dict[str, Any]]:
        """Generate creative analogies for a concept.

        Args:
            concept: Concept to create analogies for
            context: Optional context
            count: Number of analogies to generate

        Returns:
            List of analogies with metadata
        """
        logger.info("Generating analogies", concept_length=len(concept), count=count)

        client = await self._ensure_client()

        prompt = f"""Generate {count} creative and insightful analogies for the following concept:

Concept: {concept}"""

        if context:
            prompt += f"\nContext: {context}"

        prompt += f"""

For each analogy:
1. Create a meaningful comparison
2. Explain the connection
3. Rate the strength (0.0 to 1.0)

Format as JSON:
{{
  "analogies": [
    {{
      "analogy": "The analogy statement",
      "explanation": "Why this comparison works",
      "strength": 0.85,
      "domains": ["source_domain", "target_domain"]
    }}
  ]
}}"""

        messages = [
            {
                "role": "system",
                "content": "You are an expert at creating insightful analogies and metaphors.",
            },
            {"role": "user", "content": prompt},
        ]

        response = await client.fast_completion(messages)

        try:
            data = json.loads(response)
            analogies = data.get("analogies", [])

            logger.info("Generated analogies", count=len(analogies))

            return analogies

        except json.JSONDecodeError:
            logger.warning("Failed to parse analogy JSON response")
            # Return simple fallback
            return [
                {
                    "analogy": response[:200],
                    "explanation": "Raw response",
                    "strength": 0.5,
                    "domains": ["general"],
                }
            ]

    async def find_metaphorical_connections(
        self,
        source: str,
        targets: List[str],
    ) -> List[Dict[str, Any]]:
        """Find metaphorical connections between source and targets.

        Args:
            source: Source concept
            targets: List of target concepts

        Returns:
            List of metaphorical connections
        """
        logger.info(
            "Finding metaphorical connections",
            source_length=len(source),
            target_count=len(targets),
        )

        client = await self._ensure_client()

        prompt = f"""Identify metaphorical connections between the source and each target:

Source: {source}

Targets:
{chr(10).join([f"- {t}" for t in targets])}

For each target, identify:
1. The metaphorical relationship
2. Shared properties or patterns
3. Creative insights from the connection

Format as JSON:
{{
  "connections": [
    {{
      "target": "target_name",
      "relationship": "description of metaphorical relationship",
      "shared_properties": ["property1", "property2"],
      "insights": ["insight1", "insight2"],
      "strength": 0.75
    }}
  ]
}}"""

        messages = [
            {
                "role": "system",
                "content": "You are an expert at identifying metaphorical relationships and creative connections.",
            },
            {"role": "user", "content": prompt},
        ]

        response = await client.fast_completion(messages)

        try:
            data = json.loads(response)
            connections = data.get("connections", [])

            logger.info("Found metaphorical connections", count=len(connections))

            return connections

        except json.JSONDecodeError:
            logger.warning("Failed to parse metaphor JSON response")
            return []

    async def evaluate_analogy_quality(
        self,
        analogy: str,
        source_concept: str,
        target_concept: str,
    ) -> Dict[str, Any]:
        """Evaluate the quality of an analogy.

        Args:
            analogy: The analogy to evaluate
            source_concept: Source concept
            target_concept: Target concept

        Returns:
            Evaluation metrics
        """
        client = await self._ensure_client()

        prompt = f"""Evaluate this analogy:

Analogy: {analogy}
Source: {source_concept}
Target: {target_concept}

Rate the analogy on:
1. Clarity (0.0 to 1.0): How clear is the comparison?
2. Insightfulness (0.0 to 1.0): How insightful is the connection?
3. Relevance (0.0 to 1.0): How relevant is it to the concepts?
4. Creativity (0.0 to 1.0): How creative is the comparison?

Format as JSON:
{{
  "clarity": 0.85,
  "insightfulness": 0.90,
  "relevance": 0.80,
  "creativity": 0.75,
  "overall_score": 0.825,
  "feedback": "Brief evaluation"
}}"""

        messages = [{"role": "user", "content": prompt}]

        response = await client.fast_completion(messages)

        try:
            evaluation = json.loads(response)
            return evaluation

        except json.JSONDecodeError:
            logger.warning("Failed to parse analogy evaluation")
            return {
                "clarity": 0.5,
                "insightfulness": 0.5,
                "relevance": 0.5,
                "creativity": 0.5,
                "overall_score": 0.5,
                "feedback": "Could not evaluate",
            }

    async def generate_from_memories(
        self,
        concept: str,
        memories: List[Memory],
        count: int = 3,
    ) -> List[Dict[str, Any]]:
        """Generate analogies using memory context.

        Args:
            concept: Concept to create analogies for
            memories: Relevant memories to draw from
            count: Number of analogies

        Returns:
            List of memory-informed analogies
        """
        if not memories:
            return await self.generate_analogies(concept, count=count)

        # Build context from memories
        memory_context = "\n".join([f"- {m.content[:200]}" for m in memories[:5]])

        context = f"Draw inspiration from these related memories:\n{memory_context}"

        return await self.generate_analogies(concept, context=context, count=count)
