"""Persistence layer for chat sessions.

Saves and loads chat sessions as Markdown files under
<project_root>/history/chat-history/.

Filenames use the pattern: MM-DD-YYYY - Title.md
The session id in the metadata block is the stable lookup key.

File format (transcript first, metadata at the bottom):

    **You:**
    First user message here.

    **Assistant:**
    Response here.

    ---
    id: 20260527-153042-a1b2
    title: "What is recursion?"
    created_at: 2026-05-27T15:30:42+00:00
    updated_at: 2026-05-27T15:45:10+00:00
    provider: anthropic
    model: claude-sonnet-4-6
    agent: null
    message_count: 4
    ---
"""

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from santai_cli.core.chat import ChatMessage, ChatSession
from santai_cli.core.project import SantaiProject

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MULTI_DASH = re.compile(r"-{2,}")
_MULTI_SPACE = re.compile(r" {2,}")


def get_chat_history_dir(project: SantaiProject) -> Path:
    return project.root / "history" / "chat-history"


def _sanitize_title(title: str) -> str:
    """Strip characters not allowed in filenames and normalise whitespace."""
    cleaned = _INVALID_FILENAME_CHARS.sub("", title)
    cleaned = _MULTI_SPACE.sub(" ", cleaned).strip(" -")
    return cleaned[:60] or "Untitled chat"


def _session_filename(title: str, created_at: str, chat_dir: Path) -> str:
    """Return a unique filename stem for a new session."""
    try:
        date_str = datetime.fromisoformat(created_at).strftime("%m-%d-%Y")
    except (ValueError, TypeError):
        date_str = datetime.now(UTC).strftime("%m-%d-%Y")

    base = f"{date_str} - {_sanitize_title(title)}"
    candidate = f"{base}.md"
    if not (chat_dir / candidate).exists():
        return candidate

    counter = 2
    while (chat_dir / f"{base} ({counter}).md").exists():
        counter += 1
    return f"{base} ({counter}).md"


def _find_session_path(chat_dir: Path, session_id: str) -> Path | None:
    """Scan chat_dir for the file whose frontmatter id matches session_id."""
    for path in chat_dir.glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
            id_inline = f"\nid: {session_id}\n"
            id_first = f"---\nid: {session_id}\n"
            if id_inline in text or text.startswith(id_first):
                return path
        except OSError:
            continue
    return None


def generate_session_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    suffix = uuid.uuid4().hex[:4]
    return f"{ts}-{suffix}"


def auto_title(messages: list[dict[str, str]]) -> str:
    for msg in messages:
        if msg.get("role") == "user":
            text = msg.get("content", "").strip()
            return text[:60] + ("…" if len(text) > 60 else "")
    return "Untitled chat"


@dataclass
class ChatSessionMetadata:
    id: str
    title: str
    created_at: str
    updated_at: str
    provider: str
    model: str
    agent: str | None
    message_count: int


@dataclass
class PersistedChatSession:
    id: str
    title: str
    created_at: str
    updated_at: str
    provider: str
    model: str
    agent: str | None
    message_count: int
    system_prompt: str | None  # not stored; rebuilt from context on resume
    messages: list[dict[str, str]] = field(default_factory=list)
    tool_turns: list[dict] = field(default_factory=list)  # not stored in Markdown

    def to_metadata(self) -> ChatSessionMetadata:
        return ChatSessionMetadata(
            id=self.id,
            title=self.title,
            created_at=self.created_at,
            updated_at=self.updated_at,
            provider=self.provider,
            model=self.model,
            agent=self.agent,
            message_count=self.message_count,
        )


# ---------------------------------------------------------------------------
# Markdown serialisation
# ---------------------------------------------------------------------------

_MSG_PATTERN = re.compile(
    r"(?:^|\n\n)\*\*(You|Assistant):\*\*\n(.*?)(?=\n\n\*\*(?:You|Assistant):\*\*\n|$)",
    re.DOTALL,
)


def _build_markdown(
    session_id: str,
    title: str,
    created_at: str,
    updated_at: str,
    provider: str,
    model: str,
    agent: str | None,
    messages: list[dict[str, str]],
) -> str:
    agent_val = "null" if agent is None else agent
    metadata_block = (
        "---\n"
        f"id: {session_id}\n"
        f"title: {json.dumps(title, ensure_ascii=False)}\n"
        f"created_at: {created_at}\n"
        f"updated_at: {updated_at}\n"
        f"provider: {provider}\n"
        f"model: {model}\n"
        f"agent: {agent_val}\n"
        f"message_count: {len(messages)}\n"
        "---"
    )
    body_parts = []
    for msg in messages:
        label = "You" if msg["role"] == "user" else "Assistant"
        body_parts.append(f"**{label}:**\n{msg['content']}")
    body = "\n\n".join(body_parts)
    if body:
        return f"{body}\n\n{metadata_block}\n"
    return f"{metadata_block}\n"


def _parse_meta_block(block: str) -> dict:
    """Parse key: value lines from a raw metadata block string."""
    meta: dict = {}
    for line in block.splitlines():
        if ": " in line:
            key, _, raw = line.partition(": ")
            raw = raw.strip()
            if raw == "null":
                meta[key.strip()] = None
            elif raw.isdigit():
                meta[key.strip()] = int(raw)
            elif raw.startswith('"'):
                try:
                    meta[key.strip()] = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    meta[key.strip()] = raw.strip('"')
            else:
                meta[key.strip()] = raw
    return meta


