"""OpenRouter client for model abstraction."""

from typing import Any, Dict, List, Optional, Union
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class OpenRouterClient:
    """Client for interacting with OpenRouter API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 120.0,
    ):
        """Initialize OpenRouter client.

        Args:
            api_key: OpenRouter API key (defaults to settings)
            base_url: OpenRouter base URL (defaults to settings)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or settings.openrouter_api_key
        self.base_url = base_url or settings.openrouter_base_url
        self.timeout = timeout

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://creativity-engine.local",
                "X-Title": "Creativity Engine",
            },
            timeout=timeout,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Create a chat completion.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model: Model to use (defaults to main model from settings)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters to pass to the API

        Returns:
            API response dictionary

        Raises:
            httpx.HTTPError: If the request fails
        """
        model = model or settings.main_model
        temperature = temperature if temperature is not None else settings.model_temperature
        max_tokens = max_tokens or settings.model_max_tokens

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        logger.debug(
            "Sending chat completion request",
            model=model,
            message_count=len(messages),
            temperature=temperature,
        )

        response = await self.client.post("/chat/completions", json=payload)
        response.raise_for_status()

        result = response.json()
        logger.debug(
            "Received chat completion response",
            model=model,
            finish_reason=result.get("choices", [{}])[0].get("finish_reason"),
        )

        return result

    async def get_completion_text(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Get just the text content from a chat completion.

        Args:
            messages: List of message dictionaries
            model: Model to use
            **kwargs: Additional parameters

        Returns:
            The text content of the completion
        """
        response = await self.chat_completion(messages, model=model, **kwargs)
        return response["choices"][0]["message"]["content"]

    async def fast_completion(
        self,
        messages: List[Dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """Get a completion using the fast model.

        Args:
            messages: List of message dictionaries
            **kwargs: Additional parameters

        Returns:
            The text content of the completion
        """
        return await self.get_completion_text(
            messages,
            model=settings.fast_model,
            temperature=0.3,  # Lower temperature for fast, focused responses
            **kwargs,
        )

    async def main_completion(
        self,
        messages: List[Dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """Get a completion using the main model.

        Args:
            messages: List of message dictionaries
            **kwargs: Additional parameters

        Returns:
            The text content of the completion
        """
        return await self.get_completion_text(
            messages,
            model=settings.main_model,
            **kwargs,
        )

    async def streaming_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        **kwargs: Any,
    ):
        """Create a streaming chat completion.

        Args:
            messages: List of message dictionaries
            model: Model to use
            **kwargs: Additional parameters

        Yields:
            Chunks of the completion as they arrive
        """
        model = model or settings.main_model

        payload = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", settings.model_temperature),
            "max_tokens": kwargs.get("max_tokens", settings.model_max_tokens),
            "stream": True,
            **{k: v for k, v in kwargs.items() if k not in ["temperature", "max_tokens"]},
        }

        logger.debug("Starting streaming completion", model=model)

        async with self.client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    import json

                    try:
                        chunk = json.loads(data)
                        yield chunk
                    except json.JSONDecodeError:
                        continue


# Global client instance
_client: Optional[OpenRouterClient] = None


async def get_openrouter_client() -> OpenRouterClient:
    """Get the global OpenRouter client instance."""
    global _client
    if _client is None:
        _client = OpenRouterClient()
    return _client


async def close_openrouter_client() -> None:
    """Close the global OpenRouter client."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None
