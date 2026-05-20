# santai merge

Merge two Santai projects into a single new project.

## Usage

```bash
santai merge SOURCE1 SOURCE2 DESTINATION
```

## Arguments

| Argument | Description |
|----------|-------------|
| `SOURCE1` | Primary Santai project — its files take precedence on conflicts |
| `SOURCE2` | Secondary Santai project to merge in |
| `DESTINATION` | Directory name for the merged project (must not already exist) |

## Behavior

1. Validates that both source paths are existing directories
2. Copies the primary project (`SOURCE1`) fully to the destination (excluding `.git` and cache directories)
3. Merges the secondary project (`SOURCE2`) — copies files that don't already exist in the destination
4. **Conflicts**: If a file exists in both projects at the same relative path, the primary project's version wins and the secondary file is skipped
5. Initializes a fresh git repository
6. Installs pre-commit hooks via prek
7. Reports a merge summary: files copied from secondary, files skipped due to conflicts

## Examples

Merge two research projects (first project takes precedence):

```bash
santai merge project-a project-b merged-project
```

The merged project will contain:

- All files from `project-a`
- Files from `project-b` that don't conflict with `project-a`
- A fresh git history

!!! note
    The merge is file-level, not content-level. If both projects have `notes/ideas.md`, only the version from `SOURCE1` will be kept. The command reports which files were skipped so you can manually reconcile them.
