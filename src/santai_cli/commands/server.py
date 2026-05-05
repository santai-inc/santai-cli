"""Launch the headless API server."""

from __future__ import annotations

import os
from typing import Annotated

import typer
import uvicorn
from rich.console import Console

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
        typer.Option(
            "--token",
            "-t",
            help="Bearer token for API authentication "
            "(overrides SANTAI_SERVER_TOKEN env var)",
        ),
    ] = None,
) -> None:
    """Launch the headless API server.

    Starts a JSON-only API server for programmatic access to Santai
    project operations. OpenAPI docs available at /docs.
    Press Ctrl+C to stop the server.
    """
    # Resolve token: CLI flag takes precedence over env var
    resolved_token = token or os.environ.get("SANTAI_SERVER_TOKEN") or None

    app = create_server_app(token=resolved_token, host=host)

    console.print("[green]Starting Santai API server[/green]")
    console.print(f"[blue]Server running at: http://{host}:{port}[/blue]")
    console.print(f"[blue]API docs at: http://{host}:{port}/docs[/blue]")
    if resolved_token:
        console.print("[yellow]Authentication enabled[/yellow]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    console.print()

    uvicorn.run(app, host=host, port=port, log_level="info")
