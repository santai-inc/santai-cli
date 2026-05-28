"""Tests for chat history persistence (save, load, list, delete, resume)."""

from pathlib import Path

import pytest

from santai_cli.core.chat import ChatSession
from santai_cli.core.chat_history import (
    _mask_code_blocks,
    _parse_markdown,
    _sanitize_title,
    _session_filename,
    auto_title,
    delete_session,
    generate_session_id,
    get_chat_history_dir,
    hide_session,
    list_sessions,
    load_session,
    rename_session,
    restore_chat_session,
    save_session,
    unhide_session,
)
from santai_cli.core.project import SantaiProject

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(tmp_path: Path) -> SantaiProject:
    return SantaiProject(root=tmp_path, name=tmp_path.name)


def _make_session(user: str = "hello", assistant: str = "world") -> ChatSession:
    s = ChatSession(system_prompt="test prompt")
    s.add_user_message(user)
    s.add_assistant_message(assistant)
    return s


# ---------------------------------------------------------------------------
# Unit tests: core module
# ---------------------------------------------------------------------------


def test_auto_title_uses_first_user_message():
    msgs = [{"role": "user", "content": "What is the capital of France?"}]
    assert auto_title(msgs) == "What is the capital of France?"


def test_auto_title_truncates_at_40_chars():
    long_msg = "A" * 80
    result = auto_title([{"role": "user", "content": long_msg}])
    assert result == "A" * 40 + "…"
    assert len(result) == 41  # 40 chars + ellipsis (U+2026, 1 code point)


def test_auto_title_skips_non_user_messages():
    msgs = [
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "my question"},
    ]
    assert auto_title(msgs) == "my question"


def test_auto_title_fallback_on_empty():
    assert auto_title([]) == "Untitled chat"


def test_generate_session_id_format():
    sid = generate_session_id()
    parts = sid.split("-")
    assert len(parts) == 3  # YYYYMMDD, HHMMSS, 4hexchars
    assert len(parts[0]) == 8
    assert len(parts[1]) == 6
    assert len(parts[2]) == 4


def test_save_creates_chat_history_dir(tmp_path: Path):
    project = _make_project(tmp_path)
    session = _make_session()
    assert not get_chat_history_dir(project).exists()
    save_session(project, session, None, None, "anthropic", "claude-3-5-sonnet", None)
    assert get_chat_history_dir(project).is_dir()


def test_save_and_load_round_trip(tmp_path: Path):
    project = _make_project(tmp_path)
    session = _make_session("Tell me a joke", "Why did the chicken cross the road?")
    sid = save_session(
        project, session, None, "My Chat", "anthropic", "claude-sonnet-4-6", "code"
    )

    loaded = load_session(project, sid)
    assert loaded.id == sid
    assert loaded.title == "My Chat"
    assert loaded.provider == "anthropic"
    assert loaded.model == "claude-sonnet-4-6"
    assert loaded.agent == "code"
    assert loaded.message_count == 2
    assert len(loaded.messages) == 2
    assert loaded.messages[0] == {"role": "user", "content": "Tell me a joke"}
    assert loaded.messages[1]["role"] == "assistant"


def test_save_auto_generates_title_from_messages(tmp_path: Path):
    project = _make_project(tmp_path)
    session = _make_session("What is recursion?")
    sid = save_session(
        project, session, None, None, "anthropic", "claude-sonnet-4-6", None
    )
    loaded = load_session(project, sid)
    assert loaded.title == "What is recursion?"


def test_update_session_overwrites_no_duplicate(tmp_path: Path):
    project = _make_project(tmp_path)
    session = _make_session()
    sid = save_session(project, session, None, None, "anthropic", "model", None)

    # Save again with same id
    session.add_user_message("follow-up")
    session.add_assistant_message("answer")
    save_session(project, session, sid, None, "anthropic", "model", None)

    chat_dir = get_chat_history_dir(project)
    files = list(chat_dir.glob("*.md"))
    assert len(files) == 1
    loaded = load_session(project, sid)
    assert loaded.message_count == 4


def test_save_preserves_created_at_on_update(tmp_path: Path):
    project = _make_project(tmp_path)
    session = _make_session()
    sid = save_session(project, session, None, None, "anthropic", "model", None)
    first = load_session(project, sid)
    original_created_at = first.created_at

    session.add_user_message("more")
    session.add_assistant_message("data")
    save_session(project, session, sid, None, "anthropic", "model", None)
    updated = load_session(project, sid)
    assert updated.created_at == original_created_at


