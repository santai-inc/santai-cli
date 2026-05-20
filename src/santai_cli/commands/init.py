"""Initialize a new Santai project."""

import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()

AGENTS_MD_CONTENT = """\
# Santai Project

This directory is managed by Santai.

## Directory Structure

- **media/** - Reference materials including markdown files, PDFs, images, and other documents
- **history/** - Markdown documentation of major changes and decisions (supplements git history)
- **notes/** - General notes, scratch space, and quick thoughts

## Pre-commit Hooks

This project uses [prek](https://prek.j178.dev/) to run [rumdl](https://github.com/rvben/rumdl) for markdown linting.

## History Convention

The `history/` directory contains markdown files documenting significant changes:

- Use filenames in format: `YYYY-MM-DD-brief-description.md`
- Document the what, why, and any alternatives considered
- Git tracks the granular changes; history/ captures the narrative

## Notes Convention

The `notes/` directory is for general notes and scratch space:

- Use `.md` or `.txt` files
- Name files descriptively (e.g., `meeting-notes.md`, `ideas.txt`)
- Notes are displayed with previews in the dashboard
"""

README_MD_TEMPLATE = """\
# {project_name}

See [AGENTS.md](AGENTS.md) for project structure and conventions.
"""

CLAUDE_MD_CONTENT = """\
See [AGENTS.md](AGENTS.md) for project structure and conventions.
"""

PRE_COMMIT_CONFIG_CONTENT = """\
repos:
  - repo: https://github.com/rvben/rumdl-pre-commit
    rev: v0.1.68
    hooks:
      - id: rumdl-fmt
"""

RUMDL_TOML_CONTENT = """\
[global]
include = ["**/*.md"]
"""

ENV_EXAMPLE_CONTENT = """\
# Santai CLI - AI Chatbot Configuration
# Copy this file to .env and fill in your API keys.
# At least one provider key is required for `santai chat` to work.
#
# Just drop in your API key(s) below — no other configuration is needed
# to get started with the standard Anthropic or OpenAI endpoints.

# --- Anthropic ---
ANTHROPIC_API_KEY=your-anthropic-api-key-here
# ANTHROPIC_MODEL=claude-sonnet-4-20250514

# --- OpenAI ---
OPENAI_API_KEY=your-openai-api-key-here
# OPENAI_MODEL=gpt-4o
# Optional: only set this if you use a custom proxy (e.g. LiteLLM, Azure).
# If omitted, the standard OpenAI endpoint (https://api.openai.com/v1) is used.
# OPENAI_API_BASE_URL=https://your-proxy-url.example.com/v1
"""

GITIGNORE_CONTENT = """\
# Environment secrets
.env
"""


def _is_directory_empty(path: Path) -> bool:
    """Check if directory is completely empty (no files, no .git)."""
    if not path.exists():
        return True
    if not path.is_dir():
        return False
    # Check for any contents including hidden files
    contents = list(path.iterdir())
    return len(contents) == 0


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


def init(
    name: Annotated[
        str,
        typer.Argument(
            help="Directory name to create and initialize (use '.' for current directory)"
        ),
    ] = ".",
) -> None:
    """Initialize a new Santai project.

    Creates a new directory (or uses current directory) with:
    - Git repository
    - media/, history/, notes/ folders
    - AGENTS.md, README.md, CLAUDE.md
    - Pre-commit hooks with rumdl for markdown linting (using prek)
    """
    # Determine target path
    if name == ".":
        target_path = Path.cwd()
        project_name = target_path.name
    else:
        target_path = Path.cwd() / name
        project_name = name

    # Check if we need to create the directory
    if name != ".":
        if target_path.exists():
            if not _is_directory_empty(target_path):
                console.print(
                    f"[red]Error: Directory '{name}' already exists and is not empty.[/red]"
                )
                raise typer.Exit(1)
        else:
            target_path.mkdir(parents=True)
            console.print(f"Created directory: {name}")
    else:
        # Check current directory is empty
        if not _is_directory_empty(target_path):
            console.print(
                "[red]Error: Current directory is not empty. "
                "Please use an empty directory or specify a new directory name.[/red]"
            )
            raise typer.Exit(1)

    # Initialize git
    console.print("Initializing git repository...")
    if not _run_command(["git", "init"], cwd=target_path):
        console.print("[red]Failed to initialize git repository.[/red]")
        raise typer.Exit(1)

    # Create directories
    console.print("Creating directory structure...")
    for dir_name in ["media", "history", "notes"]:
        (target_path / dir_name).mkdir(exist_ok=True)
        # Add .gitkeep to keep empty directories in git
        (target_path / dir_name / ".gitkeep").touch()

    # Write AGENTS.md
    console.print("Creating AGENTS.md...")
    (target_path / "AGENTS.md").write_text(AGENTS_MD_CONTENT, encoding="utf-8")

    # Write README.md with dynamic project name
    console.print("Creating README.md...")
    readme_content = README_MD_TEMPLATE.format(project_name=project_name)
    (target_path / "README.md").write_text(readme_content, encoding="utf-8")

    # Write CLAUDE.md
    console.print("Creating CLAUDE.md...")
    (target_path / "CLAUDE.md").write_text(CLAUDE_MD_CONTENT, encoding="utf-8")

    # Write .pre-commit-config.yaml
    console.print("Creating .pre-commit-config.yaml...")
    (target_path / ".pre-commit-config.yaml").write_text(
        PRE_COMMIT_CONFIG_CONTENT, encoding="utf-8"
    )

    # Write rumdl.toml
    console.print("Creating rumdl.toml...")
    (target_path / "rumdl.toml").write_text(RUMDL_TOML_CONTENT, encoding="utf-8")

    # Write .env.example
    console.print("Creating .env.example...")
    (target_path / ".env.example").write_text(ENV_EXAMPLE_CONTENT, encoding="utf-8")

    # Write .gitignore
    console.print("Creating .gitignore...")
    (target_path / ".gitignore").write_text(GITIGNORE_CONTENT, encoding="utf-8")

    # Install prek hooks
    console.print("Installing prek hooks...")
    if not _run_command(["prek", "install"], cwd=target_path):
        console.print(
            "[yellow]Warning: Could not install prek hooks. "
            "Make sure prek is installed (see https://prek.j178.dev/installation/) "
            "and run 'prek install' manually.[/yellow]"
        )

    # Success message
    console.print()
    console.print(
        f"[green]Successfully initialized Santai project: {project_name}[/green]"
    )
    console.print()
    console.print("Project structure:")
    console.print(f"  {project_name}/")
    console.print("  ├── .git/")
    console.print("  ├── .gitignore")
    console.print("  ├── .env.example")
    console.print("  ├── .pre-commit-config.yaml")
    console.print("  ├── rumdl.toml")
    console.print("  ├── AGENTS.md")
    console.print("  ├── README.md")
    console.print("  ├── CLAUDE.md")
    console.print("  ├── media/")
    console.print("  ├── history/")
    console.print("  └── notes/")
    console.print()
    console.print("Next steps:")
    console.print(f"  cd {project_name}" if name != "." else "")
    console.print("  santai ui      # Launch TUI dashboard")
    console.print("  santai web     # Launch web dashboard")
    console.print("  santai chat    # Chat with AI models")
