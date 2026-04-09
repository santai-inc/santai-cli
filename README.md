# Santai CLI

A project management CLI that helps you organize resources, codebases, history, and notes in a structured directory layout — with a terminal UI, web dashboard, and rich CLI tools.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Commands](#commands)
  - [santai init](#santai-init)
  - [santai history](#santai-history)
  - [santai ui](#santai-ui)
  - [santai web](#santai-web)
- [Project Structure](#project-structure)
- [Conventions](#conventions)
  - [History Files](#history-files)
  - [Notes](#notes)
  - [File Linking](#file-linking)
- [Development](#development)
- [Tech Stack](#tech-stack)
- [License](#license)

## Features

- **Project scaffolding** — Initialize a structured project with git, markdown linting, and conventional directories
- **Terminal UI (TUI)** — Interactive dashboard built with [Textual](https://textual.textualize.io/) showing directory tree, file statistics, notes preview, and a file graph
- **Web dashboard** — Browser-based dashboard powered by [FastAPI](https://fastapi.tiangolo.com/) with an interactive [D3.js](https://d3js.org/) file graph visualization
- **History viewer** — Rich-formatted markdown rendering of project history entries in the terminal
- **File graph** — Automatic detection of markdown links (`[text](path)`) and wikilinks (`[[page]]`) to build a backlink graph across your project files

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** (recommended package manager)
- **Git**
- **[prek](https://prek.j178.dev/)** (optional, for pre-commit hook management)

## Installation

### Global install with uv (recommended)

Install `santai` as a globally available command using [`uv tool`](https://docs.astral.sh/uv/concepts/tools/):

```bash
# Clone the repository
git clone https://github.com/santai-inc/santai-cli.git
cd santai-cli

# Install globally (available everywhere as `santai`)
uv tool install --from . santai-cli

# Verify
santai --help
```

This installs the `santai` executable into `~/.local/bin/` with its own isolated Python environment. It's available system-wide — no need to activate a virtualenv.

To **upgrade** after pulling new changes:

```bash
cd santai-cli && git pull
uv tool install --from . --force santai-cli
```

To **uninstall**:

```bash
uv tool uninstall santai-cli
```

### Development install with uv

If you're working on santai-cli itself:

```bash
git clone https://github.com/santai-inc/santai-cli.git
cd santai-cli

# Install in development mode (use `uv run santai` to invoke)
uv sync

# Run the CLI
uv run santai --help
```

### Using pip

```bash
git clone https://github.com/santai-inc/santai-cli.git
cd santai-cli

# Install globally
pip install .

# Or install in development/editable mode
pip install -e .

# Verify
santai --help
```

## Quick Start

```bash
# 1. Create a new Santai project
santai init my-project

# 2. Navigate into the project
cd my-project

# 3. Add a history entry
echo "# Initial Setup\n\nProject initialized." > history/2025-01-15-initial-setup.md

# 4. Add a note
echo "# Ideas\n\nSome brainstorming notes." > notes/ideas.md

# 5. Launch the TUI dashboard
santai ui

# Or launch the web dashboard
santai web
```

## Commands

### `santai init`

Initialize a new Santai project with a complete directory structure.

```bash
# Create a new project in a new directory
santai init my-project

# Initialize in the current (empty) directory
santai init .
```

**What it creates:**

```
my-project/
├── .git/
├── .pre-commit-config.yaml
├── rumdl.toml
├── AGENTS.md
├── README.md
├── CLAUDE.md
├── resources/       # Reference materials (markdown, PDFs, images, docs)
├── codebases/       # Code repositories and references
├── history/         # Dated markdown entries documenting major changes
└── notes/           # General notes and scratch space
```

> **Note:** The target directory must be empty. The command also attempts to install [prek](https://prek.j178.dev/) pre-commit hooks for markdown linting with [rumdl](https://github.com/rvben/rumdl). If prek is not installed, a warning is shown and you can install hooks manually later.

### `santai history`

Display project history entries from the `history/` directory with rich markdown rendering.

```bash
# View all history entries (newest first, with pager)
santai history

# Show only the 5 most recent entries
santai history --limit 5
santai history -n 5

# Show oldest entries first
santai history --reverse
santai history -r

# Disable the pager (print directly to terminal)
santai history --no-pager
```

History entries are markdown files in `history/` following the `YYYY-MM-DD-description.md` naming convention. They are displayed with formatted markdown, sorted by date (newest first by default).

### `santai ui`

Launch an interactive terminal UI (TUI) dashboard.

```bash
santai ui
```

The TUI displays three panels:

| Panel | Description |
|-------|-------------|
| **Directory Tree** | Browse project files across resources, codebases, history, and notes |
| **Statistics & Notes** | File counts per directory, file type breakdown, recent files, and notes preview |
| **File Graph** | Visualize links between markdown files with color-coded directories |

**Keyboard shortcuts:**

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Refresh all panels |
| `g` | Toggle graph panel visibility |

### `santai web`

Launch a web-based dashboard in your browser.

```bash
# Start on default port 8000
santai web

# Start on a custom port
santai web --port 3000
santai web -p 3000

# Don't auto-open the browser
santai web --no-open
```

The web dashboard includes:

- **Project structure** — Collapsible file tree
- **Directory statistics** — File counts and total size
- **File types** — Breakdown by extension
- **Recent files** — Last modified files
- **History** — Recent history entries
- **Notes** — Notes with content previews
- **File graph** — Interactive D3.js force-directed graph with drag, hover tooltips, and color-coded directory nodes

Press `Ctrl+C` in the terminal to stop the server.

**API endpoints** (JSON):

| Endpoint | Description |
|----------|-------------|
| `GET /api/stats` | Project statistics |
| `GET /api/history` | All history entries |
| `GET /api/notes` | All notes |
| `GET /api/graph` | File graph nodes and edges |

## Project Structure

A Santai project follows this directory layout:

| Directory | Purpose |
|-----------|---------|
| `resources/` | Reference materials — markdown files, PDFs, images, and other documents |
| `codebases/` | Code repositories and references |
| `history/` | Dated markdown documentation of major changes and decisions (supplements git history) |
| `notes/` | General notes, scratch space, and quick thoughts |

Root-level files created by `santai init`:

| File | Purpose |
|------|---------|
| `AGENTS.md` | Project conventions and directory structure documentation |
| `README.md` | Project readme (links to AGENTS.md) |
| `CLAUDE.md` | AI assistant context (links to AGENTS.md) |
| `.pre-commit-config.yaml` | Pre-commit hook configuration for markdown linting |
| `rumdl.toml` | Markdown linter configuration |

## Conventions

### History Files

- **Filename format:** `YYYY-MM-DD-brief-description.md` (e.g., `2025-03-15-migrate-to-postgres.md`)
- Document the **what**, **why**, and any **alternatives considered**
- Git tracks granular changes; `history/` captures the narrative

### Notes

- Use `.md` or `.txt` files
- Name files descriptively (e.g., `meeting-notes.md`, `ideas.txt`)
- Notes are displayed with content previews in both the TUI and web dashboards

### File Linking

The file graph feature detects links between files in your project:

- **Markdown links:** `[link text](relative/path/to/file.md)`
- **Wikilinks:** `[[filename]]` or `[[filename|display text]]`

Links are resolved relative to the source file, the project root, and by filename matching. External URLs (`http://`, `https://`) are ignored.

## Development

```bash
# Clone and install
git clone https://github.com/santai-inc/santai-cli.git
cd santai-cli
uv sync

# Run the CLI
uv run santai --help

# Run via Python module
uv run python -m santai_cli
```

### Source Layout

```
src/santai_cli/
├── __init__.py
├── __main__.py          # Entry point for `python -m santai_cli`
├── cli.py               # Typer app definition and command registration
├── commands/
│   ├── init.py          # `santai init` command
│   ├── history.py       # `santai history` command
│   ├── ui.py            # `santai ui` command
│   └── web.py           # `santai web` command
├── core/
│   └── project.py       # Project detection, data models, file graph logic
├── tui/
│   └── app.py           # Textual TUI application
└── web/
    ├── app.py           # FastAPI web application
    └── templates/
        └── index.html   # Web dashboard template (Jinja2 + D3.js)
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| CLI framework | [Typer](https://typer.tiangolo.com/) |
| Terminal formatting | [Rich](https://rich.readthedocs.io/) |
| Terminal UI | [Textual](https://textual.textualize.io/) |
| Web server | [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) |
| Templating | [Jinja2](https://jinja.palletsprojects.com/) |
| Graph visualization | [D3.js](https://d3js.org/) v7 |
| Build system | [Hatchling](https://hatch.pypa.io/) |
| Package manager | [uv](https://docs.astral.sh/uv/) |

## License

See the repository for license information.