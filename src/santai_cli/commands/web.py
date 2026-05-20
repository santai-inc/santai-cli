"""Launch the web dashboard."""

import threading
import time
import webbrowser
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from rich.console import Console

from santai_cli.core.project import get_project
from santai_cli.web.app import create_app

console = Console()


def web(
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to run the server on"),
    ] = 8000,
    no_open: Annotated[
        bool,
        typer.Option("--no-open", help="Don't automatically open browser"),
    ] = False,
) -> None:
    """Launch the web dashboard.

    Starts a local web server and opens the dashboard in your browser.
    Press Ctrl+C to stop the server.
    """
    # Get project (any directory is treated as a project)
    project = get_project(Path.cwd())
    if project is None:
        console.print("[red]Error: current directory does not exist.[/red]")
        raise typer.Exit(1)

    # Create FastAPI app
    app = create_app(project)

    url = f"http://localhost:{port}"

    # Open browser after a short delay (to let server start)
    if not no_open:

        def open_browser() -> None:
            time.sleep(1)
            webbrowser.open(url)

        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()

    console.print(f"[green]Starting Santai web dashboard for: {project.name}[/green]")
    console.print(f"[blue]Server running at: {url}[/blue]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    console.print()

    # Run server
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
