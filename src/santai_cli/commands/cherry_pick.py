"""Cherry-pick specific files or folders from one Santai project into another."""

import os
import shutil
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from santai_cli.core.project import SANTAI_DIRS, is_santai_project

console = Console()

# Directories to skip when traversing a cherry-picked folder
IGNORED_DIRECTORIES = {
    ".git",
    ".ruff_cache",
    ".rumdl_cache",
    "__pycache__",
    ".venv",
}


def _validate_project(path_str: str, label: str = "Path") -> Path:
    """Resolve and validate that *path_str* points to a Santai project.

    Returns the resolved ``Path`` on success or raises ``typer.Exit(1)``.
    """
    resolved = Path.cwd() if path_str == "." else Path(path_str).resolve()

    if not resolved.exists():
        console.print(f"[red]Error: {label} '{path_str}' does not exist.[/red]")
        raise typer.Exit(1)

    if not resolved.is_dir():
        console.print(f"[red]Error: {label} '{path_str}' is not a directory.[/red]")
        raise typer.Exit(1)

    if not is_santai_project(resolved):
        console.print(f"[red]Error: '{path_str}' is not a valid Santai project.[/red]")
        console.print(
            "[yellow]A Santai project must have resources/, codebases/, "
            "history/, and notes/ directories.[/yellow]"
        )
        raise typer.Exit(1)

    return resolved


def _collect_files(base: Path, target: Path) -> list[Path]:
    """Return a sorted list of concrete file paths under *target*.

    If *target* is a file it is returned as-is.  If it is a directory,
    all files are collected recursively while skipping ignored directories.
    Every returned path is relative to *base* (the project root).
    """
    if target.is_file():
        return [target.relative_to(base)]

    if not target.is_dir():
        return []

    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(target):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRECTORIES]
        for fname in filenames:
            full = Path(dirpath) / fname
            files.append(full.relative_to(base))

    files.sort()
    return files


def _resolve_target(source_root: Path, target_arg: str) -> Path | None:
    """Resolve *target_arg* to a real path inside *source_root*.

    Accepts:
    - A relative path within the project  (``notes/idea.md``)
    - A bare filename that lives in a Santai directory (``idea.md``)

    Returns ``None`` when no match is found.
    """
    # 1. Direct relative path
    candidate = source_root / target_arg
    if candidate.exists():
        return candidate.resolve()

    # 2. Search santai directories for a filename match
    name = Path(target_arg).name
    for dir_name in SANTAI_DIRS:
        dir_path = source_root / dir_name
        if not dir_path.is_dir():
            continue
        for match in dir_path.rglob(name):
            if match.exists():
                return match.resolve()

    return None


def cherry_pick(
    source: Annotated[
        str,
        typer.Argument(
            help="Source Santai project (path or '.' for current directory)"
        ),
    ],
    destination: Annotated[
        str,
        typer.Argument(help="Destination Santai project (path or '.')"),
    ],
    files: Annotated[
        list[str],
        typer.Argument(
            help=(
                "Files or folders to cherry-pick (relative paths inside the "
                "source project, e.g. notes/idea.md wiki/)"
            ),
        ),
    ],
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite",
            help="Overwrite existing files in the destination without prompting",
        ),
    ] = False,
    skip: Annotated[
        bool,
        typer.Option(
            "--skip",
            help="Silently skip files that already exist in the destination",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Show what would be copied without actually copying",
        ),
    ] = False,
) -> None:
    """Cherry-pick specific files or folders from one Santai project into another.

    Unlike 'copy' (which clones an entire project) or 'merge' (which combines
    two full projects), cherry-pick lets you selectively move individual files
    or folders between knowledge bases.

    Examples:

        santai cherry-pick ./kb-large ./kb-small notes/idea.md

        santai cherry-pick ./research ./writing wiki/ resources/outline.md

        santai cherry-pick . ../other-kb notes/2025-04-01-plan.md --dry-run
    """
    # -- Validate both projects ----------------------------------------
    source_path = _validate_project(source, label="Source")
    dest_path = _validate_project(destination, label="Destination")

    if source_path == dest_path:
        console.print("[red]Error: Source and destination are the same project.[/red]")
        raise typer.Exit(1)

    # -- Resolve every requested target --------------------------------
    all_files: list[Path] = []  # relative to source_path
    not_found: list[str] = []

    for target_arg in files:
        resolved = _resolve_target(source_path, target_arg)
        if resolved is None:
            not_found.append(target_arg)
            continue
        collected = _collect_files(source_path, resolved)
        all_files.extend(collected)

    if not_found:
        for nf in not_found:
            console.print(f"[red]Error: '{nf}' not found in source project.[/red]")
        raise typer.Exit(1)

    if not all_files:
        console.print("[yellow]No files matched the given arguments.[/yellow]")
        raise typer.Exit(0)

    # De-duplicate while preserving order
    seen: set[Path] = set()
    unique_files: list[Path] = []
    for f in all_files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)
    all_files = unique_files

    # -- Dry-run: just print and exit ----------------------------------
    if dry_run:
        console.print(
            f"[bold]Dry run:[/bold] {len(all_files)} file(s) would be copied\n"
        )
        for f in all_files:
            dest_file = dest_path / f
            tag = " [yellow](exists)[/yellow]" if dest_file.exists() else ""
            console.print(f"  {f}{tag}")
        console.print()
        return

    # -- Copy files ----------------------------------------------------
    copied = 0
    skipped = 0
    overwritten = 0

    for rel in all_files:
        src_file = source_path / rel
        dest_file = dest_path / rel

        if dest_file.exists():
            if skip:
                skipped += 1
                continue
            if not overwrite:
                # Interactive prompt
                answer = console.input(
                    f"  '{rel}' already exists in destination. "
                    "Overwrite? [yellow]\\[y/N][/yellow] "
                )
                if answer.strip().lower() not in ("y", "yes"):
                    skipped += 1
                    continue
            overwritten += 1

        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest_file)
        copied += 1

    # -- Summary -------------------------------------------------------
    console.print()

    table = Table(title="Cherry-pick summary", show_header=False, show_edge=False)
    table.add_column(style="bold")
    table.add_column()
    table.add_row("Source", str(source_path))
    table.add_row("Destination", str(dest_path))
    table.add_row("Copied", f"[green]{copied}[/green]")
    if overwritten:
        table.add_row("Overwritten", f"[yellow]{overwritten}[/yellow]")
    if skipped:
        table.add_row("Skipped", f"[yellow]{skipped}[/yellow]")
    console.print(table)
    console.print()

    if copied:
        console.print(f"[green]Successfully cherry-picked {copied} file(s).[/green]")
    else:
        console.print("[yellow]No files were copied.[/yellow]")
