"""Launch the TUI dashboard."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from santai_cli.core.project import get_project
from santai_cli.tui.app import SantaiApp
from santai_cli.tui.themes import ThemeManager

console = Console()


def ui(
    theme: Annotated[
        str,
        typer.Option("--theme", "-t", help="Theme: claude, catppuccin, btop, light"),
    ] = "btop",
) -> None:
    """Launch the TUI dashboard.

    Displays a terminal-based user interface with:
    - Directory tree showing media/, history/, notes/
    - Dashboard with file statistics, types, and recent files

    Press 'q' to quit, 'r' to refresh, 't' to see theme options.
    """
    # Set theme
    ThemeManager.set_theme(theme)

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