def test_list_sessions_returns_newest_first(tmp_path: Path):
    import time

    project = _make_project(tmp_path)
    for i in range(3):
        s = _make_session(f"question {i}")
        save_session(project, s, None, f"Chat {i}", "anthropic", "model", None)
        time.sleep(0.01)  # ensure distinct updated_at timestamps

    sessions = list_sessions(project)
    assert len(sessions) == 3
    # Newest first: updated_at should be descending
    for j in range(len(sessions) - 1):
        assert sessions[j].updated_at >= sessions[j + 1].updated_at


def test_list_sessions_empty_when_no_dir(tmp_path: Path):
    project = _make_project(tmp_path)
    assert list_sessions(project) == []


def test_delete_session(tmp_path: Path):
    project = _make_project(tmp_path)
    session = _make_session()
    sid = save_session(project, session, None, None, "anthropic", "model", None)

    delete_session(project, sid)
    with pytest.raises(FileNotFoundError):
        load_session(project, sid)


def test_delete_session_raises_when_missing(tmp_path: Path):
    project = _make_project(tmp_path)
    with pytest.raises(FileNotFoundError):
        delete_session(project, "nonexistent-id")


def test_load_session_raises_when_missing(tmp_path: Path):
    project = _make_project(tmp_path)
    with pytest.raises(FileNotFoundError):
        load_session(project, "nonexistent-id")


def test_restore_chat_session(tmp_path: Path):
    project = _make_project(tmp_path)
    original = _make_session("question", "answer")
    sid = save_session(project, original, None, None, "anthropic", "model", None)

    persisted = load_session(project, sid)
    restored = restore_chat_session(persisted)

    assert len(restored.messages) == 2
    assert restored.messages[0].role == "user"
    assert restored.messages[0].content == "question"
    assert restored.messages[1].role == "assistant"
    assert restored.messages[1].content == "answer"


def test_chat_history_path_on_project(tmp_path: Path):
    project = _make_project(tmp_path)
    assert project.chat_history_path == tmp_path / "history" / "chat-history"


def test_get_chat_history_dir(tmp_path: Path):
    project = _make_project(tmp_path)
    assert get_chat_history_dir(project) == tmp_path / "history" / "chat-history"


def test_code_block_masking_ignores_speaker_labels_inside_fences():
    """Speaker labels inside fenced code blocks must not split the message."""
    masked, replacements = _mask_code_blocks(
        "```\n**You:** example\n**Assistant:** reply\n```"
    )
    assert "**You:**" not in masked
    assert "**Assistant:**" not in masked
    assert len(replacements) == 1


def test_parse_markdown_code_block_not_split(tmp_path: Path):
    """A message containing a fenced code block with speaker labels is parsed intact."""
    code_block = "```\n**You:** Hello!\n**Assistant:** Hi!\n```"
    content_with_block = (
        "**You:**\nHow do I greet someone?\n\n"
        f"**Assistant:**\nHere is an example:\n\n{code_block}\n\n"
        '---\nid: test-id-0001\ntitle: "test"\n'
        "created_at: 2026-01-01T00:00:00+00:00\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "provider: anthropic\nmodel: m\nagent: null\n"
        "message_count: 2\n---\n"
    )
    _meta, messages = _parse_markdown(content_with_block)
    assert len(messages) == 2
    assert messages[1]["role"] == "assistant"
    assert "```" in messages[1]["content"]
    assert "**You:** Hello!" in messages[1]["content"]


def test_index_file_created_on_save(tmp_path: Path):
    project = _make_project(tmp_path)
    session = _make_session()
    save_session(project, session, None, None, "anthropic", "model", None)

    chat_dir = get_chat_history_dir(project)
    assert (chat_dir / "_index.json").exists()


def test_index_entry_removed_on_delete(tmp_path: Path):
    import json

    project = _make_project(tmp_path)
    session = _make_session()
    sid = save_session(project, session, None, None, "anthropic", "model", None)
    delete_session(project, sid)

    chat_dir = get_chat_history_dir(project)
    index = json.loads((chat_dir / "_index.json").read_text())
    assert sid not in index


def test_rename_session_renames_file(tmp_path: Path):
    project = _make_project(tmp_path)
    session = _make_session("original question")
    sid = save_session(project, session, None, "Old Title", "anthropic", "model", None)

    chat_dir = get_chat_history_dir(project)
    old_files = list(chat_dir.glob("*.md"))
    assert any("Old-Title" in f.name or "Old Title" in f.name for f in old_files)

    rename_session(project, sid, "New Title")

    new_files = list(chat_dir.glob("*.md"))
    assert len(new_files) == 1
    assert "New Title" in new_files[0].name
    assert not any("Old Title" in f.name for f in new_files)

    loaded = load_session(project, sid)
    assert loaded.title == "New Title"


