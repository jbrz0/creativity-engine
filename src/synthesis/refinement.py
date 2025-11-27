"""Iterative Refinement - Self-improving output refinement loop."""

from typing import Dict, Any, Optional, List
import structlog

from src.synthesis.critique_ensemble import CritiqueEnsemble
from src.utils.openrouter import get_openrouter_client
from src.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class IterativeRefinement:
    """Implements self-iterative refinement loops for output improvement."""

    def __init__(self):
        """Initialize iterative refinement."""
        self.critique_ensemble = CritiqueEnsemble()
        self.client = None

    async def _ensure_client(self):
        """Ensure OpenRouter client is initialized."""
        if self.client is None:
            self.client = await get_openrouter_client()
        return self.client

    async def refine(
        self,
        content: str,
        original_input: str,
        context: Optional[Dict[str, Any]] = None,
        max_iterations: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Iteratively refine content until quality threshold is met.

        Args:
            content: Initial content to refine
            original_input: Original user input
            context: Optional context
            max_iterations: Maximum refinement iterations (defaults to settings)

        Returns:
            Refinement result with final content and history
        """
        max_iter = max_iterations or settings.max_refinement_iterations

        if not settings.enable_iterative_refinement:
            logger.info("Iterative refinement disabled, returning original content")
            return {
                "final_content": content,
                "iterations": 0,
                "refinement_history": [],
                "final_score": None,
            }

        logger.info("Starting iterative refinement", max_iterations=max_iter)

        current_content = content
        refinement_history = []

        for iteration in range(max_iter):
            logger.info("Refinement iteration", iteration=iteration + 1, max=max_iter)

            # Evaluate current content
            critique_context = {
                **(context or {}),
                "original_input": original_input,
            }

            critique = await self.critique_ensemble.evaluate(current_content, critique_context)

            ensemble_score = critique["ensemble_score"]
            needs_refinement = critique["needs_refinement"]

            logger.info(
                "Critique completed",
                iteration=iteration + 1,
                score=ensemble_score,
                needs_refinement=needs_refinement,
            )

            # Store iteration result
            refinement_history.append(
                {
                    "iteration": iteration + 1,
                    "content": current_content,
                    "ensemble_score": ensemble_score,
                    "critique": critique,
                }
            )

            # Check if refinement is needed
            if not needs_refinement:
                logger.info(
                    "Refinement complete, quality threshold met",
                    iteration=iteration + 1,
                    final_score=ensemble_score,
                )
                break

            # Perform refinement
            refined_content = await self._apply_refinement(
                current_content=current_content,
                original_input=original_input,
                critique=critique,
                iteration=iteration + 1,
            )

            current_content = refined_content

        # Final evaluation
        final_critique = await self.critique_ensemble.evaluate(current_content, critique_context)

        result = {
            "final_content": current_content,
            "iterations": len(refinement_history),
            "refinement_history": refinement_history,
            "final_score": final_critique["ensemble_score"],
            "final_critique": final_critique,
        }

        logger.info(
            "Iterative refinement complete",
            total_iterations=len(refinement_history),
            final_score=final_critique["ensemble_score"],
        )

        return result

    async def _apply_refinement(
        self,
        current_content: str,
        original_input: str,
        critique: Dict[str, Any],
        iteration: int,
    ) -> str:
        """Apply refinement based on critique.

        Args:
            current_content: Current content version
            original_input: Original input
            critique: Critique results
            iteration: Current iteration number

        Returns:
            Refined content
        """
        client = await self._ensure_client()

        # Build refinement prompt
        suggestions_text = "\n".join(
            [f"- {s}" for s in critique.get("suggestions", [])]
        )

        scores_text = "\n".join(
            [f"- {k}: {v:.2f}" for k, v in critique.get("scores", {}).items()]
        )

        prompt = f"""Refine this creative output based on the critique:

Original Input: {original_input}

Current Output (Iteration {iteration}):
{current_content}

Critique Scores:
{scores_text}

Suggestions for Improvement:
{suggestions_text}

Create a refined version that:
1. Addresses the critique suggestions
2. Improves weak areas
3. Maintains or enhances strengths
4. Preserves the core creative vision
5. Produces a more polished result

Provide the refined output:"""

        messages = [
            {
                "role": "system",
                "content": "You are an expert at refining creative outputs based on structured critique.",
            },
            {"role": "user", "content": prompt},
        ]

        refined = await client.main_completion(messages, temperature=0.6)

        logger.debug(
            "Refinement applied",
            iteration=iteration,
            old_length=len(current_content),
            new_length=len(refined),
        )

        return refined

    async def refine_with_targets(
        self,
        content: str,
        original_input: str,
        target_scores: Dict[str, float],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Refine content to meet specific target scores.

        Args:
            content: Content to refine
            original_input: Original input
            target_scores: Target scores for each dimension
            context: Optional context

        Returns:
            Refinement result
        """
        logger.info("Starting target-based refinement", targets=target_scores)

        max_iter = settings.max_refinement_iterations
        current_content = content
        refinement_history = []

        for iteration in range(max_iter):
            critique = await self.critique_ensemble.evaluate(
                current_content,
                {**(context or {}), "original_input": original_input},
            )

            scores = critique["scores"]

            # Check if all targets are met
            targets_met = all(
                scores.get(dim, 0.0) >= target for dim, target in target_scores.items()
            )

            refinement_history.append(
                {
                    "iteration": iteration + 1,
                    "content": current_content,
                    "scores": scores,
                    "targets_met": targets_met,
                }
            )

            if targets_met:
                logger.info("All target scores met", iteration=iteration + 1)
                break

            # Identify gaps
            gaps = {
                dim: target - scores.get(dim, 0.0)
                for dim, target in target_scores.items()
                if scores.get(dim, 0.0) < target
            }

            # Refine focusing on gaps
            current_content = await self._apply_targeted_refinement(
                current_content, original_input, gaps, iteration + 1
            )

        return {
            "final_content": current_content,
            "iterations": len(refinement_history),
            "refinement_history": refinement_history,
            "targets_met": targets_met,
        }

    async def _apply_targeted_refinement(
        self,
        content: str,
        original_input: str,
        gaps: Dict[str, float],
        iteration: int,
    ) -> str:
        """Apply refinement targeting specific score gaps.

        Args:
            content: Current content
            original_input: Original input
            gaps: Score gaps to address
            iteration: Iteration number

        Returns:
            Refined content
        """
        client = await self._ensure_client()

        gaps_text = "\n".join([f"- Improve {dim} by {gap:.2f}" for dim, gap in gaps.items()])

        prompt = f"""Refine this output to improve specific dimensions:

Original Input: {original_input}

Current Output:
{content}

Focus on improving:
{gaps_text}

Create a refined version that specifically addresses these gaps while maintaining overall quality.

Provide the refined output:"""

        messages = [{"role": "user", "content": prompt}]

        refined = await client.main_completion(messages, temperature=0.6)

        return refined
