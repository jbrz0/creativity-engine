"""Memory models for different memory types."""

from datetime import datetime
from enum import Enum as PyEnum
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, Text, Float, Integer, JSON, Enum
from sqlalchemy.dialects.postgresql import UUID

from src.database.session import Base


class MemoryType(str, PyEnum):
    """Memory type enumeration."""

    MONOGRAPH = "monograph"  # Written/text-based memories
    AUDIO = "audio"  # Audio/sound references
    PROTOTYPE = "prototype"  # Prototype/example memories
    SEMANTIC = "semantic"  # Semantic concepts
    EPISODIC = "episodic"  # Episodic experiences
    WORKING = "working"  # Working memory (temporary)


class Memory(Base):
    """Base memory model."""

    __tablename__ = "memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    memory_type = Column(Enum(MemoryType), nullable=False, index=True)

    # Core content
    content = Column(Text, nullable=False)
    embedding_id = Column(String(255), nullable=True, index=True)  # Pinecone vector ID

    # Metadata
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)  # List of tags
    extra_metadata = Column(JSON, nullable=True)  # Additional metadata

    # Activation and importance
    activation_level = Column(Float, default=0.0)  # Current activation (0.0 to 1.0)
    base_importance = Column(Float, default=0.5)  # Base importance (0.0 to 1.0)
    access_count = Column(Integer, default=0)  # How many times accessed
    last_accessed = Column(DateTime, nullable=True)

    # Associations
    related_memory_ids = Column(JSON, nullable=True)  # IDs of related memories
    analogies = Column(JSON, nullable=True)  # Stored analogies

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Memory(id={self.id}, type={self.memory_type}, title={self.title})>"


class MonographMemory(Base):
    """Specialized memory for written/textual content."""

    __tablename__ = "monograph_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    memory_id = Column(UUID(as_uuid=True), nullable=False, index=True)  # Reference to base Memory

    # Monograph-specific fields
    author = Column(String(255), nullable=True)
    source = Column(String(500), nullable=True)
    genre = Column(String(100), nullable=True)
    themes = Column(JSON, nullable=True)

    word_count = Column(Integer, nullable=True)
    reading_level = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<MonographMemory(id={self.id}, author={self.author})>"


class AudioMemory(Base):
    """Specialized memory for audio references."""

    __tablename__ = "audio_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    memory_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Audio-specific fields
    audio_type = Column(String(100), nullable=True)  # music, speech, sound, etc.
    duration_seconds = Column(Float, nullable=True)
    tempo = Column(String(50), nullable=True)
    mood = Column(String(100), nullable=True)
    instruments = Column(JSON, nullable=True)

    audio_url = Column(String(1000), nullable=True)
    transcript = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<AudioMemory(id={self.id}, type={self.audio_type})>"


class PrototypeMemory(Base):
    """Specialized memory for prototypes and examples."""

    __tablename__ = "prototype_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    memory_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Prototype-specific fields
    prototype_type = Column(String(100), nullable=True)
    category = Column(String(100), nullable=True)
    quality_score = Column(Float, nullable=True)  # How good of an example

    features = Column(JSON, nullable=True)  # Key features
    variations = Column(JSON, nullable=True)  # Known variations

    image_url = Column(String(1000), nullable=True)
    reference_url = Column(String(1000), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<PrototypeMemory(id={self.id}, type={self.prototype_type})>"