def _parse_markdown(text: str) -> tuple[dict, list[dict[str, str]]]:
    """Parse metadata and messages from a session Markdown file.

    Supports two layouts:
    - New: transcript first, then ``---\\n{meta}\\n---`` at the bottom.
    - Old: ``---\\n{meta}\\n---`` frontmatter at the top (backwards compat).
    """
    meta: dict = {}
    body = text

    # Metadata block at the bottom: \n---\n{key: val...}\n---
    # id: is always the first field, so \n---\nid: locates the opening delimiter.
    if "\n---\nid: " in text:
        sep_idx = text.find("\n---\nid: ")
        close_idx = text.find("\n---", sep_idx + 5)
        if close_idx != -1:
            meta = _parse_meta_block(text[sep_idx + 5 : close_idx])
            body = text[:sep_idx]

    messages: list[dict[str, str]] = []
    for match in _MSG_PATTERN.finditer(body.strip()):
        role_label, content = match.group(1), match.group(2).strip()
        if content:
            role = "user" if role_label == "You" else "assistant"
            messages.append({"role": role, "content": content})

    return meta, messages


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def save_session(
    project: SantaiProject,
    session: ChatSession,
    session_id: str | None,
    title: str | None,
    provider: str,
    model: str,
    agent: str | None,
) -> str:
    """Write a chat session to disk as Markdown. Returns the session_id."""
    chat_dir = get_chat_history_dir(project)
    chat_dir.mkdir(parents=True, exist_ok=True)

    messages = [
        {"role": m.role, "content": m.content}
        for m in session.messages
        if m.role in ("user", "assistant")
    ]

    now = datetime.now(UTC).isoformat()

    computed_title = title or auto_title(messages)

    if session_id is None:
        session_id = generate_session_id()
        created_at = now
        filename = _session_filename(computed_title, now, chat_dir)
    else:
        existing_path = _find_session_path(chat_dir, session_id)
        if existing_path is not None:
            try:
                raw = existing_path.read_text(encoding="utf-8")
                existing_meta, _ = _parse_markdown(raw)
                created_at = existing_meta.get("created_at", now)
            except OSError:
                created_at = now
            filename = existing_path.name  # keep the original filename
        else:
            created_at = now
            filename = _session_filename(computed_title, now, chat_dir)

    content = _build_markdown(
        session_id=session_id,
        title=computed_title,
        created_at=created_at,
        updated_at=now,
        provider=provider,
        model=model,
        agent=agent,
        messages=messages,
    )

    (chat_dir / filename).write_text(content, encoding="utf-8")
    return session_id


def load_session(project: SantaiProject, session_id: str) -> PersistedChatSession:
    """Load a chat session from disk. Raises FileNotFoundError if missing."""
    path = _find_session_path(get_chat_history_dir(project), session_id)
    if path is None:
        raise FileNotFoundError(f"Chat session '{session_id}' not found")

    meta, messages = _parse_markdown(path.read_text(encoding="utf-8"))
    return PersistedChatSession(
        id=meta.get("id", session_id),
        title=meta.get("title", "Untitled chat"),
        created_at=meta.get("created_at", ""),
        updated_at=meta.get("updated_at", ""),
        provider=meta.get("provider", ""),
        model=meta.get("model", ""),
        agent=meta.get("agent"),
        message_count=meta.get("message_count", len(messages)),
        system_prompt=None,
        messages=messages,
        tool_turns=[],
    )


def list_sessions(project: SantaiProject) -> list[ChatSessionMetadata]:
    """Return metadata for all saved sessions, newest first."""
    chat_dir = get_chat_history_dir(project)
    if not chat_dir.is_dir():
        return []

    entries: list[ChatSessionMetadata] = []
    for path in chat_dir.glob("*.md"):
        try:
            meta, messages = _parse_markdown(path.read_text(encoding="utf-8"))
            entries.append(
                ChatSessionMetadata(
                    id=meta.get("id", path.stem),
                    title=meta.get("title", "Untitled chat"),
                    created_at=meta.get("created_at", ""),
                    updated_at=meta.get("updated_at", ""),
                    provider=meta.get("provider", ""),
                    model=meta.get("model", ""),
                    agent=meta.get("agent"),
                    message_count=meta.get("message_count", len(messages)),
                )
            )
        except OSError:
            continue

    entries.sort(key=lambda e: e.updated_at, reverse=True)
    return entries


def delete_session(project: SantaiProject, session_id: str) -> None:
    """Delete a session file. Raises FileNotFoundError if missing."""
    path = _find_session_path(get_chat_history_dir(project), session_id)
    if path is None:
        raise FileNotFoundError(f"Chat session '{session_id}' not found")
    path.unlink()


def restore_chat_session(persisted: PersistedChatSession) -> ChatSession:
    """Reconstruct a ChatSession from a PersistedChatSession for resumption."""
    session = ChatSession()
    for msg in persisted.messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            session.messages.append(ChatMessage(role="user", content=content))
        elif role == "assistant":
            session.messages.append(ChatMessage(role="assistant", content=content))
    return session
