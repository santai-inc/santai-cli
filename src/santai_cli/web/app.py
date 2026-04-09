"""FastAPI web application for Santai."""

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from santai_cli.core.project import (
    SantaiProject,
    get_directory_stats,
    get_file_graph,
    get_history_entries,
    get_notes,
)

# Templates directory
TEMPLATES_DIR = Path(__file__).parent / "templates"


def format_size(size_bytes: int) -> str:
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
            "total_size_bytes": stats.total_size_bytes,
            "total_size_formatted": format_size(stats.total_size_bytes),
            "file_types": stats.file_types,
            "recent_files": [
                {
                    "name": f.name,
                    "path": str(f.path),
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

    return app
