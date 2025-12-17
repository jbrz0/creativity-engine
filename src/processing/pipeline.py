"""Main Processing Pipeline - Orchestrates the complete creativity engine workflow."""

from typing import Dict, Any, Optional
from uuid import UUID
import asyncio
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from src.models.request import CreativityRequest, ProcessingStatusEnum, OutputType, ProcessingStatus
from src.memory.retrieval import MemoryRetrieval
from src.memory.manager import MemoryManager
from src.agents.moment.novelty import NoveltyAgent
from src.agents.moment.mini_cae import MiniCAEAgent
from src.agents.moment.idea_cae import IdeaCAEAgent
from src.synthesis.orchestra import SynthesisOrchestra
from src.synthesis.critique_ensemble import CritiqueEnsemble
from src.synthesis.refinement import IterativeRefinement
from src.synthesis.refinement import IterativeRefinement
from src.api.status import broadcast_status_update
from src.processing.creativity.preprocess import preprocess
from src.processing.creativity.graph_stub import GraphClient
from src.processing.creativity.graph_enrich import graph_enrich
from src.processing.creativity.controls import map_sliders_to_params, slider_to_band
from src.processing.creativity.prompt_augment import AugmentConfig, build_messages, _cross_domain_seeds, _fmt_insights

logger = structlog.get_logger(__name__)


