# santai copy

Copy a Santai project to a new location with a fresh git history.

## Usage

```bash
santai copy SOURCE DESTINATION
```

## Arguments

| Argument | Description |
|----------|-------------|
| `SOURCE` | Path to the source Santai project (or `.` for the current directory) |
| `DESTINATION` | Directory name for the copy (must not already exist) |

## Behavior

1. Validates that the source is a valid Santai project (contains `resources/`, `codebases/`, `history/`, `notes/`)
2. Creates the destination directory
3. Copies all project files, **excluding**:
    - `.git/`
    - `.ruff_cache/`
    - `.rumdl_cache/`
    - `__pycache__/`
    - `.venv/`
4. Initializes a fresh git repository in the destination
5. Installs pre-commit hooks via prek

## Examples

Copy the current project to a new directory:

```bash
santai copy . my-project-v2
```

Copy from a specific path:

```bash
santai copy ~/projects/research ~/projects/research-fork
```

!!! tip
    This is useful for creating a clean fork of a project without carrying over git history, while preserving all content and structure.
