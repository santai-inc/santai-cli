# AGENTS.md

Instructions for AI agents working in this repository.

## Quick Reference

```bash
# Development setup
uv sync --group dev  # Install dependencies (includes ruff, ty, pre-commit)
uv run santai --help # Run CLI
prek install         # Set up pre-commit hooks (ruff format on commit)

# Install prek (if not already installed)
uv tool install prek # Install prek globally

# Formatting (runs automatically on commit via pre-commit)
ruff format .        # Format code

# Linting (recommended, not enforced via hooks)
ruff check --fix .   # Lint with auto-fix
ruff check .         # Lint without auto-fix

# Type checking (recommended, not enforced via hooks)
ty check src/        # Run type checker
```

## Project Structure

```
src/santai_cli/
├── cli.py           # Typer app, command registration
├── agents/          # Markdown agent profiles for AI chat system prompts
├── commands/        # CLI commands (init, copy, chat, history, ui, web)
├── core/
│   ├── project.py   # Project detection, data models, file graph
│   ├── config.py    # Environment/config loading, API key validation
│   └── chat.py      # Shared chat engine (streaming, provider abstraction)
├── tui/             # Textual TUI dashboard
│   ├── app.py       # Main TUI application (includes ChatScreen modal)
│   ├── graph_render.py  # Force-directed graph with Braille rendering
│   └── themes.py    # Multi-theme system
└── web/             # FastAPI web dashboard + Jinja2 templates
```

Entry point: `santai_cli.cli:app` (Typer application)

## Santai Project Directories

When `santai init` creates a new project, it creates these core directories:

- **resources/** - Reference materials (markdown, PDFs, images, documents)
- **codebases/** - Code repositories and references
- **history/** - Markdown documentation of major changes and decisions
- **notes/** - General notes, scratch space, and quick thoughts
- **wiki/** - Important context for grounding AI agents and solidifying project knowledge

These are defined in `SANTAI_DIRS` in `src/santai_cli/core/project.py`. When adding a new directory, update all references across `core/project.py`, `commands/init.py`, `tui/app.py`, `web/app.py`, and `web/templates/index.html`.

## Key Constraints

- **Python 3.12+** required
- **uv** is the package manager (not pip)
- **Ruff v0.15.6** for linting/formatting — version pinned in `pyproject.toml` and `.pre-commit-config.yaml` (keep in sync)
- **ty** for type checking — recommended but not enforced
- Pre-commit hooks run `ruff format` on commit (formatting only)
- Linting (`ruff check`) and type checking (`ty check`) should be run manually before submitting PRs

## Code Quality Workflow

1. **On every commit**: `ruff format` runs automatically via pre-commit hook
2. **Before submitting a PR**: Run `ruff check --fix .` and `ty check src/` manually
3. **Goal**: Zero errors from both `ruff check` and `ty check`

## Testing

No test suite currently configured.

## AI Chat Configuration

The `santai chat` command (and the chat panels in TUI/Web) require API keys configured in a `.env` file at the project root:

```bash
# At least one provider key is required
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Optional: override default models
ANTHROPIC_MODEL=claude-sonnet-4-20250514
OPENAI_MODEL=gpt-4o
```

See `.env.example` for the full template. The `.env` file is gitignored.

### Chat Architecture

- **`core/config.py`** — Loads `.env`, validates API keys, exposes available models/providers
- **`core/chat.py`** — Provider-agnostic chat engine with `ChatSession` (message history) and async streaming via `stream_response()`
- **`commands/chat.py`** — CLI REPL with Rich Live streaming, `/agent`, `/model`, `/clear` commands
- **`tui/app.py` (`ChatScreen`)** — Modal chat screen in TUI, opened with `x` key
- **`web/app.py`** — SSE streaming endpoints: `POST /api/chat`, `GET /api/chat/models`, `GET /api/chat/agents`
- **`web/templates/index.html`** — Chat panel in web dashboard with streaming display

### Agent Profiles

The `agents/` directory contains markdown files that serve as system prompts. Each file has YAML frontmatter with a `description:` field. Use `santai chat --agent code-review` to load an agent, or select one interactively in the TUI/Web chat panels.