def test_rename_session_same_sanitized_name_updates_in_place(tmp_path: Path):
    project = _make_project(tmp_path)
    session = _make_session()
    sid = save_session(
        project, session, None, "Hello World", "anthropic", "model", None
    )

    chat_dir = get_chat_history_dir(project)
    original_files = list(chat_dir.glob("*.md"))
    assert len(original_files) == 1
    original_name = original_files[0].name

    # Extra space sanitizes to same base name — should not create a duplicate
    rename_session(project, sid, "Hello  World")

    files = list(chat_dir.glob("*.md"))
    assert len(files) == 1
    assert files[0].name == original_name


def test_hide_session_excludes_from_list(tmp_path: Path):
    project = _make_project(tmp_path)
    s1 = _make_session("question one")
    s2 = _make_session("question two")
    sid1 = save_session(project, s1, None, "Chat 1", "anthropic", "model", None)
    sid2 = save_session(project, s2, None, "Chat 2", "anthropic", "model", None)

    hide_session(project, sid1)

    visible = list_sessions(project)
    ids = [s.id for s in visible]
    assert sid1 not in ids
    assert sid2 in ids

    # File still exists on disk
    chat_dir = get_chat_history_dir(project)
    assert len(list(chat_dir.glob("*.md"))) == 2


def test_unhide_session_restores_to_list(tmp_path: Path):
    project = _make_project(tmp_path)
    session = _make_session()
    sid = save_session(project, session, None, None, "anthropic", "model", None)

    hide_session(project, sid)
    assert all(s.id != sid for s in list_sessions(project))

    unhide_session(project, sid)
    assert any(s.id == sid for s in list_sessions(project))


def test_delete_session_cleans_hidden_set(tmp_path: Path):
    project = _make_project(tmp_path)
    session = _make_session()
    sid = save_session(project, session, None, None, "anthropic", "model", None)

    hide_session(project, sid)
    delete_session(project, sid)

    # After real delete, hidden set should no longer contain the id
    chat_dir = get_chat_history_dir(project)
    import json

    hidden = set(json.loads((chat_dir / "_hidden.json").read_text()))
    assert sid not in hidden


def test_rebuild_index_finds_existing_files(tmp_path: Path):
    project = _make_project(tmp_path)
    session = _make_session()
    sid = save_session(project, session, None, None, "anthropic", "model", None)

    # Delete the index to simulate a missing/stale index
    chat_dir = get_chat_history_dir(project)
    (chat_dir / "_index.json").unlink()

    # load_session should still work by rebuilding the index
    loaded = load_session(project, sid)
    assert loaded.id == sid


# ---------------------------------------------------------------------------
# Integration tests: web API endpoints
# ---------------------------------------------------------------------------


@pytest.fixture()
def web_client(tmp_path: Path):
    """Create a FastAPI test client with a temporary project."""
    from fastapi.testclient import TestClient

    from santai_cli.web.app import create_app

    project = SantaiProject(root=tmp_path, name=tmp_path.name)
    app = create_app(project)
    return TestClient(app), project


def test_api_list_empty(web_client):
    client, _ = web_client
    resp = client.get("/api/chat/history")
    assert resp.status_code == 200
    assert resp.json() == []


def test_api_save_and_list(web_client):
    client, _ = web_client
    payload = {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ],
    }
    save_resp = client.post("/api/chat/history", json=payload)
    assert save_resp.status_code == 200
    sid = save_resp.json()["session_id"]
    assert sid

    list_resp = client.get("/api/chat/history")
    assert list_resp.status_code == 200
    sessions = list_resp.json()
    assert len(sessions) == 1
    assert sessions[0]["id"] == sid
    assert sessions[0]["title"] == "Hello"
    assert sessions[0]["message_count"] == 2


def test_api_load_session(web_client):
    client, _ = web_client
    payload = {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "agent": "code",
        "messages": [
            {"role": "user", "content": "Explain recursion"},
            {"role": "assistant", "content": "Recursion is…"},
        ],
    }
    sid = client.post("/api/chat/history", json=payload).json()["session_id"]

    resp = client.get(f"/api/chat/history/{sid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == sid
    assert data["agent"] == "code"
    assert len(data["messages"]) == 2
    assert data["messages"][0]["content"] == "Explain recursion"


def test_api_load_missing_returns_404(web_client):
    client, _ = web_client
    resp = client.get("/api/chat/history/does-not-exist")
    assert resp.status_code == 404


def test_api_delete_session(web_client):
    client, _ = web_client
    payload = {
        "provider": "openai",
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "hi"}],
    }
    sid = client.post("/api/chat/history", json=payload).json()["session_id"]
    del_resp = client.delete(f"/api/chat/history/{sid}")
    assert del_resp.status_code == 200

    get_resp = client.get(f"/api/chat/history/{sid}")
    assert get_resp.status_code == 404


