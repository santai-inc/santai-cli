"""Santai CLI application."""

from __future__ import annotations

import click
import typer
import typer.core
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from santai_cli.commands import (
    auth,
    chat,
    cherry_pick,
    copy,
    init,
    merge,
    pull,
    push,
    server,
    ui,
    web,
)


class _VerboseHelpGroup(typer.core.TyperGroup):
    """Custom Click Group that intercepts ``--verbose`` / ``-v`` before
    the eager ``--help`` option fires, enabling ``--help --verbose``
    to display an extended help page.
    """

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        ctx.ensure_object(dict)
        if "--verbose" in args or "-v" in args:
            ctx.obj["verbose"] = True
            args = [a for a in args if a not in ("--verbose", "-v")]
        else:
            ctx.obj["verbose"] = False
        return super().parse_args(ctx, args)

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        if ctx.obj and ctx.obj.get("verbose"):
            _print_verbose_help()
        else:
            super().format_help(ctx, formatter)


# ---------------------------------------------------------------------------
# Typer application
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="santai",
    help="Santai project management CLI",
    cls=_VerboseHelpGroup,
    no_args_is_help=True,
)


@app.callback()
def _main() -> None:
    """Santai project management CLI"""


app.command(name="init")(init.init)
app.command(name="copy")(copy.copy)
app.command(name="cherry-pick")(cherry_pick.cherry_pick)
app.command(name="chat")(chat.chat)
app.command(name="merge")(merge.merge)
app.command(name="ui")(ui.ui)
app.command(name="web")(web.web)
app.command(name="server")(server.server)
app.command(name="push")(push.push)
app.command(name="pull")(pull.pull)
app.command(name="login")(auth.login)
app.command(name="logout")(auth.logout)
app.command(name="whoami")(auth.whoami)


# ---------------------------------------------------------------------------
# Verbose help output
# ---------------------------------------------------------------------------

_VERSION = "0.1.0"

_COMMANDS: list[dict[str, str | list[str]]] = [
    {
        "name": "santai init [NAME]",
        "summary": "Initialize a new Santai project.",
        "detail": (
            "Creates a new directory (or uses the current directory) with a\n"
            "Git repository, the standard folder structure (resources/,\n"
            "codebases/, history/, notes/), starter files (AGENTS.md,\n"
            "README.md, CLAUDE.md), and pre-commit hooks with rumdl for\n"
            "markdown linting via prek."
        ),
        "args": [
            "NAME  Directory name to create and initialize [default: .]",
        ],
    },
    {
        "name": "santai copy SOURCE DESTINATION",
        "summary": "Copy a Santai project to a new location with a fresh git history.",
        "detail": (
            "Creates a complete copy of an existing Santai project while\n"
            "excluding .git, .ruff_cache, .rumdl_cache, __pycache__, and\n"
            ".venv directories. A fresh git repository is initialized in\n"
            "the destination so you can fork a knowledge base and manage\n"
            "it independently."
        ),
        "args": [
            "SOURCE       Source Santai project path (or '.' for current directory)",
            "DESTINATION  Destination directory name for the copy",
        ],
    },
    {
        "name": "santai cherry-pick SOURCE DESTINATION FILES...",
        "summary": "Cherry-pick specific files or folders from one KB into another.",
        "detail": (
            "Selectively copies individual files or entire folders from a\n"
            "source Santai project into a destination project. Unlike 'copy'\n"
            "(which clones everything) or 'merge' (which combines two full\n"
            "projects), cherry-pick lets you move just the pieces you need."
        ),
        "args": [
            "SOURCE       Source Santai project path (or '.' for current directory)",
            "DESTINATION  Destination Santai project path (or '.')",
            "FILES...     One or more files or folders to cherry-pick (relative paths)",
        ],
        "options": [
            "--overwrite   Overwrite existing files without prompting",
            "--skip        Silently skip files that already exist",
            "--dry-run     Show what would be copied without copying",
        ],
    },
    {
        "name": "santai ui",
        "summary": "Launch the TUI dashboard.",
        "detail": (
            "Opens a terminal-based user interface built with Textual.\n"
            "The dashboard includes a directory tree, recent files panel,\n"
            "notes panel, file statistics, and an interactive force-directed\n"
            "graph of file relationships."
        ),
        "options": [
            "--theme, -t TEXT  Theme: claude, catppuccin, btop, light [default: btop]",
        ],
    },
    {
        "name": "santai web",
        "summary": "Launch the web dashboard.",
        "detail": (
            "Starts a local FastAPI web server and opens an interactive\n"
            "dashboard in your browser with a D3.js graph visualization,\n"
            "file browser, notes viewer, and history timeline.\n"
            "Press Ctrl+C to stop the server."
        ),
        "options": [
            "--port, -p INT  Port to run the server on [default: 8000]",
            "--no-open       Don't automatically open the browser",
        ],
    },
]

