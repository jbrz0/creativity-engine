"""Configuration management for the Creativity Engine."""

from functools import lru_cache
from typing import Optional

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=('settings_',)  # Allow 'model_' prefix fields
    )

    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_workers: int = Field(default=4, description="Number of API workers")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # OpenRouter Configuration
    openrouter_api_key: str = Field(..., description="OpenRouter API key")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", description="OpenRouter base URL"
    )

    # Model Configuration
    main_model: str = Field(
        default="openai/gpt-5.2", description="Main processing model for complex tasks"
    )
    fast_model: str = Field(
        default="openai/gpt-5-nano", description="Fast model for quick processing"
    )
    model_temperature: float = Field(default=0.7, description="Model temperature")
    model_max_tokens: int = Field(default=4096, description="Max tokens per generation")

    # Database Configuration
    postgres_host: str = Field(default="localhost", description="PostgreSQL host")
    postgres_port: int = Field(default=5432, description="PostgreSQL port")
    postgres_db: str = Field(default="creativity_engine", description="PostgreSQL database name")
    postgres_user: str = Field(default="creativity_user", description="PostgreSQL username")
    postgres_password: str = Field(..., description="PostgreSQL password")

    # Pinecone Configuration
    pinecone_api_key: str = Field(..., description="Pinecone API key")
    pinecone_environment: str = Field(..., description="Pinecone environment")
    pinecone_index_name: str = Field(
        default="creativity-engine", description="Pinecone index name"
    )

    # Redis Configuration
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_db: int = Field(default=0, description="Redis database")
    redis_password: Optional[str] = Field(default=None, description="Redis password")

    # RabbitMQ Configuration
    rabbitmq_host: str = Field(default="localhost", description="RabbitMQ host")
    rabbitmq_port: int = Field(default=5672, description="RabbitMQ port")
    rabbitmq_user: str = Field(default="creativity", description="RabbitMQ username")
    rabbitmq_password: str = Field(..., description="RabbitMQ password")
    rabbitmq_vhost: str = Field(default="/", description="RabbitMQ virtual host")

    # Processing Configuration
    max_concurrent_tasks: int = Field(default=10, description="Max concurrent processing tasks")
    task_timeout: int = Field(default=600, description="Task timeout in seconds")
    enable_simple_output: bool = Field(
        default=True, description="Enable simple/quick output option"
    )

    # Memory System Configuration
    memory_activation_threshold: float = Field(
        default=0.7, description="Memory activation threshold"
    )
    memory_decay_rate: float = Field(default=0.95, description="Memory decay rate")
    semantic_similarity_threshold: float = Field(
        default=0.75, description="Semantic similarity threshold"
    )

    # Critique Network Configuration
    critique_ensemble_threshold: float = Field(
        default=0.6, description="Critique ensemble threshold"
    )
    enable_iterative_refinement: bool = Field(
        default=True, description="Enable iterative refinement"
    )
    max_refinement_iterations: int = Field(
        default=3, description="Maximum refinement iterations"
    )

    # Feedback & Learning Configuration
    enable_rl_training: bool = Field(default=True, description="Enable RL training")
    training_batch_size: int = Field(default=32, description="Training batch size")
    learning_rate: float = Field(default=0.001, description="Learning rate")

    # Monitoring & Observability
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")
    enable_tracing: bool = Field(default=False, description="Enable distributed tracing")
    sentry_dsn: Optional[str] = Field(default=None, description="Sentry DSN for error tracking")

    @property
    def database_url(self) -> str:
        """Construct PostgreSQL database URL."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        """Construct Redis URL."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def rabbitmq_url(self) -> str:
        """Construct RabbitMQ URL."""
        return (
            f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}{self.rabbitmq_vhost}"
        )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
