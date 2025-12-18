import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, String, Integer, DateTime, Boolean, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from src.database.session import Base


class PlanType(str, enum.Enum):
    FREE = "free"
    PREMIUM = "premium"


class TransactionType(str, enum.Enum):
    USAGE = "usage"  # consuming a credit
    PURCHASE = "purchase"  # buying add-on
    SUBSCRIPTION = "subscription"  # monthly renewal
    RESET = "reset"  # monthly reset


class User(Base):
    """User model extending Supabase Auth."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    # This ID should match the Supabase Auth User ID
    supabase_uid = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, index=True, nullable=False)
    
    # Credit System
    monthly_credits = Column(Integer, default=50)  # Resets monthly
    addon_credits = Column(Integer, default=0)    # Purchased, don't expire
    
    # Subscription
    plan_type = Column(Enum(PlanType), default=PlanType.FREE)
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")

    @property
    def total_credits(self) -> int:
        return self.monthly_credits + self.addon_credits


class APIKey(Base):
    """API Key model for external access."""

    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    key_hash = Column(String, nullable=False, index=True) # Store hashed key
    prefix = Column(String, nullable=False) # Store first few chars for display
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="api_keys")


class Transaction(Base):
    """Transaction history for credits."""

    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    amount = Column(Integer, nullable=False) # Negative for usage, positive for purchase
    type = Column(Enum(TransactionType), nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata_json = Column(String, nullable=True) # Store extras like stripe session id

    user = relationship("User", back_populates="transactions")
