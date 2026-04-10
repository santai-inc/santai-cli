# AGENTS.md

Instructions for AI agents working in this repository.

## Quick Reference

```bash
# Development setup
uv sync              # Install dependencies
uv run santai --help # Run CLI

# Linting (runs automatically on commit via pre-commit)
ruff check --fix .   # Lint with auto-fix
ruff format .        # Format code

# Install dev tools
uv sync --group dev  # Includes ruff and pre-commit
pre-commit install   # Set up git hooks
```

## Project Structure

```
src/santai_cli/
├── cli.py           # Typer app, command registration
├── commands/        # CLI commands (init, history, ui, web)
├── core/project.py  # Project detection, data models, file graph
├── tui/app.py       # Textual TUI dashboard
└── web/             # FastAPI web dashboard + Jinja2 templates
```

Entry point: `santai_cli.cli:app` (Typer application)

## Key Constraints

- **Python 3.12+** required
- **uv** is the package manager (not pip)
- **Ruff v0.15.6** for linting/formatting - version pinned in `pyproject.toml` and `.pre-commit-config.yaml` (keep in sync)
- Pre-commit hooks run `ruff check --fix` then `ruff format` on commit

## Testing

No test suite currently configured.
