"""Synthesis Orchestra - Merges and synthesizes outputs from multiple agents."""

from typing import List, Dict, Any, Optional
import asyncio
import json
import structlog

from src.agents.base import AgentResponse
from src.utils.openrouter import get_openrouter_client
from src.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class SynthesisOrchestra:
    """Orchestrates the synthesis of multiple agent outputs into a cohesive result."""

    def __init__(self):
        """Initialize synthesis orchestra."""
        self.client = None

    async def _ensure_client(self):
        """Ensure OpenRouter client is initialized."""
        if self.client is None:
            self.client = await get_openrouter_client()
        return self.client

    async def merge_outputs(
        self,
        agent_responses: List[AgentResponse],
        synthesis_strategy: str = "comprehensive",
    ) -> str:
        """Merge multiple agent outputs into a single synthesis.

        Args:
            agent_responses: List of agent responses
            synthesis_strategy: "comprehensive", "best_of", or "hybrid"

        Returns:
            Synthesized output
        """
        logger.info(
            "Merging agent outputs",
            agent_count=len(agent_responses),
            strategy=synthesis_strategy,
        )

        client = await self._ensure_client()

        # Build synthesis prompt
        agent_outputs = []
        for response in agent_responses:
            agent_outputs.append(
                {
                    "agent": response.agent_name,
                    "content": response.content,
                    "confidence": response.confidence,
                    "metadata": response.metadata,
                }
            )

        outputs_text = "\n\n".join(
            [
                f"[{out['agent']}] (Confidence: {out['confidence']:.2f})\n{out['content']}"
                for out in agent_outputs
            ]
        )

        if synthesis_strategy == "comprehensive":
            prompt = f"""Synthesize these creative outputs into a comprehensive, cohesive result:

{outputs_text}

Create a synthesis that:
1. Incorporates the best ideas from each agent
2. Maintains creative coherence
3. Builds depth and richness
4. Resolves any conflicts or redundancies
5. Produces a polished, unified output

Provide the synthesized creative output:"""

        elif synthesis_strategy == "best_of":
            prompt = f"""Select and refine the best elements from these creative outputs:

{outputs_text}

Create a synthesis that:
1. Identifies the strongest ideas
2. Selects the most promising elements
3. Refines and polishes them
4. Combines into a focused output

Provide the refined creative output:"""

        else:  # hybrid
            prompt = f"""Create a hybrid synthesis from these creative outputs:

{outputs_text}

Create a synthesis that:
1. Balances multiple perspectives
2. Combines complementary ideas
3. Creates something greater than the sum of parts
4. Maintains originality and coherence

Provide the hybrid creative output:"""

        messages = [
            {
                "role": "system",
                "content": "You are an expert at synthesizing creative outputs into cohesive, polished results.",
            },
            {"role": "user", "content": prompt},
        ]

        synthesized = await client.main_completion(messages, temperature=0.7)

        logger.info("Synthesis completed", output_length=len(synthesized))

        return synthesized

    async def parallel_merge(
        self,
        agent_responses: List[AgentResponse],
    ) -> Dict[str, str]:
        """Create multiple parallel synthesis variants.

        Args:
            agent_responses: List of agent responses

        Returns:
            Dictionary with different synthesis variants
        """
        logger.info("Creating parallel synthesis variants", agent_count=len(agent_responses))

        # Run multiple synthesis strategies in parallel
        results = await asyncio.gather(
            self.merge_outputs(agent_responses, "comprehensive"),
            self.merge_outputs(agent_responses, "best_of"),
            self.merge_outputs(agent_responses, "hybrid"),
            return_exceptions=True,
        )

        variants = {
            "comprehensive": results[0] if not isinstance(results[0], Exception) else "",
            "best_of": results[1] if not isinstance(results[1], Exception) else "",
            "hybrid": results[2] if not isinstance(results[2], Exception) else "",
        }

        return variants

    async def synthesize_with_metadata(
        self,
        agent_responses: List[AgentResponse],
        original_input: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Synthesize outputs with detailed metadata.

        Args:
            agent_responses: List of agent responses
            original_input: Original user input
            context: Optional context

        Returns:
            Synthesis with metadata
        """
        logger.info("Synthesizing with metadata", agent_count=len(agent_responses))

        # Perform synthesis
        synthesized_text = await self.merge_outputs(agent_responses, "comprehensive")

        # Calculate aggregate metadata
        avg_confidence = (
            sum(r.confidence for r in agent_responses) / len(agent_responses)
            if agent_responses
            else 0.5
        )

        # Collect all metadata
        all_metadata = {}
        for response in agent_responses:
            all_metadata[response.agent_name] = response.metadata

        result = {
            "synthesized_output": synthesized_text,
            "original_input": original_input,
            "aggregate_confidence": avg_confidence,
            "agent_count": len(agent_responses),
            "agent_metadata": all_metadata,
            "synthesis_strategy": "comprehensive",
        }

        return result

    async def weighted_synthesis(
        self,
        agent_responses: List[AgentResponse],
        weights: Optional[Dict[str, float]] = None,
    ) -> str:
        """Create weighted synthesis based on agent confidence or custom weights.

        Args:
            agent_responses: List of agent responses
            weights: Optional custom weights by agent name

        Returns:
            Weighted synthesis
        """
        if not agent_responses:
            return ""

        # Use confidence as default weights if not provided
        if not weights:
            total_confidence = sum(r.confidence for r in agent_responses)
            weights = {
                r.agent_name: r.confidence / total_confidence for r in agent_responses
            }

        # Build weighted prompt
        client = await self._ensure_client()

        weighted_outputs = "\n\n".join(
            [
                f"[{r.agent_name}] (Weight: {weights.get(r.agent_name, 0.0):.2f})\n{r.content}"
                for r in agent_responses
            ]
        )

        prompt = f"""Create a weighted synthesis from these outputs, giving more emphasis to higher-weighted contributions:

{weighted_outputs}

Synthesize into a cohesive output that respects the weights while maintaining quality and coherence:"""

        messages = [
            {
                "role": "system",
                "content": "You are an expert at creating weighted syntheses that balance multiple perspectives.",
            },
            {"role": "user", "content": prompt},
        ]

        synthesis = await client.main_completion(messages, temperature=0.7)

        return synthesis
