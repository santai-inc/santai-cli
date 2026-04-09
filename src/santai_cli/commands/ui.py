"""Launch the TUI dashboard."""

from pathlib import Path

import typer
from rich.console import Console

from santai_cli.core.project import get_project
from santai_cli.tui.app import SantaiApp

console = Console()


def ui() -> None:
    """Launch the TUI dashboard.

    Displays a terminal-based user interface with:
    - Directory tree showing resources/, codebases/, history/
    - Dashboard with file statistics, types, and recent files

    Press 'q' to quit, 'r' to refresh.
    """
    # Get project
    project = get_project(Path.cwd())
    if project is None:
        console.print(
            "[red]Error: Not a Santai project. "
            "Run 'santai init' to initialize a project.[/red]"
        )
        raise typer.Exit(1)

    # Launch TUI
    app = SantaiApp(project)
    app.run()
