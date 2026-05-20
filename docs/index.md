# Santai CLI

**Santai CLI** is a project management tool designed for organizing knowledge and reference materials into a structured workspace. It provides a terminal UI, a web dashboard, and an AI-powered chat interface to help you manage and navigate your project context.

## What is a Santai Project?

A Santai project is a directory with a defined structure for organizing information:

| Directory | Purpose |
|-----------|---------|
| `media/` | Reference materials — markdown, PDFs, images, documents |
| `history/` | Dated markdown entries documenting major changes and decisions |
| `notes/` | General notes, scratch space, and quick thoughts |

Santai provides tools to create, browse, analyze, and chat about this structure through three interfaces: a CLI, a TUI dashboard, and a web dashboard.

## Features

- **Project scaffolding** — `santai init` creates a complete project structure with git, pre-commit hooks, and markdown linting
- **Project operations** — Copy, merge, and cherry-pick between projects while preserving structure
- **AI chat** — Interactive chat with Anthropic and OpenAI models, with swappable agent profiles for different workflows
- **Cloud sync** — Push and pull projects to Santai Hub for backup and sharing
- **TUI dashboard** — Terminal-based dashboard with file graph visualization, directory stats, notes panel, and theme support
- **Web dashboard** — Browser-based dashboard with the same features plus a streaming chat panel
- **File graph** — Automatic detection and visualization of links between your project files

## Quick Install

```bash
# Install with uv (recommended)
uv tool install santai-cli

# Or install with pip
pip install santai-cli
```

Then create your first project:

```bash
santai init my-project
cd my-project
santai ui
```

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
