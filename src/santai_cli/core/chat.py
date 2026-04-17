"""Shared chat engine for Santai CLI.

Provides a provider-agnostic chat interface with streaming support
for both Anthropic and OpenAI models. Used by the CLI, TUI, and
Web interfaces.
"""

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

import anthropic
import openai

from santai_cli.core.config import ProviderConfig


@dataclass
class ChatMessage:
    """A single message in a chat conversation."""

    role: str  # "system", "user", or "assistant"
    content: str


@dataclass
class ChatSession:
    """Manages conversation history for a chat session."""

    system_prompt: str | None = None
    messages: list[ChatMessage] = field(default_factory=list)

    def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation."""
        self.messages.append(ChatMessage(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant response to the conversation."""
        self.messages.append(ChatMessage(role="assistant", content=content))

    def clear(self) -> None:
        """Clear conversation history (keeps system prompt)."""
        self.messages.clear()

    def to_anthropic_messages(self) -> list[dict[str, str]]:
        """Convert messages to Anthropic API format.

        Anthropic handles system prompts separately, so this only
        returns user/assistant messages.
        """
        return [
            {"role": m.role, "content": m.content}
            for m in self.messages
            if m.role in ("user", "assistant")
        ]

    def to_openai_messages(self) -> list[dict[str, str]]:
        """Convert messages to OpenAI API format.

        OpenAI expects system prompts inline as messages.
        """
        msgs: list[dict[str, str]] = []
        if self.system_prompt:
            msgs.append({"role": "system", "content": self.system_prompt})
        msgs.extend(
            {"role": m.role, "content": m.content}
            for m in self.messages
            if m.role in ("user", "assistant")
        )
        return msgs


async def stream_response(
    session: ChatSession,
    provider: str,
    provider_config: ProviderConfig,
    model: str | None = None,
) -> AsyncGenerator[str, None]:
    """Stream a response from the specified provider.

    Yields text chunks as they arrive from the model.

    Args:
        session: The current chat session with message history.
        provider: Provider name ('anthropic' or 'openai').
        provider_config: Configuration for the provider (API key, etc.).
        model: Model to use. Falls back to provider_config.model if None.

    Yields:
        Text chunks of the response.
    """
    target_model = model or provider_config.model

    if provider == "anthropic":
        async for chunk in _stream_anthropic(
            session, provider_config.api_key, target_model
        ):
            yield chunk
    elif provider == "openai":
        async for chunk in _stream_openai(
            session, provider_config.api_key, target_model
        ):
            yield chunk
    else:
        raise ValueError(f"Unknown provider: {provider}")


async def get_response(
    session: ChatSession,
    provider: str,
    provider_config: ProviderConfig,
    model: str | None = None,
) -> str:
    """Get a complete (non-streaming) response from the specified provider.

    Args:
        session: The current chat session with message history.
        provider: Provider name ('anthropic' or 'openai').
        provider_config: Configuration for the provider.
        model: Model to use. Falls back to provider_config.model if None.

    Returns:
        The full response text.
    """
    chunks: list[str] = []
    async for chunk in stream_response(session, provider, provider_config, model):
        chunks.append(chunk)
    return "".join(chunks)


def get_response_sync(
    session: ChatSession,
    provider: str,
    provider_config: ProviderConfig,
    model: str | None = None,
) -> str:
    """Synchronous wrapper around get_response for non-async contexts."""
    return asyncio.run(get_response(session, provider, provider_config, model))


async def _stream_anthropic(
    session: ChatSession,
    api_key: str,
    model: str,
) -> AsyncGenerator[str, None]:
    """Stream a response from the Anthropic API."""
    client = anthropic.AsyncAnthropic(api_key=api_key)

    kwargs: dict = {
        "model": model,
        "max_tokens": 4096,
        "messages": session.to_anthropic_messages(),
    }
    if session.system_prompt:
        kwargs["system"] = session.system_prompt

    async with client.messages.stream(**kwargs) as stream:
        async for text in stream.text_stream:
            yield text


async def _stream_openai(
    session: ChatSession,
    api_key: str,
    model: str,
) -> AsyncGenerator[str, None]:
    """Stream a response from the OpenAI API."""
    client = openai.AsyncOpenAI(api_key=api_key)

    stream = await client.chat.completions.create(
        model=model,
        messages=session.to_openai_messages(),
        max_tokens=4096,
        stream=True,
    )

    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
