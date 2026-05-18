# AGENTS.md

Instructions for AI agents working in this repository.

## Quick Reference

```bash
uv sync --group dev    # Install dependencies
uv run santai --help   # Run CLI
ruff format .          # Format code
ruff check --fix .     # Lint with auto-fix
ty check src/          # Type check
```

## Project Structure

```
src/santai_cli/
├── cli.py           # Typer app, command registration
├── agents/          # Markdown agent profiles (system prompts for chat)
├── commands/        # CLI commands (init, copy, cherry-pick, merge, chat, ui, web)
├── core/
│   ├── project.py   # Project detection, data models, file graph
│   ├── config.py    # Environment/config loading, API key validation
│   └── chat.py      # Chat engine (streaming, provider abstraction)
├── tui/             # Textual TUI dashboard
└── web/             # FastAPI web dashboard + Jinja2 templates
```

Entry point: `santai_cli.cli:app` (Typer application)

## Adding a New Command

1. Create `src/santai_cli/commands/yourcommand.py` with a single function
2. Use `Annotated[..., typer.Argument/Option(...)]` for parameters
3. Use `is_santai_project()` / `get_project()` from `core/project.py` for validation
4. Import in `cli.py` and register with `app.command(name="yourcommand")(mod.func)`

## Santai Project Directories

Defined in `SANTAI_DIRS` in `src/santai_cli/core/project.py`:

- **media/** - Reference materials (markdown, PDFs, images, documents)
- **history/** - Markdown documentation of major changes and decisions
- **notes/** - General notes, scratch space, and quick thoughts

When adding a new directory, update references across `core/project.py`, `commands/init.py`, `tui/app.py`, `web/app.py`, and `web/templates/index.html`.

## Key Constraints

- **Python 3.12+** required
- **uv** is the package manager (not pip)
- **Ruff** for linting/formatting — version pinned in `pyproject.toml` and `.pre-commit-config.yaml`
- Pre-commit hooks run `ruff format` on commit
- Run `ruff check --fix .` and `ty check src/` before submitting PRs

## AI Chat Configuration

Requires API keys in `.env` (see `.env.example`):

```bash
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

Agent profiles live in `agents/` as markdown files with YAML frontmatter.
