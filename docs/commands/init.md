# santai init

Initialize a new Santai project with the standard directory structure, git repository, and configuration files.

## Usage

```bash
santai init [NAME]
```

## Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `NAME` | `.` | Directory name to create and initialize. Use `.` to initialize in the current directory. |

## What It Creates

### Directories

Each directory is created with a `.gitkeep` file so it is tracked by git:

| Directory | Purpose |
|-----------|---------|
| `resources/` | Reference materials — markdown, PDFs, images, documents |
| `codebases/` | Code repositories and references |
| `history/` | Dated markdown entries documenting major changes and decisions |
| `notes/` | General notes, scratch space, quick thoughts |
| `wiki/` | Curated knowledge for AI agent context grounding |

### Files

| File | Purpose |
|------|---------|
| `AGENTS.md` | Project structure documentation and conventions for AI agents |
| `README.md` | Project readme (pre-filled with project name) |
| `CLAUDE.md` | AI assistant context pointer (links to AGENTS.md) |
| `.pre-commit-config.yaml` | Pre-commit hook config for rumdl markdown linting |
| `rumdl.toml` | Markdown linter configuration |
| `.env.example` | Template for AI chat API keys |
| `.gitignore` | Ignores `.env` files |

### Git Setup

- Initializes a new git repository
- Installs pre-commit hooks via [prek](https://github.com/santai-inc/prek) (warns if prek is not installed)

## Examples

Create a new project in a new directory:

```bash
santai init my-research-project
cd my-research-project
```

Initialize in the current (empty) directory:

```bash
mkdir my-project && cd my-project
santai init .
```

!!! warning
    The target directory must be empty or non-existent. `santai init` will refuse to overwrite existing files.