class CreativityPipeline:
    """Main pipeline for processing creativity requests."""

    def __init__(self, db_session: AsyncSession):
        """Initialize creativity pipeline.

        Args:
            db_session: Database session
        """
        self.db = db_session
        self.memory_retrieval = MemoryRetrieval(db_session)
        self.memory_manager = MemoryManager(db_session)

        # Initialize agents
        self.mini_cae_agent = MiniCAEAgent()
        self.idea_cae_agent = IdeaCAEAgent()

        # Initialize synthesis components
        self.synthesis_orchestra = SynthesisOrchestra()
        self.critique_ensemble = CritiqueEnsemble()
        self.critique_ensemble = CritiqueEnsemble()
        self.iterative_refinement = IterativeRefinement()
        
        # Initialize graph client for v1 support
        self.graph_client = GraphClient()

    async def process_request(self, request_id: UUID) -> Dict[str, Any]:
        """Process a complete creativity request through the pipeline.

        Args:
            request_id: Request ID to process

        Returns:
            Processing result
        """
        logger.info("Starting creativity pipeline", request_id=str(request_id))

        # Get request
        result = await self.db.execute(
            select(CreativityRequest).where(CreativityRequest.id == request_id)
        )
        request = result.scalar_one_or_none()

        if not request:
            raise ValueError(f"Request {request_id} not found")

        try:
            # Update status to processing
            await self._update_status(request, ProcessingStatusEnum.PREPARING, 5.0, "Preparing request")

            # Check if simple output is requested
            if request.output_type == OutputType.SIMPLE:
                return await self._process_simple(request)

            # Full processing pipeline
            return await self._process_full(request)

        except Exception as e:
            logger.error("Pipeline error", request_id=str(request_id), error=str(e), exc_info=e)
            await self._update_status(
                request,
                ProcessingStatusEnum.FAILED,
                0.0,
                f"Processing failed: {str(e)}",
            )
            raise

    async def _process_simple(self, request: CreativityRequest) -> Dict[str, Any]:
        """Process request with simple/fast output.

        Args:
            request: Creativity request

        Returns:
            Simple processing result
        """
        logger.info("Processing simple output", request_id=str(request.id))

        await self._update_status(
            request,
            ProcessingStatusEnum.PROCESSING_MOMENT,
            50.0,
            "Generating quick creative output",
        )

        # Use only Mini-CAE for fast processing
        input_data = {"input_text": request.input_text}
        response = await self.mini_cae_agent.process(input_data)

        # Update request with output
        request.output_text = response.content
        request.output_data = {
            "type": "simple",
            "agent": response.agent_name,
            "confidence": response.confidence,
            "metadata": response.metadata,
        }
        request.status = ProcessingStatusEnum.COMPLETED
        request.progress_percentage = 100.0

        await self.db.commit()

        logger.info("Simple output completed", request_id=str(request.id))

        return {
            "request_id": request.id,
            "output_text": response.content,
            "output_data": request.output_data,
        }

    async def _process_full(self, request: CreativityRequest) -> Dict[str, Any]:
        """Process request with full pipeline.

        Args:
            request: Creativity request

        Returns:
            Full processing result
        """
        logger.info("Processing full pipeline", request_id=str(request.id))

        # 1. Preparation: Retrieve relevant memories
        await self._update_status(
            request,
            ProcessingStatusEnum.PREPARING,
            10.0,
            "Retrieving relevant memories",
        )

        memories = await self.memory_retrieval.retrieve_context_memories(
            request.input_text,
            context_data=request.input_metadata,
            top_k=10,
        )

        logger.info("Retrieved memories", count=len(memories))

        # Prepare context with creative controls if present
        metadata = request.input_metadata or {}
        controls = metadata.get("controls") or metadata 

        context = {
            "memories": [{"content": m.content, "type": m.memory_type.value} for m in memories],
            "user_preferences": metadata.get("preferences", {}),
            "creative_config": None
        }
        
        # specific creative controls logic
        if "randomness" in controls or "speculation" in controls:
             logger.info("Creative controls detected, preparing rich context")
             
             # 1. Preprocess
             pre = preprocess(request.input_text)
             
             # 2. Graph Enrich
             ge = await graph_enrich(self.graph_client, pre)
             
             # 3. Map controls to parameters
             randomness = int(controls.get("randomness", 50))
             speculation = int(controls.get("speculation", 50))
             ideas = int(controls.get("ideas", 50))
             
             maps = map_sliders_to_params(randomness, speculation, ideas)
             sampling = maps["sampling"]
             hints = maps["kernel"]
             
             # 4. Generate Seeds/Insights
             seeds = _cross_domain_seeds(pre, hints["serendipity_cross_domain_seeds"])
             insights = _fmt_insights(ge, max_seeds=3)
             
             # Add to context
             context["creative_config"] = {
                 "enabled": True,
                 "sampling": sampling,
                 "kernel": hints,
                 "seeds": seeds,
                 "insights": insights,
                 "graph_data": ge.fallback,
                 "sliders": {
                     "randomness": randomness, 
                     "speculation": speculation, 
                     "ideas": ideas
                 }
             }

        # 2. Moment Layer: Run all agents in parallel
        await self._update_status(
            request,
            ProcessingStatusEnum.PROCESSING_MOMENT,
            30.0,
            "Processing with moment agents",
        )

        input_data = {"input_text": request.input_text}

        agent_results = await asyncio.gather(
            self.novelty_agent.process(input_data, context),
            self.specialized_agent.process(input_data, context),
            self.mini_cae_agent.process(input_data, context),
            self.idea_cae_agent.process(input_data, context),
            return_exceptions=True,
        )

        # Filter out exceptions
        valid_responses = [r for r in agent_results if not isinstance(r, Exception)]

        logger.info("Moment agents completed", valid_count=len(valid_responses))

        # 3. Synthesis: Merge agent outputs
        await self._update_status(
            request,
            ProcessingStatusEnum.PROCESSING_SYNTHESIS,
            50.0,
            "Synthesizing agent outputs",
        )

        synthesized = await self.synthesis_orchestra.merge_outputs(
            valid_responses,
            synthesis_strategy="comprehensive",
        )

        logger.info("Synthesis completed", output_length=len(synthesized))

        # 4. Critique: Evaluate synthesis
        await self._update_status(
            request,
            ProcessingStatusEnum.PROCESSING_CRITIQUE,
            70.0,
            "Evaluating output quality",
        )

        critique_context = {
            "original_input": request.input_text,
            **context,
        }

        critique = await self.critique_ensemble.evaluate(synthesized, critique_context)

        logger.info("Critique completed", ensemble_score=critique["ensemble_score"])

        # 5. Refinement: Iteratively improve if needed
        final_output = synthesized
        refinement_data = None

        if critique["needs_refinement"]:
            await self._update_status(
                request,
                ProcessingStatusEnum.REFINING,
                85.0,
                "Refining output",
            )

            refinement_result = await self.iterative_refinement.refine(
                content=synthesized,
                original_input=request.input_text,
                context=critique_context,
            )

            final_output = refinement_result["final_content"]
            refinement_data = {
                "iterations": refinement_result["iterations"],
                "final_score": refinement_result["final_score"],
            }

            logger.info(
                "Refinement completed",
                iterations=refinement_result["iterations"],
                final_score=refinement_result.get("final_score"),
            )

        # 6. Finalize
        await self._update_status(
            request,
            ProcessingStatusEnum.COMPLETED,
            100.0,
            "Processing complete",
        )

        # Store results
        request.output_text = final_output
        request.output_data = {
            "type": "full",
            "agent_responses": [
                {
                    "agent": r.agent_name,
                    "confidence": r.confidence,
                    "content_preview": r.content[:200],
                }
                for r in valid_responses
            ],
            "synthesis_strategy": "comprehensive",
            "critique_scores": critique["scores"],
            "ensemble_score": critique["ensemble_score"],
            "refinement": refinement_data,
        }
        request.status = ProcessingStatusEnum.COMPLETED
        request.progress_percentage = 100.0

        await self.db.commit()

        logger.info("Full pipeline completed", request_id=str(request.id))

        return {
            "request_id": request.id,
            "output_text": final_output,
            "output_data": request.output_data,
        }

    async def _update_status(
        self,
        request: CreativityRequest,
        status: ProcessingStatusEnum,
        progress: float,
        stage: str,
    ) -> None:
        """Update request status and broadcast to WebSocket.

        Args:
            request: Request to update
            status: New status
            progress: Progress percentage
            stage: Current stage description
        """
        request.status = status
        request.progress_percentage = progress
        request.current_stage = stage

        await self.db.commit()

        # Broadcast status update
        await broadcast_status_update(
            request.id,
            {
                "status": status.value,
                "progress_percentage": progress,
                "current_stage": stage,
            },
        )

        logger.debug(
            "Status updated",
            request_id=str(request.id),
            status=status.value,
            progress=progress,
        )


