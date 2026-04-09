"""Display project history entries."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule

from santai_cli.core.project import get_history_entries, get_project

console = Console()


def history(
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-n", help="Show only N most recent entries"),
    ] = None,
    reverse: Annotated[
        bool,
        typer.Option(
            "--reverse", "-r", help="Show oldest first instead of newest first"
        ),
    ] = False,
    no_pager: Annotated[
        bool,
        typer.Option("--no-pager", help="Disable paging output"),
    ] = False,
) -> None:
    """Display project history entries.

    Shows markdown files from the history/ directory that follow the
    YYYY-MM-DD-description.md naming convention.
    """
    # Get project
    project = get_project(Path.cwd())
    if project is None:
        console.print(
            "[red]Error: Not a Santai project. "
            "Run 'santai init' to initialize a project.[/red]"
        )
        raise typer.Exit(1)

    # Get history entries
    entries = get_history_entries(project)

    if not entries:
        console.print("[dim]No history entries found.[/dim]")
        raise typer.Exit(0)

    # Apply reverse if requested (entries are newest-first by default)
    if reverse:
        entries = list(reversed(entries))

    # Apply limit if specified
    if limit is not None:
        entries = entries[:limit]

    # Build output
    def render_output() -> None:
        console.print()
        console.print(
            Panel(
                f"[bold]Santai History - {project.name}[/bold]",
                expand=False,
            )
        )
        console.print()

        for entry in entries:
            # Header with date and title
            date_str = entry.date.strftime("%Y-%m-%d")
            console.print(Rule(f"{date_str} - {entry.title}", style="bold blue"))
            console.print()

            # Render markdown content
            md = Markdown(entry.content)
            console.print(md)
            console.print()

        console.print(Rule(style="dim"))
        console.print(
            f"[dim]{len(entries)} {'entry' if len(entries) == 1 else 'entries'} total[/dim]"
        )
        console.print()

    # Render with or without pager
    if no_pager:
        render_output()
    else:
        with console.pager(styles=True):
            render_output()