def test_api_delete_missing_returns_404(web_client):
    client, _ = web_client
    resp = client.delete("/api/chat/history/nonexistent")
    assert resp.status_code == 404


def test_api_update_title(web_client):
    client, _ = web_client
    payload = {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "messages": [{"role": "user", "content": "Original title from message"}],
    }
    sid = client.post("/api/chat/history", json=payload).json()["session_id"]

    patch_resp = client.patch(
        f"/api/chat/history/{sid}/title", json={"title": "My Custom Title"}
    )
    assert patch_resp.status_code == 200

    loaded = client.get(f"/api/chat/history/{sid}").json()
    assert loaded["title"] == "My Custom Title"


def test_api_update_with_existing_session_id(web_client):
    client, _ = web_client
    payload = {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "messages": [{"role": "user", "content": "First message"}],
    }
    sid = client.post("/api/chat/history", json=payload).json()["session_id"]

    # Update with same session_id (should overwrite, not create new)
    payload2 = {
        "session_id": sid,
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "messages": [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "Response"},
            {"role": "user", "content": "Follow-up"},
        ],
    }
    resp2 = client.post("/api/chat/history", json=payload2)
    assert resp2.status_code == 200
    assert resp2.json()["session_id"] == sid

    list_resp = client.get("/api/chat/history")
    assert len(list_resp.json()) == 1  # still only one session
    loaded = client.get(f"/api/chat/history/{sid}").json()
    assert loaded["message_count"] == 3


# ---------------------------------------------------------------------------
# _sanitize_title
# ---------------------------------------------------------------------------


def test_sanitize_title_empty_returns_untitled():
    assert _sanitize_title("") == "Untitled chat"


def test_sanitize_title_all_punct_returns_untitled():
    assert _sanitize_title("---...") == "Untitled chat"


def test_sanitize_title_strips_leading_dot():
    assert not _sanitize_title(". hidden").startswith(".")


def test_sanitize_title_truncates_at_60():
    long = "a" * 80
    assert len(_sanitize_title(long)) == 60


def test_sanitize_title_collapses_spaces():
    assert _sanitize_title("hello   world") == "hello world"


# ---------------------------------------------------------------------------
# _session_filename collision counter
# ---------------------------------------------------------------------------


def test_session_filename_collision_counter(tmp_path: Path):
    chat_dir = tmp_path
    created_at = "2026-01-15T12:00:00+00:00"
    first = _session_filename("My Chat", created_at, chat_dir)
    assert first == "01-15-2026 - My Chat.md"

    # Simulate the first file existing
    (chat_dir / first).touch()
    second = _session_filename("My Chat", created_at, chat_dir)
    assert second == "01-15-2026 - My Chat (2).md"

    (chat_dir / second).touch()
    third = _session_filename("My Chat", created_at, chat_dir)
    assert third == "01-15-2026 - My Chat (3).md"


# ---------------------------------------------------------------------------
# Old-format round-trip (legacy --- block migrates to HTML comment on save)
# ---------------------------------------------------------------------------


def test_old_format_roundtrip(tmp_path: Path):
    """Old --- metadata block loads and re-saves in HTML comment format."""
    project = _make_project(tmp_path)
    chat_dir = get_chat_history_dir(project)
    chat_dir.mkdir(parents=True, exist_ok=True)

    old_content = (
        "**You:**\nHello\n\n"
        "**Assistant:**\nHi there\n\n"
        '---\nid: legacy-id-0001\ntitle: "Old format"\n'
        "created_at: 2026-01-01T00:00:00+00:00\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "provider: anthropic\nmodel: m\nagent: null\n"
        "message_count: 2\n---\n"
    )
    (chat_dir / "01-01-2026 - Old format.md").write_text(old_content, encoding="utf-8")

    # Load via the public API
    loaded = load_session(project, "legacy-id-0001")
    assert loaded.id == "legacy-id-0001"
    assert loaded.title == "Old format"
    assert len(loaded.messages) == 2

    # Re-save — the new file should use HTML comment format
    session = restore_chat_session(loaded)
    save_session(
        project,
        session,
        "legacy-id-0001",
        loaded.title,
        loaded.provider,
        loaded.model,
        loaded.agent,
    )
    files = list(chat_dir.glob("*.md"))
    assert len(files) == 1
    new_content = files[0].read_text(encoding="utf-8")
    assert "<!-- santai" in new_content
    assert "---\nid:" not in new_content


# ---------------------------------------------------------------------------
# hide_session validates existence
# ---------------------------------------------------------------------------


def test_hide_session_raises_for_missing_session(tmp_path: Path):
    project = _make_project(tmp_path)
    with pytest.raises(FileNotFoundError):
        hide_session(project, "nonexistent-id")
