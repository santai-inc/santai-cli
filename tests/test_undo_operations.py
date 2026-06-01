"""Integration tests for the inverse-roundtrip behaviour of the file API.

Each test exercises a forward operation followed by its manual reverse call,
verifying that the filesystem returns to its original state. These tests cover
the API primitives that the JS undo system relies on — they do not exercise the
JS snapshot/restore logic or UndoManager state machine.
"""

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def web_client(tmp_path: Path):
    from fastapi.testclient import TestClient

    from santai_cli.core.project import SantaiProject
    from santai_cli.web.app import create_app

    project = SantaiProject(root=tmp_path, name=tmp_path.name)
    app = create_app(project)
    return TestClient(app), project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_file(project, rel_path: str, content: str) -> Path:
    """Create a file with *content* inside the project root."""
    p = project.root / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# SAVE (text edit) — undo restores previous content
# ---------------------------------------------------------------------------


def test_inverse_roundtrip_save_restores_previous_content(web_client):
    client, project = web_client

    _write_file(project, "notes/hello.md", "original content")

    # Forward: save new content
    resp = client.post(
        "/api/files/save?path=notes/hello.md",
        json={"content": "updated content"},
    )
    assert resp.status_code == 200
    assert (project.root / "notes/hello.md").read_text() == "updated content"

    # Undo: restore old content (same endpoint, old content as body)
    resp = client.post(
        "/api/files/save?path=notes/hello.md",
        json={"content": "original content"},
    )
    assert resp.status_code == 200
    assert (project.root / "notes/hello.md").read_text() == "original content"


def test_inverse_roundtrip_save_rejects_invalid_path(web_client):
    client, _ = web_client
    resp = client.post(
        "/api/files/save?path=../../etc/passwd",
        json={"content": "hack"},
    )
    assert resp.status_code in (400, 403, 404, 422)


# ---------------------------------------------------------------------------
# RENAME — undo renames back to original name
# ---------------------------------------------------------------------------


def test_inverse_roundtrip_rename_restores_original_name(web_client):
    client, project = web_client

    _write_file(project, "docs/original.md", "content")

    # Forward: rename to new-name.md
    resp = client.post(
        "/api/files/rename",
        json={"old_path": "docs/original.md", "new_name": "renamed.md"},
    )
    assert resp.status_code == 200
    assert (project.root / "docs/renamed.md").exists()
    assert not (project.root / "docs/original.md").exists()

    # Undo: rename back to original.md
    resp = client.post(
        "/api/files/rename",
        json={"old_path": "docs/renamed.md", "new_name": "original.md"},
    )
    assert resp.status_code == 200
    assert (project.root / "docs/original.md").exists()
    assert not (project.root / "docs/renamed.md").exists()


def test_inverse_roundtrip_rename_folder_restores_original_name(web_client):
    client, project = web_client

    (project.root / "old-folder").mkdir()
    (project.root / "old-folder/file.md").write_text("hi")

    resp = client.post(
        "/api/files/rename",
        json={"old_path": "old-folder", "new_name": "new-folder"},
    )
    assert resp.status_code == 200
    assert (project.root / "new-folder").is_dir()

    # Undo
    resp = client.post(
        "/api/files/rename",
        json={"old_path": "new-folder", "new_name": "old-folder"},
    )
    assert resp.status_code == 200
    assert (project.root / "old-folder").is_dir()
    assert not (project.root / "new-folder").exists()


# ---------------------------------------------------------------------------
# MOVE — undo moves items back to their original location
# ---------------------------------------------------------------------------


def test_inverse_roundtrip_move_file_restores_original_location(web_client):
    client, project = web_client

    _write_file(project, "src/file.md", "hello")
    (project.root / "dest").mkdir()

    # Forward: move src/file.md → dest/
    resp = client.post(
        "/api/files/move",
        json={"source_path": "src/file.md", "target_folder": "dest"},
    )
    assert resp.status_code == 200
    assert (project.root / "dest/file.md").exists()
    assert not (project.root / "src/file.md").exists()

    # Undo: move dest/file.md → src/
    resp = client.post(
        "/api/files/move",
        json={"source_path": "dest/file.md", "target_folder": "src"},
    )
    assert resp.status_code == 200
    assert (project.root / "src/file.md").exists()
    assert not (project.root / "dest/file.md").exists()


