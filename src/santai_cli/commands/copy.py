"""Copy an existing Santai project to a new location."""

import shutil
import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from santai_cli.core.project import is_santai_project

console = Console()

# Directories to exclude when copying
IGNORED_DIRECTORIES = {
    ".git",
    ".ruff_cache",
    ".rumdl_cache",
    "__pycache__",
    ".venv",
}


def _ignore_patterns(directory: str, files: list[str]) -> set[str]:
    """Return set of files/directories to ignore during copy."""
    return {f for f in files if f in IGNORED_DIRECTORIES}


def _run_command(cmd: list[str], cwd: Path) -> bool:
    """Run a command and return True if successful."""
    try:
        subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Command failed: {' '.join(cmd)}[/red]")
        if e.stderr:
            console.print(f"[red]{e.stderr}[/red]")
        return False
    except FileNotFoundError:
        console.print(f"[red]Command not found: {cmd[0]}[/red]")
        return False


def copy(
    source: Annotated[
        str,
        typer.Argument(
            help="Source Santai project (path or '.' for current directory)"
        ),
    ],
    destination: Annotated[
        str,
        typer.Argument(help="Destination directory name for the copy"),
    ],
) -> None:
    """Copy a Santai project to a new location with a fresh git history.

    Creates a copy of an existing Santai project, excluding the .git directory,
    and initializes a fresh git repository in the destination.

    This allows you to fork a knowledge base and manage it independently.
    """
    # Resolve source path
    source_path = Path.cwd() if source == "." else Path(source).resolve()

    # Validate source exists
    if not source_path.exists():
        console.print(f"[red]Error: Source path '{source}' does not exist.[/red]")
        raise typer.Exit(1)

    if not source_path.is_dir():
        console.print(f"[red]Error: Source path '{source}' is not a directory.[/red]")
        raise typer.Exit(1)

    # Validate source is a Santai project
    if not is_santai_project(source_path):
        console.print(f"[red]Error: '{source}' is not a valid Santai project.[/red]")
        console.print(
            "[yellow]A Santai project must have resources/, codebases/, history/, "
            "and notes/ directories.[/yellow]"
        )
        raise typer.Exit(1)

    # Resolve destination path
    dest_path = (Path.cwd() / destination).resolve()

    # Check destination doesn't already exist
    if dest_path.exists():
        console.print(f"[red]Error: Destination '{destination}' already exists.[/red]")
        raise typer.Exit(1)

    project_name = dest_path.name

    # Copy files
    console.print(f"Copying Santai project from '{source}' to '{destination}'...")
    console.print("Copying files (excluding .git and cache directories)...")

    try:
        shutil.copytree(source_path, dest_path, ignore=_ignore_patterns)
    except Exception as e:
        console.print(f"[red]Error copying files: {e}[/red]")
        raise typer.Exit(1) from e

    # Initialize fresh git repository
    console.print("Initializing fresh git repository...")
    if not _run_command(["git", "init"], cwd=dest_path):
        console.print("[red]Failed to initialize git repository.[/red]")
        raise typer.Exit(1)

    # Install prek hooks
    console.print("Installing prek hooks...")
    if not _run_command(["prek", "install"], cwd=dest_path):
        console.print(
            "[yellow]Warning: Could not install prek hooks. "
            "Make sure prek is installed (see https://prek.j178.dev/installation/) "
            "and run 'prek install' manually.[/yellow]"
        )

    # Success message
    console.print()
    console.print(
        f"[green]Successfully copied Santai project to: {project_name}[/green]"
    )
    console.print()
    console.print("Project structure:")
    console.print(f"  {project_name}/")
    console.print("  ├── .git/")
    console.print("  ├── .pre-commit-config.yaml")
    console.print("  ├── rumdl.toml")
    console.print("  ├── AGENTS.md")
    console.print("  ├── README.md")
    console.print("  ├── CLAUDE.md")
    console.print("  ├── resources/")
    console.print("  ├── codebases/")
    console.print("  ├── history/")
    console.print("  ├── notes/")
    console.print("  └── wiki/")
    console.print()
    console.print("Next steps:")
    console.print(f"  cd {project_name}")
    console.print("  santai ui      # Launch TUI dashboard")
    console.print("  santai web     # Launch web dashboard")
    console.print("  santai history # View project history")
