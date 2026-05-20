"""Merge two Santai projects into a new combined project."""

import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()

# Directories to exclude when copying/merging
IGNORED_DIRECTORIES = {
    ".git",
    ".ruff_cache",
    ".rumdl_cache",
    "__pycache__",
    ".venv",
}

# Files excluded by default (secrets, credentials).
# Users can opt-in to include .env via --include-env.
SENSITIVE_FILES = {
    ".env",
    "credentials.json",
}


def _make_ignore_fn(
    ignored_files: set[str],
) -> Callable[[str, list[str]], set[str]]:
    """Return an ignore function for shutil.copytree."""

    def _ignore(directory: str, files: list[str]) -> set[str]:
        return {f for f in files if f in IGNORED_DIRECTORIES or f in ignored_files}

    return _ignore


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


def _merge_tree(
    source: Path, destination: Path, ignored_files: set[str]
) -> tuple[int, int]:
    """Merge files from source into destination, skipping existing files.

    Walks the source directory tree, copying files into the corresponding
    location in destination. Files that already exist in destination are
    skipped (destination's version is kept).

    Returns:
        A tuple of (copied_count, skipped_count).
    """
    copied = 0
    skipped = 0

    for dirpath, dirnames, filenames in os.walk(source):
        # Filter out ignored directories in-place so os.walk doesn't descend
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRECTORIES]

        rel_dir = Path(dirpath).relative_to(source)
        dest_dir = destination / rel_dir

        # Ensure the directory exists in the destination
        dest_dir.mkdir(parents=True, exist_ok=True)

        for filename in filenames:
            if filename in ignored_files:
                skipped += 1
                continue
            src_file = Path(dirpath) / filename
            dest_file = dest_dir / filename

            if dest_file.exists():
                skipped += 1
            else:
                shutil.copy2(src_file, dest_file)
                copied += 1

    return copied, skipped


def _validate_source(path_str: str) -> Path:
    """Resolve and validate that *path_str* points to an existing directory.

    Returns the resolved Path on success, or raises typer.Exit on failure.
    """
    source_path = Path.cwd() if path_str == "." else Path(path_str).resolve()

    if not source_path.exists():
        console.print(f"[red]Error: Source path '{path_str}' does not exist.[/red]")
        raise typer.Exit(1)

    if not source_path.is_dir():
        console.print(f"[red]Error: Source path '{path_str}' is not a directory.[/red]")
        raise typer.Exit(1)

    return source_path


def merge(
    source1: Annotated[
        str,
        typer.Argument(
            help="Primary Santai project — its files take precedence on conflicts"
        ),
    ],
    source2: Annotated[
        str,
        typer.Argument(help="Secondary Santai project to merge in"),
    ],
    destination: Annotated[
        str,
        typer.Argument(help="Destination directory name for the merged project"),
    ],
    include_env: Annotated[
        bool,
        typer.Option(
            "--include-env",
            help="Include .env files in the merge (may contain API keys)",
        ),
    ] = False,
) -> None:
    """Merge two Santai projects into a new combined project.

    Creates a new Santai project at the destination that contains the combined
    contents of both source projects. When both projects have a file at the
    same relative path, the primary project's version is kept.

    This allows you to combine two knowledge bases into one.
    """
    # Validate both sources
    source1_path = _validate_source(source1)
    source2_path = _validate_source(source2)

    # Resolve destination path
    dest_path = (Path.cwd() / destination).resolve()

    # Check destination doesn't already exist
    if dest_path.exists():
        console.print(f"[red]Error: Destination '{destination}' already exists.[/red]")
        raise typer.Exit(1)

    project_name = dest_path.name

    # Determine which files to exclude
    ignored_files = set(SENSITIVE_FILES)
    has_env = (source1_path / ".env").is_file() or (source2_path / ".env").is_file()
    if not include_env and has_env:
        include_env = typer.confirm(
            "A .env file was found in one or both source projects "
            "(may contain API keys). Include it in the merge?",
            default=False,
        )
    if include_env:
        ignored_files.discard(".env")

    # Step 1: Copy primary project to destination
    console.print(
        f"Merging Santai projects into '{destination}'...",
    )
    console.print(
        f"Copying primary project from '{source1}' "
        "(excluding .git and cache directories)...",
    )

    try:
        shutil.copytree(source1_path, dest_path, ignore=_make_ignore_fn(ignored_files))
    except Exception as e:
        console.print(f"[red]Error copying primary project: {e}[/red]")
        raise typer.Exit(1) from e

    # Step 2: Merge secondary project into destination
    console.print(f"Merging files from secondary project '{source2}'...")

    try:
        copied, skipped = _merge_tree(source2_path, dest_path, ignored_files)
    except Exception as e:
        console.print(f"[red]Error merging secondary project: {e}[/red]")
        raise typer.Exit(1) from e

    # Step 3: Initialize fresh git repository
    console.print("Initializing fresh git repository...")
    if not _run_command(["git", "init"], cwd=dest_path):
        console.print("[red]Failed to initialize git repository.[/red]")
        raise typer.Exit(1)

    # Step 4: Install prek hooks
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
        f"[green]Successfully merged Santai projects into: {project_name}[/green]"
    )
    console.print()

    # Merge summary
    console.print("Merge summary:")
    console.print(f"  Files from primary project ('{source1}'): copied in full")
    console.print(f"  Files merged from secondary project ('{source2}'): {copied}")
    if skipped > 0:
        console.print(
            f"  [yellow]Conflicting files skipped (kept primary): {skipped}[/yellow]"
        )
    console.print()

    console.print("Next steps:")
    console.print(f"  cd {project_name}")
    console.print("  santai ui      # Launch TUI dashboard")
    console.print("  santai web     # Launch web dashboard")
