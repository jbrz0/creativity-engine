"""Memory Manager - Handles memory storage, retrieval, and activation."""

from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from src.models.memory import Memory, MemoryType
from src.config import get_settings
from src.utils.pinecone_client import get_pinecone_client

logger = structlog.get_logger(__name__)
settings = get_settings()


class MemoryManager:
    """Manages memory storage, activation, and decay."""

    def __init__(self, db_session: AsyncSession):
        """Initialize memory manager.

        Args:
            db_session: Database session
        """
        self.db = db_session
        self.pinecone_client = None

    async def _ensure_pinecone(self):
        """Ensure Pinecone client is initialized."""
        if self.pinecone_client is None:
            self.pinecone_client = await get_pinecone_client()
        return self.pinecone_client

    async def create_memory(
        self,
        content: str,
        memory_type: MemoryType,
        embedding: List[float],
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
    ) -> Memory:
        """Create a new memory.

        Args:
            content: Memory content
            memory_type: Type of memory
            embedding: Vector embedding
            title: Optional title
            description: Optional description
            tags: Optional tags
            metadata: Optional metadata
            importance: Base importance (0.0 to 1.0)

        Returns:
            Created memory
        """
        logger.info("Creating new memory", memory_type=memory_type.value, importance=importance)

        # Generate embedding ID
        pinecone = await self._ensure_pinecone()
        embedding_id = pinecone.generate_id(content, prefix=f"{memory_type.value}_")

        # Store in Pinecone
        vector_data = {
            "id": embedding_id,
            "values": embedding,
            "metadata": {
                "content": content[:500],  # Store first 500 chars in Pinecone
                "memory_type": memory_type.value,
                "title": title or "",
                "tags": tags or [],
                **(metadata or {}),
            },
        }

        await pinecone.upsert_vectors(
            [vector_data],
            namespace=memory_type.value,
        )

        # Create database record
        memory = Memory(
            memory_type=memory_type,
            content=content,
            embedding_id=embedding_id,
            title=title,
            description=description,
            tags=tags,
            metadata=metadata,
            base_importance=importance,
            activation_level=0.0,
        )

        self.db.add(memory)
        await self.db.commit()
        await self.db.refresh(memory)

        logger.info("Memory created", memory_id=str(memory.id), embedding_id=embedding_id)

        return memory

    async def activate_memory(
        self,
        memory_id: UUID,
        activation_boost: float = 0.3,
    ) -> None:
        """Activate a memory, increasing its activation level.

        Args:
            memory_id: Memory ID
            activation_boost: Amount to boost activation
        """
        result = await self.db.execute(select(Memory).where(Memory.id == memory_id))
        memory = result.scalar_one_or_none()

        if not memory:
            logger.warning("Memory not found for activation", memory_id=str(memory_id))
            return

        # Increase activation level (capped at 1.0)
        new_activation = min(1.0, memory.activation_level + activation_boost)

        await self.db.execute(
            update(Memory)
            .where(Memory.id == memory_id)
            .values(
                activation_level=new_activation,
                access_count=memory.access_count + 1,
                last_accessed=datetime.utcnow(),
            )
        )

        await self.db.commit()

        logger.debug(
            "Memory activated",
            memory_id=str(memory_id),
            old_activation=memory.activation_level,
            new_activation=new_activation,
        )

    async def decay_memories(self, decay_rate: Optional[float] = None) -> int:
        """Apply decay to all memories.

        Args:
            decay_rate: Decay rate (defaults to settings)

        Returns:
            Number of memories decayed
        """
        decay = decay_rate or settings.memory_decay_rate

        # Get all memories with activation > 0
        result = await self.db.execute(select(Memory).where(Memory.activation_level > 0))
        memories = result.scalars().all()

        count = 0
        for memory in memories:
            new_activation = memory.activation_level * decay
            if new_activation < 0.01:
                new_activation = 0.0

            await self.db.execute(
                update(Memory)
                .where(Memory.id == memory.id)
                .values(activation_level=new_activation)
            )
            count += 1

        await self.db.commit()

        logger.debug("Applied memory decay", count=count, decay_rate=decay)

        return count

    async def get_active_memories(
        self,
        threshold: Optional[float] = None,
        limit: int = 20,
    ) -> List[Memory]:
        """Get currently active memories above threshold.

        Args:
            threshold: Activation threshold (defaults to settings)
            limit: Maximum number to return

        Returns:
            List of active memories
        """
        thresh = threshold or settings.memory_activation_threshold

        result = await self.db.execute(
            select(Memory)
            .where(Memory.activation_level >= thresh)
            .order_by(Memory.activation_level.desc())
            .limit(limit)
        )

        memories = result.scalars().all()

        logger.debug("Retrieved active memories", count=len(memories), threshold=thresh)

        return list(memories)

    async def get_memory_by_id(self, memory_id: UUID) -> Optional[Memory]:
        """Get memory by ID.

        Args:
            memory_id: Memory ID

        Returns:
            Memory or None
        """
        result = await self.db.execute(select(Memory).where(Memory.id == memory_id))
        return result.scalar_one_or_none()

    async def delete_memory(self, memory_id: UUID) -> bool:
        """Delete a memory.

        Args:
            memory_id: Memory ID

        Returns:
            True if deleted, False if not found
        """
        memory = await self.get_memory_by_id(memory_id)
        if not memory:
            return False

        # Delete from Pinecone
        if memory.embedding_id:
            pinecone = await self._ensure_pinecone()
            await pinecone.delete_vectors(
                [memory.embedding_id],
                namespace=memory.memory_type.value,
            )

        # Delete from database
        await self.db.delete(memory)
        await self.db.commit()

        logger.info("Memory deleted", memory_id=str(memory_id))

        return True
