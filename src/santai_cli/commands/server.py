"""Launch the headless API server."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from rich.console import Console

from santai_cli.core.project import get_project
from santai_cli.server.app import create_server_app

console = Console()


def server(
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Host to bind the server to"),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to run the server on"),
    ] = 8080,
    token: Annotated[
        str | None,
        typer.Option("--token", "-t", help="Bearer token for API authentication"),
    ] = None,
) -> None:
    """Launch the headless API server.

    Starts a JSON-only API server for programmatic access to Santai
    project operations. OpenAPI docs available at /docs.
    Press Ctrl+C to stop the server.
    """
    project = get_project(Path.cwd())
    if project is None:
        console.print(
            "[red]Error: Not a Santai project. "
            "Run 'santai init' to initialize a project.[/red]"
        )
        raise typer.Exit(1)

    app = create_server_app(project, token=token)

    console.print(f"[green]Starting Santai API server for: {project.name}[/green]")
    console.print(f"[blue]Server running at: http://{host}:{port}[/blue]")
    console.print(f"[blue]API docs at: http://{host}:{port}/docs[/blue]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    console.print()

    uvicorn.run(app, host=host, port=port, log_level="info")
