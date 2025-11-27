"""Base agent class for all AI agents in the creativity engine."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import structlog

from src.utils.openrouter import OpenRouterClient, get_openrouter_client

logger = structlog.get_logger(__name__)


@dataclass
class AgentResponse:
    """Response from an agent."""

    content: str
    confidence: float  # 0.0 to 1.0
    metadata: Dict[str, Any]
    agent_name: str
    reasoning: Optional[str] = None


class BaseAgent(ABC):
    """Base class for all AI agents."""

    def __init__(
        self,
        name: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ):
        """Initialize agent.

        Args:
            name: Agent name
            model: Model to use (None = use main model)
            temperature: Sampling temperature
            system_prompt: System prompt for the agent
        """
        self.name = name
        self.model = model
        self.temperature = temperature
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.client: Optional[OpenRouterClient] = None

        logger.info(
            "Initialized agent",
            agent_name=self.name,
            model=self.model or "default",
            temperature=self.temperature,
        )

    async def _ensure_client(self) -> OpenRouterClient:
        """Ensure OpenRouter client is initialized."""
        if self.client is None:
            self.client = await get_openrouter_client()
        return self.client

    @abstractmethod
    def _default_system_prompt(self) -> str:
        """Get default system prompt for this agent.

        Returns:
            System prompt string
        """
        pass

    @abstractmethod
    async def process(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """Process input and generate response.

        Args:
            input_data: Input data for processing
            context: Optional context information

        Returns:
            Agent response
        """
        pass

    async def _generate_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
    ) -> str:
        """Generate a completion using the LLM.

        Args:
            messages: List of message dictionaries
            temperature: Override temperature

        Returns:
            Generated text
        """
        client = await self._ensure_client()

        # Add system prompt if not already present
        if not any(msg.get("role") == "system" for msg in messages):
            messages = [{"role": "system", "content": self.system_prompt}] + messages

        temp = temperature if temperature is not None else self.temperature

        logger.debug(
            "Generating completion",
            agent=self.name,
            message_count=len(messages),
            temperature=temp,
        )

        if self.model:
            response = await client.get_completion_text(
                messages, model=self.model, temperature=temp
            )
        else:
            response = await client.main_completion(messages, temperature=temp)

        return response

    async def _fast_completion(
        self,
        messages: List[Dict[str, str]],
    ) -> str:
        """Generate a fast completion using the fast model.

        Args:
            messages: List of message dictionaries

        Returns:
            Generated text
        """
        client = await self._ensure_client()

        if not any(msg.get("role") == "system" for msg in messages):
            messages = [{"role": "system", "content": self.system_prompt}] + messages

        return await client.fast_completion(messages)

    def _extract_confidence(self, text: str) -> float:
        """Extract confidence score from agent output.

        Looks for patterns like "Confidence: 0.85" or "[Confidence: 85%]"

        Args:
            text: Text to search

        Returns:
            Confidence score (0.0 to 1.0), defaults to 0.7
        """
        import re

        # Look for "Confidence: X.XX" or "Confidence: XX%"
        patterns = [
            r"Confidence:\s*([0-9.]+)",
            r"Confidence:\s*([0-9]+)%",
            r"\[Confidence:\s*([0-9.]+)\]",
            r"\[Confidence:\s*([0-9]+)%\]",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                # Convert percentage to decimal if needed
                if value > 1.0:
                    value = value / 100.0
                return max(0.0, min(1.0, value))

        # Default confidence
        return 0.7
