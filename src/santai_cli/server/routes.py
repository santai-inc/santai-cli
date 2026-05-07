"""API route definitions for Santai project operations."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from santai_cli.core.project import SANTAI_DIRS, is_santai_project
from santai_cli.server.models import (
    CherryPickRequest,
    CherryPickResponse,
    CopyRequest,
    CopyResponse,
    InitRequest,
    InitResponse,
    MergeRequest,
    MergeResponse,
)

router = APIRouter(prefix="/api")

# Directories to exclude when copying
_IGNORED_DIRECTORIES = {
    ".git",
    ".ruff_cache",
    ".rumdl_cache",
    "__pycache__",
    ".venv",
}

# Sensitive files excluded by default
_SENSITIVE_FILES = {
    ".env",
    "credentials.json",
}

# Template content for new projects (matches commands/init.py)
_AGENTS_MD_CONTENT = """\
# Santai Project

This directory is managed by Santai.

## Directory Structure

- **resources/** - Reference materials including markdown files, PDFs, images, \
and other documents
- **codebases/** - Code repositories and references
- **history/** - Markdown documentation of major changes and decisions \
(supplements git history)
- **notes/** - General notes, scratch space, and quick thoughts
- **wiki/** - Important context for grounding AI agents and solidifying \
project knowledge
"""

_README_MD_TEMPLATE = """\
# {project_name}

See [AGENTS.md](AGENTS.md) for project structure and conventions.
"""

_GITIGNORE_CONTENT = """\
# Environment secrets
.env
"""


def _resolve_path(path_str: str) -> Path:
    """Resolve a path string to an absolute path."""
    return Path(path_str).expanduser().resolve()


def _validate_santai_project(path: Path, label: str = "Path") -> None:
    """Validate that a path is a valid Santai project.

    Raises HTTPException if validation fails.
    """
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{label} '{path}' does not exist",
        )
    if not path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} '{path}' is not a directory",
        )
    if not is_santai_project(path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{label} '{path}' is not a valid Santai project. "
                "Must contain resources/, codebases/, history/, and notes/ "
                "directories."
            ),
        )


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
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    return True


def _ignore_fn(directory: str, files: list[str]) -> set[str]:
    """Ignore function for shutil.copytree."""
    return {f for f in files if f in _IGNORED_DIRECTORIES or f in _SENSITIVE_FILES}


def _merge_tree(source: Path, destination: Path) -> tuple[int, int]:
    """Merge files from source into destination, skipping conflicts.

    Returns (copied_count, skipped_count).
    """
    copied = 0
    skipped = 0

    for dirpath, dirnames, filenames in os.walk(source):
        dirnames[:] = [d for d in dirnames if d not in _IGNORED_DIRECTORIES]

        rel_dir = Path(dirpath).relative_to(source)
        dest_dir = destination / rel_dir
        dest_dir.mkdir(parents=True, exist_ok=True)

        for filename in filenames:
            if filename in _SENSITIVE_FILES:
                skipped += 1
                continue
            dest_file = dest_dir / filename
            if dest_file.exists():
                skipped += 1
            else:
                src_file = Path(dirpath) / filename
                shutil.copy2(src_file, dest_file)
                copied += 1

    return copied, skipped


# ---------------------------------------------------------------------------
# POST /api/init
# ---------------------------------------------------------------------------


@router.post("/init", response_model=InitResponse)
async def api_init(req: InitRequest) -> InitResponse:
    """Initialize a new Santai project."""
    target = _resolve_path(req.path)
    project_name = req.name or target.name

    # Validate target doesn't already exist as a non-empty directory
    if target.exists():
        if not target.is_dir():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Path '{req.path}' exists and is not a directory",
            )
        if any(target.iterdir()):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Directory '{req.path}' already exists and is not empty",
            )
    else:
        target.mkdir(parents=True)

    # Initialize git
    _run_command(["git", "init"], cwd=target)

    # Create directory structure
    for dir_name in ["resources", "codebases", "history", "notes", "wiki"]:
        (target / dir_name).mkdir(exist_ok=True)
        (target / dir_name / ".gitkeep").touch()

    # Write starter files
    (target / "AGENTS.md").write_text(_AGENTS_MD_CONTENT, encoding="utf-8")
    readme_content = _README_MD_TEMPLATE.format(project_name=project_name)
    (target / "README.md").write_text(readme_content, encoding="utf-8")
    (target / ".gitignore").write_text(_GITIGNORE_CONTENT, encoding="utf-8")

    # Best-effort prek install
    _run_command(["prek", "install"], cwd=target)

    return InitResponse(path=str(target))


# ---------------------------------------------------------------------------
# POST /api/copy
# ---------------------------------------------------------------------------


@router.post("/copy", response_model=CopyResponse)
async def api_copy(req: CopyRequest) -> CopyResponse:
    """Copy a Santai project to a new location."""
    source = _resolve_path(req.source)
    destination = _resolve_path(req.destination)

    _validate_santai_project(source, label="Source")

    if destination.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Destination '{req.destination}' already exists",
        )

    # Copy project files (excluding .git, caches, sensitive files)
    try:
        shutil.copytree(source, destination, ignore=_ignore_fn)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to copy project: {e}",
        ) from e

    # Initialize fresh git repository
    _run_command(["git", "init"], cwd=destination)

    # Best-effort prek install
    _run_command(["prek", "install"], cwd=destination)

    return CopyResponse(destination=str(destination))


# ---------------------------------------------------------------------------
# POST /api/cherry-pick
# ---------------------------------------------------------------------------


def _resolve_cherry_pick_target(source_root: Path, target_arg: str) -> Path | None:
    """Resolve a target argument to a real path inside the source project."""
    # Direct relative path
    candidate = source_root / target_arg
    if candidate.exists():
        return candidate.resolve()

    # Search santai directories for a filename match
    name = Path(target_arg).name
    for dir_name in SANTAI_DIRS:
        dir_path = source_root / dir_name
        if not dir_path.is_dir():
            continue
        for match in dir_path.rglob(name):
            if match.exists():
                return match.resolve()

    return None


def _collect_files(base: Path, target: Path) -> list[Path]:
    """Collect file paths under target, relative to base."""
    if target.is_file():
        return [target.relative_to(base)]

    if not target.is_dir():
        return []

    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(target):
        dirnames[:] = [d for d in dirnames if d not in _IGNORED_DIRECTORIES]
        for fname in filenames:
            full = Path(dirpath) / fname
            files.append(full.relative_to(base))

    files.sort()
    return files


@router.post("/cherry-pick", response_model=CherryPickResponse)
async def api_cherry_pick(req: CherryPickRequest) -> CherryPickResponse:
    """Selectively copy files between Santai projects."""
    source = _resolve_path(req.source)
    destination = _resolve_path(req.destination)

    _validate_santai_project(source, label="Source")
    _validate_santai_project(destination, label="Destination")

    if source == destination:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and destination are the same project",
        )

    if not req.files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files specified",
        )

    # Resolve all file targets
    all_files: list[Path] = []
    not_found: list[str] = []

    for target_arg in req.files:
        resolved = _resolve_cherry_pick_target(source, target_arg)
        if resolved is None:
            not_found.append(target_arg)
            continue
        collected = _collect_files(source, resolved)
        all_files.extend(collected)

    if not_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Files not found in source project: {not_found}",
        )

    if not all_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files matched the given arguments",
        )

    # De-duplicate
    seen: set[Path] = set()
    unique_files: list[Path] = []
    for f in all_files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)

    # Copy files
    copied: list[str] = []
    for rel in unique_files:
        src_file = source / rel
        dest_file = destination / rel

        if dest_file.exists() and not req.overwrite:
            continue

        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest_file)
        copied.append(str(rel))

    return CherryPickResponse(copied=copied)


# ---------------------------------------------------------------------------
# POST /api/merge
# ---------------------------------------------------------------------------


@router.post("/merge", response_model=MergeResponse)
async def api_merge(req: MergeRequest) -> MergeResponse:
    """Merge two Santai projects into a new combined project."""
    primary = _resolve_path(req.primary)
    secondary = _resolve_path(req.secondary)
    output = _resolve_path(req.output)

    _validate_santai_project(primary, label="Primary")
    _validate_santai_project(secondary, label="Secondary")

    if output.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Output path '{req.output}' already exists",
        )

    # Step 1: Copy primary project to output
    try:
        shutil.copytree(primary, output, ignore=_ignore_fn)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to copy primary project: {e}",
        ) from e

    # Step 2: Merge secondary into output (skip conflicts)
    try:
        _merge_tree(secondary, output)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to merge secondary project: {e}",
        ) from e

    # Step 3: Initialize fresh git repository
    _run_command(["git", "init"], cwd=output)

    # Step 4: Best-effort prek install
    _run_command(["prek", "install"], cwd=output)

    return MergeResponse(output=str(output))