_KEYBINDINGS: list[tuple[str, str]] = [
    ("q", "Quit"),
    ("r", "Refresh all panels"),
    ("g", "Toggle fullscreen graph"),
    ("/", "Open graph search"),
    ("f", "Open graph filter by directory"),
    ("t", "Open theme selector"),
    ("n", "Add a new note"),
    ("p", "Cycle palette within current theme"),
    ("c", "Clear graph search / filter"),
    ("Esc", "Back / exit fullscreen graph"),
]


def _print_verbose_help() -> None:
    """Render a comprehensive help page using Rich."""
    console = Console()
    console.print()

    # -- Header --------------------------------------------------------
    console.print(
        Panel(
            Text.from_markup(
                f"[bold]Santai CLI[/bold]  v{_VERSION}\n"
                "A CLI tool for managing Santai knowledge-base projects\n"
                "with TUI and web dashboards."
            ),
            border_style="bright_cyan",
            padding=(1, 2),
        )
    )

    # -- Commands (detailed) -------------------------------------------
    console.print("\n[bold underline]Commands[/bold underline]\n")
    for cmd in _COMMANDS:
        console.print(f"  [bold cyan]{cmd['name']}[/bold cyan]")
        console.print(f"  {cmd['summary']}\n")
        detail = cmd.get("detail", "")
        if detail:
            for line in str(detail).split("\n"):
                console.print(f"    {line}")
            console.print()

        args = cmd.get("args")
        if args:
            console.print("    [dim]Arguments:[/dim]")
            for a in args:
                console.print(f"      {a}")
            console.print()

        options = cmd.get("options")
        if options:
            console.print("    [dim]Options:[/dim]")
            for o in options:
                console.print(f"      {o}")
            console.print()

    # -- Quick Start ---------------------------------------------------
    console.print("[bold underline]Quick Start[/bold underline]\n")
    quick_start = [
        ("santai init myproject", "Create a new project"),
        ("cd myproject", ""),
        ("santai ui", "Launch the TUI dashboard"),
        ("santai web", "Launch the web dashboard (http://localhost:8000)"),
        ("santai copy . ../backup", "Copy project with fresh git history"),
        (
            "santai cherry-pick ./src ./dst notes/idea.md",
            "Cherry-pick files between KBs",
        ),
    ]
    for cmd_text, description in quick_start:
        if description:
            console.print(
                f"  [green]$ {cmd_text:<30}[/green] [dim]# {description}[/dim]"
            )
        else:
            console.print(f"  [green]$ {cmd_text}[/green]")
    console.print()

    # -- TUI Keybindings -----------------------------------------------
    console.print("[bold underline]TUI Keybindings[/bold underline]\n")
    kb_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    kb_table.add_column("Key", style="bold yellow", min_width=6)
    kb_table.add_column("Action")
    for key, action in _KEYBINDINGS:
        kb_table.add_row(key, action)
    console.print(kb_table)
    console.print()

    # -- Project Structure ---------------------------------------------
    console.print("[bold underline]Project Structure[/bold underline]\n")
    dirs = [
        ("resources/", "Reference materials and documents"),
        ("codebases/", "Code snippets and repositories"),
        ("history/", "Timeline entries (YYYY-MM-DD-description.md)"),
        ("notes/", "Personal notes and documentation"),
    ]
    for dirname, desc in dirs:
        console.print(f"  [bold]{dirname:<14}[/bold] {desc}")
    console.print()

    # -- Tips ----------------------------------------------------------
    console.print("[bold underline]Tips[/bold underline]\n")
    tips = [
        "TUI themes: claude, catppuccin, btop (default), light",
        "Web dashboard auto-opens your browser at http://localhost:PORT",
        "Use 'santai copy' to fork a knowledge base with a clean git history",
        "Use 'santai cherry-pick' to move specific files between KBs",
        "Run 'santai <command> --help' for detailed help on any command",
    ]
    for tip in tips:
        console.print(f"  [dim]\u2022[/dim] {tip}")
    console.print()


if __name__ == "__main__":
    app()
