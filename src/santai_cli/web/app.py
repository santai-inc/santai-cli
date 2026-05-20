"""FastAPI web application for Santai."""

import logging
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from santai_cli.core.project import (
    MARKDOWN_LINK_PATTERN,
    WIKILINK_PATTERN,
    SantaiProject,
    get_directory_stats,
    get_file_graph,
    get_history_entries,
    get_notes,
)
from santai_cli.core.repo_context import build_repo_context, inject_repo_context

# Templates and static directories
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

# Files hidden from all file-tree listings (in addition to dotfiles).
_HIDDEN_FILES: set[str] = {"rumdl.toml"}


class RenameRequest(BaseModel):
    old_path: str
    new_name: str


class MkdirRequest(BaseModel):
    path: str
    name: str


class TouchRequest(BaseModel):
    path: str
    name: str


class FileContentRequest(BaseModel):
    content: str


class MoveRequest(BaseModel):
    source_path: str
    target_folder: str


class ChatRequest(BaseModel):
    messages: list[dict[str, str]]
    provider: str
    model: str
    agent: str | None = None


class SettingsRequest(BaseModel):
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None


def format_size(size_bytes: int | float) -> str:
    """Format bytes as human-readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def format_time_ago(dt: datetime) -> str:
    """Format datetime as relative time (e.g., '2 hours ago')."""
    now = datetime.now()
    diff = now - dt

    seconds = diff.total_seconds()
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    else:
        return dt.strftime("%Y-%m-%d")


def get_file_tree(
    base_path: Path, relative_to: Path | None = None
) -> list[dict[str, Any]]:
    """Build a file tree structure for display."""
    if relative_to is None:
        relative_to = base_path

    tree = []
    if not base_path.is_dir():
        return tree

    for item in sorted(
        base_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())
    ):
        if item.name.startswith(".") or item.name in _HIDDEN_FILES:
            continue

        node: dict[str, Any] = {
            "name": item.name,
            "path": str(item.relative_to(relative_to)),
            "is_dir": item.is_dir(),
        }

        if item.is_dir():
            node["children"] = get_file_tree(item, relative_to)

        tree.append(node)

    return tree


def _update_markdown_links(root_dir: Path, old_abs: Path, new_abs: Path) -> None:
    """Rewrite markdown links across the project after a file/folder move or rename.

    Two cases are handled for every .md file found:
    - Outside the moved item: any link that resolved to old_abs (or inside it) is
      rewritten to point to the equivalent path under new_abs.
    - Inside the moved item: outbound links whose targets didn't move are recomputed
      from the file's new directory, and links whose targets also moved are left alone
      (relative path within the subtree is unchanged).

    Only root-relative wikilinks are rewritten; filename-only wikilinks are left alone
    since they resolve by lookup, not path.
    """

    def _make_replacer(link_base: Path, md_file: Path, file_moved: bool):
        def replacer(match: re.Match) -> str:
            text = match.group(1)
            target = match.group(2)

            if target.startswith(("http://", "https://", "mailto:", "#")):
                return match.group(0)

            fragment = ""
            if "#" in target:
                target, frag = target.split("#", 1)
                fragment = "#" + frag
                if not target:
                    return match.group(0)

            resolved = (link_base / target).resolve()

            if resolved == old_abs:
                new_target_abs = new_abs
            elif resolved.is_relative_to(old_abs):
                new_target_abs = new_abs / resolved.relative_to(old_abs)
            elif file_moved:
                # File moved but this link points outside the moved subtree —
                # recompute the relative path from the new file location.
                new_target_abs = resolved
            else:
                return match.group(0)

            try:
                new_rel = os.path.relpath(new_target_abs, md_file.parent).replace(
                    "\\", "/"
                )
            except ValueError:
                return match.group(0)
            return f"[{text}]({new_rel}{fragment})"

        return replacer

    def _wikilink_replacer(match: re.Match) -> str:
        inner = match.group(1).strip()
        display = match.group(2)
        resolved = (root_dir / inner).resolve()
        if resolved == old_abs:
            new_target = str(new_abs.relative_to(root_dir)).replace("\\", "/")
        elif resolved.is_relative_to(old_abs):
            new_target_abs = new_abs / resolved.relative_to(old_abs)
            new_target = str(new_target_abs.relative_to(root_dir)).replace("\\", "/")
        else:
            return match.group(0)
        return f"[[{new_target}|{display}]]" if display else f"[[{new_target}]]"

    for md_file in root_dir.rglob("*.md"):
        if not md_file.is_file():
            continue

        # Work out where this file's links were authored from.
        # If the file was inside the moved subtree its links were written relative
        # to its OLD location; we need to resolve them from there.
        if md_file == new_abs or (new_abs.is_dir() and md_file.is_relative_to(new_abs)):
            suffix = md_file.relative_to(new_abs) if new_abs.is_dir() else Path(".")
            link_base = (old_abs / suffix).parent
            file_moved = True
        else:
            link_base = md_file.parent
            file_moved = False

        try:
            content = md_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        if old_abs.name not in content:
            continue

        new_content = MARKDOWN_LINK_PATTERN.sub(
            _make_replacer(link_base, md_file, file_moved), content
        )
        new_content = WIKILINK_PATTERN.sub(_wikilink_replacer, new_content)

        if new_content != content:
            try:
                md_file.write_text(new_content, encoding="utf-8")
            except OSError as exc:
                logging.warning("Failed to update links in %s: %s", md_file, exc)


def create_app(project: SantaiProject) -> FastAPI:
    """Create and configure the FastAPI application."""
    startup_token = str(uuid.uuid4())
    app = FastAPI(title=f"Santai - {project.name}")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    # Add custom filters to Jinja2
    templates.env.filters["format_size"] = format_size
    templates.env.filters["format_time_ago"] = format_time_ago

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        """Render the main dashboard page."""
        stats = get_directory_stats(project)
        history = get_history_entries(project)
        notes = get_notes(project)

        # Build file trees for each directory
        file_tree = [
            {
                "name": "resources",
                "path": "resources",
                "is_dir": True,
                "children": get_file_tree(project.resources_path, project.root),
            },
            {
                "name": "codebases",
                "path": "codebases",
                "is_dir": True,
                "children": get_file_tree(project.codebases_path, project.root),
            },
            {
                "name": "history",
                "path": "history",
                "is_dir": True,
                "children": get_file_tree(project.history_path, project.root),
            },
            {
                "name": "notes",
                "path": "notes",
                "is_dir": True,
                "children": get_file_tree(project.notes_path, project.root),
            },
            {
                "name": "wiki",
                "path": "wiki",
                "is_dir": True,
                "children": get_file_tree(project.wiki_path, project.root),
            },
        ]

        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "project_name": project.name,
                "stats": stats,
                "history": history[:5],  # Show last 5 history entries
                "notes": notes[:5],  # Show last 5 notes
                "file_tree": file_tree,
                "startup_token": startup_token,
            },
        )

    @app.get("/api/stats")
    async def api_stats() -> dict[str, Any]:
        """Return project statistics as JSON."""
        stats = get_directory_stats(project)
        return {
            "resources_count": stats.resources_count,
            "codebases_count": stats.codebases_count,
            "history_count": stats.history_count,
            "notes_count": stats.notes_count,
            "wiki_count": stats.wiki_count,
            "total_size_bytes": stats.total_size_bytes,
            "total_size_formatted": format_size(stats.total_size_bytes),
            "file_types": stats.file_types,
            "recent_files": [
                {
                    "name": f.name,
                    "path": str(f.path.relative_to(project.root))
                    if f.path.is_relative_to(project.root)
                    else str(f.path),
                    "size": f.size_bytes,
                    "modified": f.modified_at.isoformat(),
                    "modified_ago": format_time_ago(f.modified_at),
                    "type": f.file_type,
                }
                for f in stats.recent_files
            ],
        }

    @app.get("/api/history")
    async def api_history() -> list[dict[str, Any]]:
        """Return history entries as JSON."""
        entries = get_history_entries(project)
        return [
            {
                "date": entry.date.isoformat(),
                "title": entry.title,
                "content": entry.content,
                "filename": entry.filename,
            }
            for entry in entries
        ]

    @app.get("/api/notes")
    async def api_notes() -> list[dict[str, Any]]:
        """Return notes as JSON."""
        entries = get_notes(project)
        return [
            {
                "title": note.title,
                "preview": note.preview,
                "content": note.content,
                "filename": note.filename,
                "modified": note.modified_at.isoformat(),
                "modified_ago": format_time_ago(note.modified_at),
                "size": note.size_bytes,
            }
            for note in entries
        ]

    @app.get("/api/graph")
    async def api_graph() -> dict[str, Any]:
        """Return file graph data for visualization."""
        graph = get_file_graph(project)
        return {
            "nodes": [
                {
                    "id": node.id,
                    "name": node.name,
                    "directory": node.directory,
                    "file_type": node.file_type,
                    "size": node.size_bytes,
                }
                for node in graph.nodes
            ],
            "edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "link_text": edge.link_text,
                    "edge_type": edge.edge_type,
                }
                for edge in graph.edges
            ],
        }

    # File browser helpers
    root_dir = project.root.resolve()

    def safe_path(path: str) -> Path:
        """Validate and resolve path, ensuring it stays within root_dir."""
        if not path:
            return root_dir
        resolved = (root_dir / path).resolve()
        try:
            resolved.relative_to(root_dir)
        except ValueError:
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside root directory",
            ) from None
        return resolved

    def get_file_info(path: Path) -> dict[str, Any]:
        """Get file/directory information."""
        stat = path.stat()
        return {
            "name": path.name,
            "path": str(path.relative_to(root_dir)),
            "is_dir": path.is_dir(),
            "size": stat.st_size,
            "size_formatted": format_size(stat.st_size) if not path.is_dir() else "",
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "extension": path.suffix.lower() if path.suffix else "",
        }

    @app.get("/api/files")
    async def list_files(path: str = Query(default="")) -> dict[str, Any]:
        """List files and directories in the given path."""
        target = safe_path(path)
        if not target.exists():
            raise HTTPException(status_code=404, detail="Path not found")
        if not target.is_dir():
            raise HTTPException(status_code=400, detail="Path is not a directory")

        items = []
        for item in sorted(
            target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())
        ):
            if item.name.startswith(".") or item.name in _HIDDEN_FILES:
                continue
            try:
                items.append(get_file_info(item))
            except (OSError, PermissionError):
                continue

        breadcrumbs = [{"name": root_dir.name, "path": ""}]
        if path:
            parts = Path(path).parts
            for i, part in enumerate(parts):
                breadcrumbs.append({"name": part, "path": str(Path(*parts[: i + 1]))})

        return {"path": path, "items": items, "breadcrumbs": breadcrumbs}

    @app.post("/api/files")
    async def upload_file(
        file: UploadFile,
        path: str = Query(default=""),
        relative_path: str = Query(default=""),
    ) -> dict[str, str]:
        """Upload a file to the given path.

        When relative_path is provided (folder upload), the full relative path
        within the folder is preserved and parent directories are created.
        """
        target_dir = safe_path(path)
        if not target_dir.is_dir():
            raise HTTPException(
                status_code=400, detail="Target path is not a directory"
            )

        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        if relative_path:
            file_path = target_dir / relative_path
            # Validate the resolved path is within the project root
            safe_path(str(file_path.relative_to(root_dir)))
            file_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            file_path = target_dir / file.filename
            if file_path.exists():
                raise HTTPException(status_code=409, detail="File already exists")
            safe_path(str(file_path.relative_to(root_dir)))

        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        return {
            "message": "File uploaded successfully",
            "path": str(file_path.relative_to(root_dir)),
        }

    @app.delete("/api/files")
    async def delete_file(path: str = Query(...)) -> dict[str, str]:
        """Delete a file or directory."""
        target = safe_path(path)
        if not target.exists():
            raise HTTPException(status_code=404, detail="Path not found")
        if target == root_dir:
            raise HTTPException(status_code=403, detail="Cannot delete root directory")

        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

        return {"message": "Deleted successfully"}

    @app.post("/api/files/rename")
    async def rename_file(req: RenameRequest) -> dict[str, str]:
        """Rename a file or directory."""
        target = safe_path(req.old_path)
        if not target.exists():
            raise HTTPException(status_code=404, detail="Path not found")

        new_path = target.parent / req.new_name
        safe_path(str(new_path.relative_to(root_dir)))
        if new_path.exists():
            raise HTTPException(
                status_code=409, detail="A file with that name already exists"
            )

        old_abs = target.resolve()
        target.rename(new_path)
        _update_markdown_links(root_dir, old_abs, new_path.resolve())
        return {
            "message": "Renamed successfully",
            "path": str(new_path.relative_to(root_dir)),
        }

    @app.post("/api/files/mkdir")
    async def make_directory(req: MkdirRequest) -> dict[str, str]:
        """Create a new directory."""
        parent = safe_path(req.path)
        if not parent.is_dir():
            raise HTTPException(
                status_code=400, detail="Parent path is not a directory"
            )

        new_dir = parent / req.name
        safe_path(str(new_dir.relative_to(root_dir)))
        if new_dir.exists():
            raise HTTPException(status_code=409, detail="Directory already exists")

        new_dir.mkdir()
        return {
            "message": "Directory created",
            "path": str(new_dir.relative_to(root_dir)),
        }

    @app.post("/api/files/touch")
    async def touch_file(req: TouchRequest) -> dict[str, str]:
        """Create a new empty file."""
        parent = safe_path(req.path)
        if not parent.is_dir():
            raise HTTPException(
                status_code=400, detail="Parent path is not a directory"
            )

        new_file = parent / req.name
        safe_path(str(new_file.relative_to(root_dir)))
        if new_file.exists():
            raise HTTPException(
                status_code=409, detail="A file with that name already exists"
            )

        new_file.touch()
        return {
            "message": "File created",
            "path": str(new_file.relative_to(root_dir)),
        }

    @app.post("/api/files/move")
    async def move_file(req: MoveRequest) -> dict[str, str]:
        """Move a file or directory to a new location."""
        source = safe_path(req.source_path)
        target_dir = safe_path(req.target_folder)

        if not source.exists():
            raise HTTPException(status_code=404, detail="Source not found")
        if not target_dir.is_dir():
            raise HTTPException(status_code=400, detail="Target must be a directory")

        new_path = target_dir / source.name
        if new_path.exists():
            raise HTTPException(
                status_code=409,
                detail="A file with that name already exists in the target folder",
            )

        # Prevent moving a folder into itself
        if source.is_dir():
            try:
                target_dir.relative_to(source)
                raise HTTPException(
                    status_code=400, detail="Cannot move a folder into itself"
                )
            except ValueError:
                pass  # Not a subdirectory, OK to proceed

        shutil.move(str(source), str(new_path))
        _update_markdown_links(root_dir, source, new_path)
        return {
            "message": "Moved successfully",
            "path": str(new_path.relative_to(root_dir)),
        }

    @app.get("/api/files/tree")
    async def api_files_tree(
        path: str = Query(default=""), depth: int = Query(default=10)
    ) -> dict[str, Any]:
        """Get recursive tree structure of files and directories."""
        target = safe_path(path)
        if not target.exists():
            raise HTTPException(status_code=404, detail="Path not found")
        if not target.is_dir():
            raise HTTPException(status_code=400, detail="Path is not a directory")

        def build_tree(dir_path: Path, current_depth: int) -> list[dict[str, Any]]:
            if current_depth <= 0:
                return []
            items = []
            try:
                for item in sorted(
                    dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())
                ):
                    if item.name.startswith(".") or item.name in _HIDDEN_FILES:
                        continue
                    node = {
                        "name": item.name,
                        "path": str(item.relative_to(root_dir)),
                        "is_dir": item.is_dir(),
                    }
                    if item.is_dir():
                        node["children"] = build_tree(item, current_depth - 1)
                    items.append(node)
            except (OSError, PermissionError):
                pass
            return items

        return {
            "name": target.name if path else root_dir.name,
            "path": path,
            "is_dir": True,
            "children": build_tree(target, depth),
        }

    @app.get("/api/files/content")
    async def get_file_content(path: str = Query(...)) -> dict[str, Any]:
        """Get file content for preview."""
        target = safe_path(path)
        if not target.exists():
            raise HTTPException(status_code=404, detail="File not found")
        if target.is_dir():
            raise HTTPException(
                status_code=400, detail="Cannot read directory contents"
            )

        size = target.stat().st_size
        if size > 1024 * 1024:
            return {
                "name": target.name,
                "path": path,
                "size": size,
                "size_formatted": format_size(size),
                "preview": False,
                "message": "File too large to preview",
            }

        text_extensions = {
            ".txt",
            ".md",
            ".py",
            ".js",
            ".ts",
            ".html",
            ".css",
            ".json",
            ".yaml",
            ".yml",
            ".xml",
            ".csv",
            ".log",
            ".sh",
            ".bash",
            ".zsh",
            ".env",
            ".gitignore",
            ".toml",
            ".ini",
            ".cfg",
            ".conf",
            ".jsx",
            ".tsx",
            ".vue",
            ".svelte",
            ".rs",
            ".go",
            ".rb",
            ".php",
            ".java",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".sql",
            ".graphql",
            ".prisma",
        }

        ext = target.suffix.lower()
        is_text = ext in text_extensions or ext == ""

        if is_text:
            try:
                content = target.read_text(encoding="utf-8")
                return {
                    "name": target.name,
                    "path": path,
                    "size": size,
                    "size_formatted": format_size(size),
                    "preview": True,
                    "type": "text",
                    "content": content,
                    "extension": ext,
                }
            except UnicodeDecodeError:
                is_text = False

        image_extensions = {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".svg",
            ".ico",
            ".bmp",
        }
        if ext in image_extensions:
            return {
                "name": target.name,
                "path": path,
                "size": size,
                "size_formatted": format_size(size),
                "preview": True,
                "type": "image",
                "url": f"/api/files/download?path={path}",
            }

        return {
            "name": target.name,
            "path": path,
            "size": size,
            "size_formatted": format_size(size),
            "preview": False,
            "message": "Binary file - cannot preview",
        }

    @app.post("/api/files/save")
    async def save_file_content(
        req: FileContentRequest, path: str = Query(...)
    ) -> dict[str, str]:
        """Save file content."""
        target = safe_path(path)
        if not target.exists():
            raise HTTPException(status_code=404, detail="File not found")
        if target.is_dir():
            raise HTTPException(status_code=400, detail="Cannot write to a directory")

        try:
            target.write_text(req.content, encoding="utf-8")
            return {"message": "File saved successfully"}
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to save file: {e!s}"
            ) from e

    @app.get("/api/files/download")
    async def download_file(path: str = Query(...)) -> FileResponse:
        """Download a file."""
        target = safe_path(path)
        if not target.exists():
            raise HTTPException(status_code=404, detail="File not found")
        if target.is_dir():
            raise HTTPException(status_code=400, detail="Cannot download a directory")

        return FileResponse(target, filename=target.name)

    # === Chat API Endpoints ===

    # Models to never show in the dropdown regardless of what the proxy returns.
    _BLOCKED_MODELS: set[str] = {
        "deepseekr1-bedrock",  # fakes tool calls as plain text
        "llama3.3-bedrock",  # fakes tool calls as plain text
        "llama3.1-bedrock",  # no tool use in streaming mode
        "llama3.2-1B-bedrock",  # no tool use in streaming mode
        "qwen3-coder-bedrock",  # invalid model identifier
        "jamba.2-bedrock",  # deprecated
        "grok2-xai",  # deprecated
    }

    _MODEL_DISPLAY_NAMES: dict[str, str] = {
        # Direct Anthropic models
        "claude-opus-4-7": "Claude Opus 4.7",
        "claude-sonnet-4-6": "Claude Sonnet 4.6",
        "claude-haiku-4-5-20251001": "Claude Haiku 4.5",
        "claude-3-7-sonnet-20250219": "Claude Sonnet 3.7",
        "claude-3-5-sonnet-20241022": "Claude Sonnet 3.5",
        "claude-3-5-haiku-20241022": "Claude Haiku 3.5",
        # Anthropic via direct API
        "anthropic-4.5": "Claude Sonnet 4.5",
        # Anthropic via Bedrock
        "anthropic-claude-bedrock4.5": "Claude Sonnet 4.5",
        "anthropic-claude-bedrock4.6": "Claude Sonnet 4.6",
        "anthropic-claude-bedrock4.6opus": "Claude Opus 4.6",
        "anthropic-claude-bedrock4.7opus": "Claude Opus 4.7",
        "anthropic-claude-bedrock4.5-haiku": "Claude Haiku 4.5",
        "anthropic-claude-opus-4.5-bedrock": "Claude Opus 4.5",
        # These config names are outdated — both point to Sonnet 4.5 in the proxy
        "anthropic-claude-bedrock4.0": "Claude Sonnet 4.5",
        "anthropic-claude-bedrock3.7": "Claude Sonnet 4.5",
        # Amazon
        "us.amazon.nova-pro-v1:0": "Nova Pro",
        "novapro-bedrock": "Nova Pro",
        # xAI Grok
        "grok3-xai": "Grok 3",
        # Google Gemini
        "gemini-flash-2": "Gemini 2.0 Flash",
        "gemini-3": "Gemini 3 Pro Preview",
        # Moonshot AI
        "Kimi-K2.5": "Kimi K2.5",
        # OpenAI (direct)
        "gpt-4o": "GPT-4o",
        "gpt-4o-mini": "GPT-4o mini",
        "gpt-4.1": "GPT-4.1",
        "gpt-4.1-mini": "GPT-4.1 mini",
        "gpt-4.1-nano": "GPT-4.1 nano",
        "chatgpt-4o-latest": "GPT-4o",
        "o1": "o1",
        "o1-mini": "o1-mini",
        "o1-preview": "o1-preview",
        "o3": "o3",
        "o3-mini": "o3-mini",
        "o4-mini": "o4-mini",
        # OpenAI (via proxy)
        "gpt-5big-santai": "GPT-5",
        "gpt-5.4-santai": "GPT-5.4",
        "gpt-5mini-santai": "GPT-5 Mini",
        "gpt-5.5": "GPT-5.5",
        "gpt-5.5-pro": "GPT-5.5 Pro",
    }

    # Words that should render as uppercase acronyms
    _ACRONYMS = {"gpt", "xai", "ai", "llm", "aws", "us"}
    # Segments to drop entirely (provider noise)
    _NOISE = {"anthropic", "bedrock", "amazon"}

    def _prettify_model_id(model_id: str) -> str:
        """Convert a raw model ID to a human-readable label.

        e.g. 'anthropic-claude-bedrock4.5-haiku'  -> 'Claude Haiku 4.5'
             'claude-3-5-haiku-20241022'           -> 'Claude Haiku 3.5'
             'claude-3-7-sonnet-20250219'          -> 'Claude Sonnet 3.7'
             'gemini-2.5-pro'                      -> 'Gemini 2.5 Pro'
             'llama3.1-70b'                        -> 'Llama 3.1 70b'
             'us.amazon.nova-pro-v1:0'             -> 'Nova Pro'
        """
        # Drop trailing revision suffixes like :0
        model_id = re.sub(r":\d+$", "", model_id)
        # Strip trailing 8-digit release dates (e.g. -20241022, -20250219)
        model_id = re.sub(r"-\d{8}$", "", model_id)
        # Strip trailing YYYY-MM-DD dates (e.g. -2024-11-20)
        model_id = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", model_id)
        # Strip trailing -latest alias
        model_id = re.sub(r"-latest$", "", model_id)

        # Split on hyphens/underscores, then expand dot-namespaced word segments
        # (e.g. 'us.amazon.nova') but keep decimal versions ('2.5') and
        # alpha+version segments ('llama3.1') intact.
        raw_parts: list[str] = []
        for seg in re.split(r"[-_]", model_id):
            if (
                "." in seg
                and not re.match(r"^(v?\d|bedrock)", seg, re.IGNORECASE)
                and not re.search(r"\d\.", seg)  # skip if digit precedes dot (version)
            ):
                raw_parts.extend(seg.split("."))
            else:
                raw_parts.append(seg)

        # Collapse consecutive single-digit numeric tokens into a dotted version.
        # e.g. ['claude', '3', '5', 'haiku'] -> ['claude', '3.5', 'haiku']
        collapsed: list[str] = []
        i = 0
        while i < len(raw_parts):
            if (
                re.fullmatch(r"\d", raw_parts[i])
                and i + 1 < len(raw_parts)
                and re.fullmatch(r"\d+", raw_parts[i + 1])
            ):
                collapsed.append(f"{raw_parts[i]}.{raw_parts[i + 1]}")
                i += 2
            else:
                collapsed.append(raw_parts[i])
                i += 1
        raw_parts = collapsed

        words: list[str] = []
        trailing_versions: list[str] = []
        is_claude = raw_parts and raw_parts[0].lower() == "claude"
        for part in raw_parts:
            if not part:
                continue
            low = part.lower()
            if low in _NOISE:
                continue
            # 'bedrock4.5', 'bedrock4.6opus' → trailing version + optional word suffix
            bm = re.match(r"^bedrock([\d.]+)([a-zA-Z]*)$", part, re.IGNORECASE)
            if bm:
                trailing_versions.append(bm.group(1))
                if bm.group(2):
                    words.append(bm.group(2).capitalize())
                continue
            # Pure version/numeric segment — for Claude IDs push to end so the
            # family word comes first: "Claude Haiku 3.5" not "Claude 3.5 Haiku"
            if re.match(r"^v?\d", low):
                if is_claude:
                    trailing_versions.append(part)
                else:
                    words.append(part)
                continue
            # Alpha prefix glued to version, e.g. 'llama3.1', 'gpt4o'
            am = re.match(r"^([a-zA-Z]+)(\d.*)$", part)
            if am:
                prefix, ver = am.group(1), am.group(2)
                words.append(
                    prefix.upper()
                    if prefix.lower() in _ACRONYMS
                    else prefix.capitalize()
                )
                words.append(ver)
                continue
            if low in _ACRONYMS:
                words.append(part.upper())
            else:
                words.append(part.capitalize())
        return " ".join(words + trailing_versions)

    # Cache provider API clients keyed by api_key so a config change gets a
    # fresh client automatically without re-instantiating on every request.
    _anthropic_clients: dict[str, Any] = {}
    _openai_clients: dict[str, Any] = {}

    # Chat-model prefixes to keep from the OpenAI /v1/models response.
    # Excludes embeddings, TTS, Whisper, DALL-E, legacy completions, etc.
    _OPENAI_CHAT_PREFIXES = (
        "gpt-4",
        "gpt-3.5-turbo",
        "o1",
        "o3",
        "o4",
        "chatgpt-4o",
        "gpt-5",
    )

    @app.get("/api/chat/models")
    async def chat_models() -> dict[str, Any]:
        """Return available AI models based on configured API keys.

        When a provider has a base_url (e.g. a LiteLLM proxy), fetches the
        model list dynamically from the proxy's /v1/models endpoint instead
        of using the hardcoded AVAILABLE_MODELS list.
        """
        import anthropic as _anthropic
        import httpx
        import openai as _openai

        from santai_cli.core.config import load_config

        config = load_config(project.root)
        models: list[dict[str, str | bool]] = []
        # Maps provider_name -> {type, display} for providers that failed.
        provider_errors: dict[str, dict[str, str]] = {}
        for provider_name, provider_config in config.providers.items():

            def _err(kind: str) -> dict[str, str]:
                return {"type": kind, "display": provider_config.name}

            if provider_config.base_url:
                # Fetch model list from LiteLLM proxy
                proxy_models: list[str] = []
                try:
                    base = provider_config.base_url.rstrip("/")
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.get(
                            f"{base}/v1/models",
                            headers={
                                "Authorization": f"Bearer {provider_config.api_key}"
                            },
                        )
                        resp.raise_for_status()
                        data = resp.json()
                        proxy_models = [m["id"] for m in data.get("data", [])]
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (401, 403):
                        provider_errors[provider_name] = _err("invalid_key")
                    else:
                        provider_errors[provider_name] = _err("unavailable")
                except Exception:
                    provider_errors[provider_name] = _err("unavailable")
                if not proxy_models and provider_name not in provider_errors:
                    provider_errors[provider_name] = _err("unavailable")
                model_list = proxy_models
            elif provider_name == "anthropic":
                try:
                    if provider_config.api_key not in _anthropic_clients:
                        _anthropic_clients[provider_config.api_key] = (
                            _anthropic.AsyncAnthropic(api_key=provider_config.api_key)
                        )
                    ac = _anthropic_clients[provider_config.api_key]
                    page = await ac.models.list(limit=100)
                    model_list = [m.id for m in page.data]
                except _anthropic.AuthenticationError:
                    model_list = []
                    provider_errors[provider_name] = _err("invalid_key")
                except Exception:
                    model_list = []
                    provider_errors[provider_name] = _err("unavailable")
            elif provider_name == "openai":
                try:
                    if provider_config.api_key not in _openai_clients:
                        _openai_clients[provider_config.api_key] = _openai.AsyncOpenAI(
                            api_key=provider_config.api_key
                        )
                    oc = _openai_clients[provider_config.api_key]
                    page = await oc.models.list()
                    model_list = sorted(
                        [
                            m.id
                            for m in page.data
                            if m.id.startswith(_OPENAI_CHAT_PREFIXES)
                            # Exclude dated snapshots (e.g. gpt-4o-2024-11-20).
                            # These are identical to the base model and clutter
                            # the list; the base ID is always present alongside them.
                            and not re.search(r"-\d{4}-\d{2}-\d{2}$", m.id)
                        ],
                        reverse=True,
                    )
                except _openai.AuthenticationError:
                    model_list = []
                    provider_errors[provider_name] = _err("invalid_key")
                except Exception:
                    model_list = []
                    provider_errors[provider_name] = _err("unavailable")
            else:
                # Unknown provider type (e.g. Bedrock, custom). Use the
                # pre-configured model list from config — this is intentional
                # fallback behaviour, not a sign that the provider is broken.
                model_list = provider_config.available_models

            for model_name in model_list:
                if model_name in _BLOCKED_MODELS:
                    continue
                is_default = model_name == provider_config.model
                models.append(
                    {
                        "provider": provider_name,
                        "provider_display": provider_config.name,
                        "model": model_name,
                        "display": _MODEL_DISPLAY_NAMES.get(model_name)
                        or _prettify_model_id(model_name),
                        "default": is_default,
                    }
                )

        # Deduplicate by display name — keep the first occurrence of each label.
        seen: set[str] = set()
        deduped: list[dict[str, str | bool]] = []
        for m in models:
            if m["display"] not in seen:
                seen.add(m["display"])
                deduped.append(m)
        deduped.sort(key=lambda m: m["display"].lower())
        return {
            "models": deduped,
            "configured": config.has_any_provider,
            "errors": provider_errors,
        }

    @app.get("/api/chat/agents")
    async def chat_agents() -> dict[str, Any]:
        """Return available agent profiles."""
        from santai_cli.core.config import get_agent_profiles

        profiles = get_agent_profiles()
        agents = [{"name": name, "description": desc} for name, desc in profiles]
        return {"agents": agents}

    @app.post("/api/chat")
    async def chat_send(req: ChatRequest) -> StreamingResponse:
        """Stream an AI chat response via Server-Sent Events (SSE).

        Accepts the full conversation history and streams the
        assistant's response back as SSE data events.
        """
        import json

        from santai_cli.core.chat import ChatSession, stream_response
        from santai_cli.core.config import load_agent_prompt, load_config

        config = load_config(project.root)

        if req.provider not in config.providers:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Provider '{req.provider}' not configured. Check your .env file."
                ),
            )

        provider_config = config.providers[req.provider]

        # Build session from message history
        system_prompt = None
        if req.agent:
            system_prompt = load_agent_prompt(req.agent)

        # Inject repository context
        repo_context = build_repo_context(project)
        system_prompt = inject_repo_context(system_prompt, repo_context)

        session = ChatSession(system_prompt=system_prompt, project_root=project.root)
        for msg in req.messages:
            if msg.get("role") == "user":
                session.add_user_message(msg.get("content", ""))
            elif msg.get("role") == "assistant":
                session.add_assistant_message(msg.get("content", ""))

        async def event_generator():
            """Generate SSE events from the streaming response."""
            try:
                async for chunk in stream_response(
                    session, req.provider, provider_config, req.model
                ):
                    if isinstance(chunk, dict):
                        evt = chunk.get("event", "")
                        if evt == "file_written":
                            data = json.dumps(
                                {"type": "file_written", "path": chunk["path"]}
                            )
                        elif evt == "tool_call":
                            data = json.dumps(
                                {"type": "tool_call", "name": chunk["name"]}
                            )
                        else:
                            continue
                    else:
                        data = json.dumps({"type": "chunk", "content": chunk})
                    yield f"data: {data}\n\n"
                # Send done event
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
            except Exception as e:
                error_data = json.dumps({"type": "error", "content": str(e)})
                yield f"data: {error_data}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/api/settings")
    async def get_settings() -> dict[str, Any]:
        """Return current API key configuration status (keys masked)."""
        import os

        from dotenv import dotenv_values

        env_path = project.root / ".env"
        stored = dotenv_values(env_path) if env_path.is_file() else {}

        def masked(key: str) -> str | None:
            val = stored.get(key) or os.environ.get(key, "")
            if not val or val.startswith("your-"):
                return None
            return val[:8] + "..." + val[-4:] if len(val) > 12 else "****"

        return {
            "anthropic": {
                "configured": bool(
                    (
                        stored.get("ANTHROPIC_API_KEY")
                        or os.environ.get("ANTHROPIC_API_KEY", "")
                    )
                    and not (stored.get("ANTHROPIC_API_KEY", "") or "").startswith(
                        "your-"
                    )
                ),
                "key_preview": masked("ANTHROPIC_API_KEY"),
            },
            "openai": {
                "configured": bool(
                    (
                        stored.get("OPENAI_API_KEY")
                        or os.environ.get("OPENAI_API_KEY", "")
                    )
                    and not (stored.get("OPENAI_API_KEY", "") or "").startswith("your-")
                ),
                "key_preview": masked("OPENAI_API_KEY"),
            },
        }

    @app.post("/api/settings")
    async def save_settings(req: SettingsRequest) -> dict[str, str]:
        """Save API keys to the project .env file."""

        from dotenv import dotenv_values, load_dotenv

        env_path = project.root / ".env"

        # Read existing values
        existing: dict[str, str] = {}
        if env_path.is_file():
            existing = dict(dotenv_values(env_path))

        # Update with new values (empty string = leave unchanged)
        if req.anthropic_api_key is not None and req.anthropic_api_key.strip():
            existing["ANTHROPIC_API_KEY"] = req.anthropic_api_key.strip()
        if req.openai_api_key is not None and req.openai_api_key.strip():
            existing["OPENAI_API_KEY"] = req.openai_api_key.strip()

        # Write .env file — quote all values so special chars are preserved
        lines = [f'{k}="{v}"\n' for k, v in existing.items()]
        # Atomic write: create temp file with restricted permissions, then
        # rename into place so .env is never world-readable even briefly.
        fd, tmp = tempfile.mkstemp(dir=env_path.parent)
        try:
            with os.fdopen(fd, "w") as f:
                f.write("".join(lines))
            os.chmod(tmp, 0o600)
            os.replace(tmp, env_path)
        except Exception:
            os.unlink(tmp)
            raise

        # Reload into the running process immediately
        load_dotenv(env_path, override=True)

        return {"status": "saved"}

    return app
