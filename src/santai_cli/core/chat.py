"""Shared chat engine for Santai CLI.

Provides a provider-agnostic chat interface with streaming support
for both Anthropic and OpenAI models. Used by the CLI, TUI, and
Web interfaces.
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anthropic
import openai

from santai_cli.core.config import ProviderConfig

TOOLS = [
    {
        "name": "write_file",
        "description": "Write content to a file. Creates directories as needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filepath": {
                    "type": "string",
                    "description": "The file path to write to (relative to project root)",
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file",
                },
            },
            "required": ["filepath", "content"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filepath": {
                    "type": "string",
                    "description": "The file path to read (relative to project root)",
                },
            },
            "required": ["filepath"],
        },
    },
    {
        "name": "list_dir",
        "description": "List files in a directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "The directory to list (relative to project root). "
                    "Defaults to project root.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "mkdir",
        "description": "Create a directory. Creates parent directories as needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The directory path to create (relative to project root)",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "remove_file",
        "description": "Remove a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filepath": {
                    "type": "string",
                    "description": "The file path to remove (relative to project root)",
                },
            },
            "required": ["filepath"],
        },
    },
    {
        "name": "remove_dir",
        "description": (
            "Remove a directory. If the directory is empty, it is deleted immediately. "
            "If it has contents, the tool returns a warning — relay the warning to the user "
            "and ask for confirmation. Once the user confirms, call again with confirmed=true."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The directory path to remove (relative to project root)",
                },
                "confirmed": {
                    "type": "boolean",
                    "description": "Set to true after the user has confirmed deletion of a non-empty directory.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "move",
        "description": "Move a file or directory to a new location. Prefer this over manually copying and deleting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "The source path (relative to project root)",
                },
                "destination": {
                    "type": "string",
                    "description": "The destination path (relative to project root)",
                },
            },
            "required": ["source", "destination"],
        },
    },
]

TOOLS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        },
    }
    for t in TOOLS
]


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
    # Each entry pairs the assistant's tool_calls with their results for one turn.
    tool_turns: list[dict[str, Any]] = field(default_factory=list)
    project_root: Path | None = None

    def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation."""
        self.messages.append(ChatMessage(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant response to the conversation."""
        self.messages.append(ChatMessage(role="assistant", content=content))

    def add_tool_turn(
        self,
        tool_calls: list[dict[str, Any]],
        results: list[tuple[str, dict[str, Any], str]],
    ) -> None:
        """Record one round of tool calls and their results."""
        self.tool_turns.append(
            {
                "calls": tool_calls,
                "results": [
                    {
                        "tool_name": name,
                        "tool_use_id": inp.get("id", "unknown"),
                        "content": content,
                    }
                    for name, inp, content in results
                ],
            }
        )

    def clear(self) -> None:
        """Clear conversation history (keeps system prompt)."""
        self.messages.clear()
        self.tool_turns.clear()

    def to_anthropic_messages(self) -> list[dict[str, Any]]:
        """Convert messages to Anthropic API format."""
        msgs: list[dict[str, Any]] = [
            {"role": m.role, "content": m.content}
            for m in self.messages
            if m.role in ("user", "assistant")
        ]
        for turn in self.tool_turns:
            # Assistant message containing the tool_use blocks
            msgs.append(
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["name"],
                            "input": json.loads(tc.get("arguments", "{}") or "{}"),
                        }
                        for tc in turn["calls"]
                    ],
                }
            )
            # User message containing the tool_result blocks
            msgs.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": r["tool_use_id"],
                            "content": r["content"],
                        }
                        for r in turn["results"]
                    ],
                }
            )
        return msgs

    def to_openai_messages(self) -> list[dict[str, Any]]:
        """Convert messages to OpenAI API format."""
        msgs: list[dict[str, Any]] = []
        if self.system_prompt:
            msgs.append({"role": "system", "content": self.system_prompt})
        msgs.extend(
            {"role": m.role, "content": m.content}
            for m in self.messages
            if m.role in ("user", "assistant")
        )
        for turn in self.tool_turns:
            # Assistant message with tool_calls array
            msgs.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": tc.get("arguments", "{}") or "{}",
                            },
                        }
                        for tc in turn["calls"]
                    ],
                }
            )
            # One tool message per result
            for r in turn["results"]:
                msgs.append(
                    {
                        "role": "tool",
                        "tool_call_id": r["tool_use_id"],
                        "name": r["tool_name"],
                        "content": r["content"],
                    }
                )
        return msgs


async def stream_response(
    session: ChatSession,
    provider: str,
    provider_config: ProviderConfig,
    model: str | None = None,
) -> AsyncGenerator[str | dict, None]:
    """Stream a response from the specified provider with tool support.

    Handles the full conversation loop: if the model calls tools,
    executes them and continues streaming the response.

    Args:
        session: The current chat session with message history.
        provider: Provider name ('anthropic' or 'openai').
        provider_config: Configuration for the provider (API key, etc.).
        model: Model to use. Falls back to provider_config.model if None.

    Yields:
        Text chunks (str) or file event dicts like
        {"event": "file_written", "path": "..."}.
    """
    target_model = model or provider_config.model
    max_tool_turns = 10

    for _ in range(max_tool_turns):
        if provider == "anthropic":
            text, tool_calls = await _stream_anthropic_with_tools(
                session, provider_config.api_key, target_model
            )
        else:
            text, tool_calls = await _stream_openai_with_tools(
                session, provider_config.api_key, target_model, provider_config.base_url
            )

        if not tool_calls:
            if text:
                yield text
            break

        results = []
        for tool_call in tool_calls:
            result = execute_tool(tool_call, session.project_root)
            results.append((tool_call.get("name", "unknown"), tool_call, result))
            tool_name = tool_call.get("name", "")
            if tool_name in ("write_file", "move"):
                try:
                    args = json.loads(tool_call.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                path = (
                    args.get("destination")
                    if tool_name == "move"
                    else args.get("filepath")
                )
                if path:
                    yield {"event": "file_written", "path": path}
        session.add_tool_turn(tool_calls, results)


async def _stream_anthropic_with_tools(
    session: ChatSession,
    api_key: str,
    model: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Stream from Anthropic API with tool support.

    Returns (text, tool_calls) tuple.
    """
    client = anthropic.AsyncAnthropic(api_key=api_key)
    tool_calls: list[dict[str, Any]] = []
    full_text = ""

    kwargs: dict = {
        "model": model,
        "max_tokens": 4096,
        "messages": session.to_anthropic_messages(),
        "tools": TOOLS,
    }
    if session.system_prompt:
        kwargs["system"] = session.system_prompt

    pending_tool: dict[str, Any] | None = None

    async with client.messages.stream(**kwargs) as stream:
        async for event in stream:
            if event.type == "content_block_delta":
                delta = getattr(event, "delta", None)
                delta_type = getattr(delta, "type", None)
                if delta_type == "text_delta":
                    full_text += getattr(delta, "text", "")
                elif delta_type == "input_json_delta" and pending_tool is not None:
                    args_text = getattr(delta, "partial_json", "")
                    pending_tool["arguments"] = (
                        pending_tool.get("arguments", "") + args_text
                    )
            elif event.type == "content_block_start":
                block = getattr(event, "content_block", None)
                block_type = getattr(block, "type", None)
                if block_type == "tool_use":
                    pending_tool = {
                        "id": getattr(block, "id", ""),
                        "name": getattr(block, "name", ""),
                        "arguments": "",
                    }
            elif event.type == "content_block_stop":
                if pending_tool is not None:
                    tool_calls.append(pending_tool)
                    pending_tool = None
    return full_text, tool_calls


async def _stream_openai_with_tools(
    session: ChatSession,
    api_key: str,
    model: str,
    base_url: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Stream from OpenAI API with tool support.

    Returns (text, tool_calls) tuple.
    """
    client_kwargs: dict = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = openai.AsyncOpenAI(**client_kwargs)
    pending_tools: dict[int, dict[str, Any]] = {}
    full_text = ""

    stream = await client.chat.completions.create(
        model=model,
        messages=session.to_openai_messages(),
        max_tokens=4096,
        stream=True,
        tools=TOOLS_OPENAI,  # type: ignore[arg-type]
    )

    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta:
            delta = chunk.choices[0].delta
            if delta.content:
                full_text += delta.content
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in pending_tools:
                        pending_tools[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc.id:
                        pending_tools[idx]["id"] = tc.id
                    if tc.function and tc.function.name:
                        pending_tools[idx]["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        pending_tools[idx]["arguments"] += tc.function.arguments

    return full_text, list(pending_tools.values())


def execute_tool(tool_call: dict[str, Any], project_root: Path | None) -> str:
    """Execute a tool call and return the result as a string."""
    tool_name = tool_call.get("name", "")
    if tool_name == "write_file":
        return _tool_write_file(tool_call, project_root)
    elif tool_name == "read_file":
        return _tool_read_file(tool_call, project_root)
    elif tool_name == "list_dir":
        return _tool_list_dir(tool_call, project_root)
    elif tool_name == "mkdir":
        return _tool_mkdir(tool_call, project_root)
    elif tool_name == "remove_file":
        return _tool_remove_file(tool_call, project_root)
    elif tool_name == "remove_dir":
        return _tool_remove_dir(tool_call, project_root)
    elif tool_name == "move":
        return _tool_move(tool_call, project_root)
    return f"Error: Unknown tool '{tool_name}'"


def _resolve_path(filepath: str, project_root: Path | None) -> Path:
    """Resolve a filepath relative to project root."""
    if project_root is None:
        project_root = Path.cwd()
    return (project_root / filepath).resolve()


def _tool_write_file(tool_call: dict[str, Any], project_root: Path | None) -> str:
    """Execute write_file tool."""
    try:
        args = json.loads(tool_call.get("arguments", "{}"))
    except json.JSONDecodeError:
        args = {}

    filepath = args.get("filepath", "")
    content = args.get("content", "")
    if not filepath:
        return "Error: filepath is required"

    path = _resolve_path(filepath, project_root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"OK: wrote {len(content)} bytes to {filepath}"
    except Exception as e:
        return f"Error: {e}"


def _tool_read_file(tool_call: dict[str, Any], project_root: Path | None) -> str:
    """Execute read_file tool."""
    try:
        args = json.loads(tool_call.get("arguments", "{}"))
    except json.JSONDecodeError:
        args = {}

    filepath = args.get("filepath", "")
    if not filepath:
        return "Error: filepath is required"

    path = _resolve_path(filepath, project_root)
    try:
        content = path.read_text(encoding="utf-8")
        max_len = 10000
        if len(content) > max_len:
            content = (
                content[:max_len] + f"\n... (truncated, {len(content)} total bytes)"
            )
        return content
    except Exception as e:
        return f"Error: {e}"


def _tool_list_dir(tool_call: dict[str, Any], project_root: Path | None) -> str:
    """Execute list_dir tool."""
    try:
        args = json.loads(tool_call.get("arguments", "{}"))
    except json.JSONDecodeError:
        args = {}

    directory = args.get("directory", "")
    if not directory:
        directory = "."

    path = _resolve_path(directory, project_root)
    try:
        if not path.is_dir():
            return f"Error: {directory} is not a directory"
        entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        lines = [f"{'d' if p.is_dir() else 'f'} {p.name}" for p in entries]
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def _tool_mkdir(tool_call: dict[str, Any], project_root: Path | None) -> str:
    """Execute mkdir tool."""
    try:
        args = json.loads(tool_call.get("arguments", "{}"))
    except json.JSONDecodeError:
        args = {}

    dir_path = args.get("path", "")
    if not dir_path:
        return "Error: path is required"

    path = _resolve_path(dir_path, project_root)
    try:
        path.mkdir(parents=True, exist_ok=True)
        return f"OK: created directory {dir_path}"
    except Exception as e:
        return f"Error: {e}"


def _tool_remove_file(tool_call: dict[str, Any], project_root: Path | None) -> str:
    """Execute remove_file tool."""
    try:
        args = json.loads(tool_call.get("arguments", "{}"))
    except json.JSONDecodeError:
        args = {}

    filepath = args.get("filepath", "")
    if not filepath:
        return "Error: filepath is required"

    path = _resolve_path(filepath, project_root)
    try:
        path.unlink()
        return f"OK: removed {filepath}"
    except Exception as e:
        return f"Error: {e}"


def _tool_remove_dir(tool_call: dict[str, Any], project_root: Path | None) -> str:
    """Execute remove_dir tool."""
    import shutil

    try:
        args = json.loads(tool_call.get("arguments", "{}"))
    except json.JSONDecodeError:
        args = {}

    dir_path = args.get("path", "")
    confirmed = args.get("confirmed", False)
    if not dir_path:
        return "Error: path is required"

    path = _resolve_path(dir_path, project_root)
    if not path.is_dir():
        return f"Error: {dir_path} is not a directory"

    contents = list(path.iterdir())
    if contents and not confirmed:
        count = len(contents)
        item_str = "1 item" if count == 1 else f"{count} items"
        return (
            f"CONFIRM_REQUIRED: The '{dir_path}' folder contains {item_str}. "
            "Are you sure you want to delete this folder and all its contents? "
            "(If yes, call remove_dir again with confirmed=true.)"
        )

    try:
        shutil.rmtree(path)
        return f"OK: removed directory {dir_path}"
    except Exception as e:
        return f"Error: {e}"


def _tool_move(tool_call: dict[str, Any], project_root: Path | None) -> str:
    """Execute move tool."""
    import shutil

    try:
        args = json.loads(tool_call.get("arguments", "{}"))
    except json.JSONDecodeError:
        args = {}

    source = args.get("source", "")
    destination = args.get("destination", "")
    if not source or not destination:
        return "Error: source and destination are required"

    src_path = _resolve_path(source, project_root)
    dst_path = _resolve_path(destination, project_root)
    try:
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dst_path))
        return f"OK: moved {source} to {destination}"
    except Exception as e:
        return f"Error: {e}"


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
    """Stream a response from the Anthropic API (legacy, unused)."""
    client = anthropic.AsyncAnthropic(api_key=api_key)

    kwargs: dict = {
        "model": model,
        "max_tokens": 4096,
        "messages": session.to_anthropic_messages(),
    }
    if session.system_prompt:
        kwargs["system"] = session.system_prompt

    async with client.messages.stream(**kwargs) as stream:  # type: ignore[union-attr]
        async for text in stream.text_stream:  # type: ignore[union-attr]
            yield text


async def _stream_openai(
    session: ChatSession,
    api_key: str,
    model: str,
    base_url: str | None = None,
) -> AsyncGenerator[str, None]:
    """Stream a response from the OpenAI API (legacy, unused)."""
    client_kwargs: dict = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = openai.AsyncOpenAI(**client_kwargs)  # type: ignore[arg-type]

    stream = await client.chat.completions.create(  # type: ignore[call-overload]
        model=model,
        messages=session.to_openai_messages(),
        max_tokens=4096,
        stream=True,
    )

    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
