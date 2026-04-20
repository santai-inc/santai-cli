# Santai CLI

A CLI for managing Santai knowledge-base projects — with a terminal UI, web dashboard, and AI chat.

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)**
- **Git**
- **[prek](https://prek.j178.dev/)** (optional, for pre-commit hooks)

## Installation

```bash
git clone https://github.com/santai-inc/santai-cli.git
cd santai-cli

# Global install (recommended)
uv tool install --from . santai-cli

# Or development install
uv sync
uv run santai --help
```

## Quick Start

```bash
santai init my-project
cd my-project
santai ui
```

## Commands

### `santai init [NAME]`

Initialize a new Santai project with the standard directory structure, git repo, and pre-commit hooks.

```bash
santai init my-project
santai init .
```

### `santai copy SOURCE DESTINATION`

Copy an entire project to a new location with a fresh git history.

```bash
santai copy . ../forked-kb
```

### `santai cherry-pick SOURCE DESTINATION FILES...`

Selectively copy specific files or folders from one project into another.

```bash
santai cherry-pick ./kb-large ./kb-small notes/idea.md
santai cherry-pick ./research ./writing wiki/ resources/outline.md
santai cherry-pick . ../other-kb notes/ --dry-run
```

| Option | Description |
|--------|-------------|
| `--overwrite` | Overwrite existing files without prompting |
| `--skip` | Silently skip files that already exist |
| `--dry-run` | Preview what would be copied |

### `santai merge SOURCE1 SOURCE2 DESTINATION`

Merge two projects into a new combined project. The primary project's files take precedence on conflicts.

```bash
santai merge ./primary-kb ./secondary-kb ./combined-kb
```

### `santai chat`

Interactive AI chat session. Requires an API key in `.env` (see `.env.example`).

```bash
santai chat
santai chat --agent research
santai chat --model claude-sonnet-4-20250514
```

### `santai ui`

Launch the terminal UI dashboard.

```bash
santai ui
santai ui --theme catppuccin
```

### `santai web`

Launch the web dashboard in your browser.

```bash
santai web
santai web --port 3000
```

### `santai push` / `santai pull`

Sync projects with Santai Hub (requires `santai login`).

```bash
santai push                  # Upload current project
santai pull my-project       # Download a project
```

### `santai login` / `santai logout` / `santai whoami`

Authenticate with Santai Hub.

```bash
santai login                 # Browser-based auth flow
santai whoami                # Show current user
santai logout                # Clear credentials
```

---

For detailed usage, options, and examples for all commands, see the [full documentation](https://santai-inc.github.io/santai-cli/commands/).

## Project Structure

A Santai project contains these directories:

| Directory | Purpose |
|-----------|---------|
| `resources/` | Reference materials (markdown, PDFs, images, documents) |
| `codebases/` | Code repositories and references |
| `history/` | Dated markdown entries documenting major changes |
| `notes/` | General notes and scratch space |
| `wiki/` | Context for grounding AI agents |

## Development

```bash
uv sync --group dev
uv run santai --help
ruff format .
ruff check --fix .

# Serve documentation locally
uv run mkdocs serve
```

### Source Layout

```
src/santai_cli/
├── cli.py               # Typer app, command registration
├── commands/
│   ├── init.py          # santai init
│   ├── copy.py          # santai copy
│   ├── cherry_pick.py   # santai cherry-pick
│   ├── merge.py         # santai merge
│   ├── chat.py          # santai chat
│   ├── auth.py          # santai login/logout/whoami
│   ├── push.py          # santai push
│   ├── pull.py          # santai pull
│   ├── ui.py            # santai ui
│   └── web.py           # santai web
├── core/
│   ├── project.py       # Project detection, data models, file graph
│   ├── config.py        # Environment/config loading, API key validation
│   └── chat.py          # Chat engine (streaming, provider abstraction)
├── tui/
│   └── app.py           # Textual TUI application
└── web/
    ├── app.py           # FastAPI web application
    └── templates/
        └── index.html   # Web dashboard (Jinja2 + D3.js)
```

## License

See the repository for license information.
