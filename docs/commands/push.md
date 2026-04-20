# santai push

Push the current Santai project to Santai Hub for cloud backup and sharing.

## Usage

```bash
santai push [NAME]
```

## Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `NAME` | Current directory name | Project name on the Hub |

## Prerequisites

- Must be logged in (`santai login`)
- Must be run from within a valid Santai project directory

## Behavior

1. Validates the current directory is a Santai project
2. Packages the project into a zip archive, **excluding**:
    - `.git/`
    - `.ruff_cache/`
    - `.rumdl_cache/`
    - `__pycache__/`
    - `.venv/`
    - `node_modules/`
3. Validates the archive is under 50 MB
4. Uploads to Santai Hub

## Examples

Push with the default name (current directory name):

```bash
santai push
```

Push with a custom name:

```bash
santai push my-research-kb
```

## Size Limit

The maximum upload size is **50 MB** (compressed). If your project exceeds this, consider excluding large binary files or using `.gitignore`-style filtering.

## Error Handling

| Error | Cause |
|-------|-------|
| Not a Santai project | Missing required directories |
| Not logged in | Run `santai login` first |
| Archive exceeds 50 MB | Project too large after compression |
| Session expired | Re-authenticate with `santai login` |
| Could not reach the hub | Network issue or hub is down |
