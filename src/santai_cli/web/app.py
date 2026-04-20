"""FastAPI web application for Santai."""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from santai_cli.core.project import (
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


class RenameRequest(BaseModel):
    old_path: str
    new_name: str


class MkdirRequest(BaseModel):
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
        if item.name.startswith("."):
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


def create_app(project: SantaiProject) -> FastAPI:
    """Create and configure the FastAPI application."""
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
            if item.name.startswith("."):
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
        file: UploadFile, path: str = Query(default="")
    ) -> dict[str, str]:
        """Upload a file to the given path."""
        target_dir = safe_path(path)
        if not target_dir.is_dir():
            raise HTTPException(
                status_code=400, detail="Target path is not a directory"
            )

        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

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

        target.rename(new_path)
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

    @app.post("/api/files/move")
    async def move_file(req: MoveRequest) -> dict[str, str]:
        """Move a file or directory to a new location."""
        # Protected top-level paths that cannot be moved
        protected_paths = {
            "codebases",
            "history",
            "notes",
            "resources",
            "wiki",
            "AGENTS.md",
            "CLAUDE.md",
            "README.md",
            "rumdl.toml",
        }

        if req.source_path in protected_paths:
            raise HTTPException(
                status_code=403, detail="Cannot move protected files or folders"
            )

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
                    if item.name.startswith("."):
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

    @app.get("/api/chat/models")
    async def chat_models() -> dict[str, Any]:
        """Return available AI models based on configured API keys.

        When a provider has a base_url (e.g. a LiteLLM proxy), fetches the
        model list dynamically from the proxy's /v1/models endpoint instead
        of using the hardcoded AVAILABLE_MODELS list.
        """
        import httpx

        from santai_cli.core.config import load_config

        config = load_config(project.root)
        models: list[dict[str, str | bool]] = []
        for provider_name, provider_config in config.providers.items():
            if provider_config.base_url:
                # Fetch model list from proxy
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
                except Exception:
                    pass
                model_list = proxy_models or [provider_config.model]
            else:
                model_list = provider_config.available_models

            for model_name in model_list:
                is_default = model_name == provider_config.model
                models.append(
                    {
                        "provider": provider_name,
                        "provider_display": provider_config.name,
                        "model": model_name,
                        "default": is_default,
                    }
                )
        return {"models": models, "configured": config.has_any_provider}

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
                        data = json.dumps({"type": "file_written", "path": chunk["path"]})
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

        # Ensure defaults are present
        existing.setdefault("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        existing.setdefault("OPENAI_MODEL", "gpt-4o")

        # Write .env file — quote all values so special chars are preserved
        lines = [f'{k}="{v}"\n' for k, v in existing.items()]
        env_path.write_text("".join(lines), encoding="utf-8")

        # Reload into the running process immediately
        load_dotenv(env_path, override=True)

        return {"status": "saved"}

    return app
