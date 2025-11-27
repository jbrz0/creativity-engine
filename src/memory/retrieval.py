"""Memory Retrieval - Semantic search and memory recall."""

from typing import List, Dict, Any, Optional
from uuid import UUID
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.memory import Memory, MemoryType
from src.config import get_settings
from src.utils.pinecone_client import get_pinecone_client
from src.utils.openrouter import get_openrouter_client

logger = structlog.get_logger(__name__)
settings = get_settings()


class MemoryRetrieval:
    """Handles semantic memory retrieval and search."""

    def __init__(self, db_session: AsyncSession):
        """Initialize memory retrieval.

        Args:
            db_session: Database session
        """
        self.db = db_session
        self.pinecone_client = None
        self.openrouter_client = None

    async def _ensure_clients(self):
        """Ensure clients are initialized."""
        if self.pinecone_client is None:
            self.pinecone_client = await get_pinecone_client()
        if self.openrouter_client is None:
            self.openrouter_client = await get_openrouter_client()
        return self.pinecone_client, self.openrouter_client

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        # Note: OpenRouter doesn't have a dedicated embeddings endpoint
        # In production, you'd want to use a dedicated embedding model
        # For now, we'll create a placeholder
        # TODO: Integrate proper embedding model (e.g., OpenAI embeddings via OpenRouter)

        import hashlib
        import numpy as np

        # Temporary: Generate deterministic fake embedding from hash
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()

        # Convert to 1536-dim vector (standard embedding size)
        np.random.seed(int.from_bytes(hash_bytes[:4], byteorder="big"))
        embedding = np.random.randn(1536).tolist()

        # Normalize
        norm = np.linalg.norm(embedding)
        embedding = (np.array(embedding) / norm).tolist()

        return embedding

    async def search_memories(
        self,
        query: str,
        memory_types: Optional[List[MemoryType]] = None,
        top_k: int = 10,
        min_score: float = 0.7,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for relevant memories.

        Args:
            query: Search query
            memory_types: Optional filter by memory types
            top_k: Number of results
            min_score: Minimum similarity score
            filter_dict: Optional metadata filter

        Returns:
            List of relevant memories with scores
        """
        logger.info(
            "Searching memories",
            query_length=len(query),
            memory_types=memory_types,
            top_k=top_k,
        )

        pinecone, _ = await self._ensure_clients()

        # Generate query embedding
        query_embedding = await self._generate_embedding(query)

        # Search in each memory type namespace
        all_results = []

        types_to_search = memory_types or list(MemoryType)

        for memory_type in types_to_search:
            try:
                results = await pinecone.query_vectors(
                    vector=query_embedding,
                    top_k=top_k,
                    namespace=memory_type.value,
                    filter_dict=filter_dict,
                    include_metadata=True,
                )

                # Filter by score and add memory type
                for result in results:
                    if result["score"] >= min_score:
                        result["memory_type"] = memory_type.value
                        all_results.append(result)

            except Exception as e:
                logger.error(
                    "Error searching memory type",
                    memory_type=memory_type.value,
                    error=str(e),
                )

        # Sort by score and limit
        all_results.sort(key=lambda x: x["score"], reverse=True)
        all_results = all_results[:top_k]

        # Enrich with database data
        enriched_results = []
        for result in all_results:
            memory_id = result.get("metadata", {}).get("memory_id")
            if memory_id:
                db_result = await self.db.execute(
                    select(Memory).where(Memory.embedding_id == result["id"])
                )
                memory = db_result.scalar_one_or_none()

                if memory:
                    enriched_results.append(
                        {
                            "memory": memory,
                            "score": result["score"],
                            "metadata": result.get("metadata", {}),
                        }
                    )

        logger.info("Memory search completed", results_count=len(enriched_results))

        return enriched_results

    async def retrieve_similar_memories(
        self,
        memory_id: UUID,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Retrieve memories similar to a given memory.

        Args:
            memory_id: Source memory ID
            top_k: Number of similar memories to retrieve

        Returns:
            List of similar memories
        """
        # Get source memory
        result = await self.db.execute(select(Memory).where(Memory.id == memory_id))
        memory = result.scalar_one_or_none()

        if not memory:
            logger.warning("Memory not found for similarity search", memory_id=str(memory_id))
            return []

        # Search using memory content
        return await self.search_memories(
            query=memory.content,
            memory_types=[memory.memory_type],
            top_k=top_k + 1,  # +1 to exclude self
        )

    async def retrieve_context_memories(
        self,
        input_text: str,
        context_data: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
    ) -> List[Memory]:
        """Retrieve contextually relevant memories for processing.

        Args:
            input_text: Input text to find relevant memories for
            context_data: Additional context data
            top_k: Number of memories to retrieve

        Returns:
            List of relevant memories
        """
        logger.info("Retrieving context memories", input_length=len(input_text), top_k=top_k)

        # Search memories
        results = await self.search_memories(
            query=input_text,
            top_k=top_k,
            min_score=settings.semantic_similarity_threshold,
        )

        # Extract memory objects
        memories = [r["memory"] for r in results if "memory" in r]

        logger.info("Retrieved context memories", count=len(memories))

        return memories
