# santai cherry-pick

Selectively copy specific files or folders from one Santai project into another.

Unlike `copy` (which clones an entire project) or `merge` (which combines two full projects), `cherry-pick` lets you move just the pieces you need between knowledge bases.

## Usage

```bash
santai cherry-pick SOURCE DESTINATION FILES...
```

## Arguments

| Argument | Description |
|----------|-------------|
| `SOURCE` | Source Santai project path (or `.` for current directory) |
| `DESTINATION` | Destination Santai project path (or `.`) |
| `FILES...` | One or more files or folders to cherry-pick (relative paths inside the source project) |

## Options

| Option | Description |
|--------|-------------|
| `--overwrite` | Overwrite existing files in the destination without prompting |
| `--skip` | Silently skip files that already exist in the destination |
| `--dry-run` | Show what would be copied without actually copying |

## Behavior

1. Validates that both source and destination are valid Santai projects
2. Resolves each target path:
    - Direct relative paths (e.g., `notes/idea.md`)
    - Bare filenames searched across Santai directories (e.g., `idea.md`)
3. For directories, recursively collects all files (excluding `.git`, `.ruff_cache`, `.rumdl_cache`, `__pycache__`, `.venv`)
4. Copies files to the same relative path in the destination
5. On conflicts:
    - With `--overwrite`: replaces existing files
    - With `--skip`: silently skips
    - Otherwise: prompts interactively for each conflict
6. Reports a summary of copied, overwritten, and skipped files

## Examples

Cherry-pick a single file:

```bash
santai cherry-pick ./kb-large ./kb-small notes/idea.md
```

Cherry-pick an entire directory and a specific file:

```bash
santai cherry-pick ./research ./writing wiki/ resources/outline.md
```

Preview what would be copied:

```bash
santai cherry-pick . ../other-kb notes/ --dry-run
```

Overwrite all conflicts without prompting:

```bash
santai cherry-pick ./source ./dest wiki/architecture.md --overwrite
```

Skip existing files silently:

```bash
santai cherry-pick ./source ./dest resources/ --skip
```

!!! tip
    Use `--dry-run` first to preview exactly which files will be copied and which already exist in the destination.