def test_inverse_roundtrip_move_folder_restores_original_location(web_client):
    client, project = web_client

    (project.root / "source-dir").mkdir()
    (project.root / "source-dir/child.md").write_text("data")
    (project.root / "archive").mkdir()

    # Forward: move source-dir into archive/
    resp = client.post(
        "/api/files/move",
        json={"source_path": "source-dir", "target_folder": "archive"},
    )
    assert resp.status_code == 200
    assert (project.root / "archive/source-dir").is_dir()

    # Undo: move archive/source-dir back to root (empty target = root)
    resp = client.post(
        "/api/files/move",
        json={"source_path": "archive/source-dir", "target_folder": ""},
    )
    assert resp.status_code == 200
    assert (project.root / "source-dir").is_dir()
    assert not (project.root / "archive/source-dir").exists()


# ---------------------------------------------------------------------------
# CREATE_FILE — undo deletes the created file
# ---------------------------------------------------------------------------


def test_inverse_roundtrip_create_file_deletes_it(web_client):
    client, project = web_client

    # Forward: create new file
    resp = client.post(
        "/api/files/touch",
        json={"path": "", "name": "new-note.md"},
    )
    assert resp.status_code == 200
    created_path = resp.json().get("path", "new-note.md")
    assert (project.root / created_path).exists()

    # Undo: delete the file
    resp = client.delete(f"/api/files?path={created_path}")
    assert resp.status_code == 200
    assert not (project.root / created_path).exists()


def test_inverse_roundtrip_create_file_in_subfolder(web_client):
    client, project = web_client

    (project.root / "notes").mkdir()
    resp = client.post(
        "/api/files/touch",
        json={"path": "notes", "name": "memo.md"},
    )
    assert resp.status_code == 200
    assert (project.root / "notes/memo.md").exists()

    resp = client.delete("/api/files?path=notes/memo.md")
    assert resp.status_code == 200
    assert not (project.root / "notes/memo.md").exists()


# ---------------------------------------------------------------------------
# CREATE_FOLDER — undo deletes the created folder
# ---------------------------------------------------------------------------


def test_inverse_roundtrip_create_folder_deletes_it(web_client):
    client, project = web_client

    resp = client.post(
        "/api/files/mkdir",
        json={"path": "", "name": "new-project"},
    )
    assert resp.status_code == 200
    assert (project.root / "new-project").is_dir()

    resp = client.delete("/api/files?path=new-project")
    assert resp.status_code == 200
    assert not (project.root / "new-project").exists()


def test_inverse_roundtrip_create_nested_folder(web_client):
    client, project = web_client

    (project.root / "parent").mkdir()
    resp = client.post(
        "/api/files/mkdir",
        json={"path": "parent", "name": "child"},
    )
    assert resp.status_code == 200
    assert (project.root / "parent/child").is_dir()

    resp = client.delete("/api/files?path=parent/child")
    assert resp.status_code == 200
    assert not (project.root / "parent/child").exists()


# ---------------------------------------------------------------------------
# Keyboard shortcut integration: Ctrl/Cmd+Z should not interfere with edits
# (Tested via frontend JS; these Python tests cover the API surface only.)
# ---------------------------------------------------------------------------


def test_save_endpoint_is_idempotent_for_same_content(web_client):
    """Saving the same content twice is safe (no-op from undo perspective)."""
    client, project = web_client
    _write_file(project, "file.md", "hello")

    resp1 = client.post("/api/files/save?path=file.md", json={"content": "hello"})
    resp2 = client.post("/api/files/save?path=file.md", json={"content": "hello"})
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert (project.root / "file.md").read_text() == "hello"
