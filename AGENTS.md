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
├── commands/        # CLI commands (init, copy, history, ui, web)
├── core/project.py  # Project detection, data models, file graph
├── tui/             # Textual TUI dashboard
│   ├── app.py       # Main TUI application
│   ├── graph_render.py  # Force-directed graph with Braille rendering
│   └── themes.py    # Multi-theme system
└── web/             # FastAPI web dashboard + Jinja2 templates
```

Entry point: `santai_cli.cli:app` (Typer application)

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
