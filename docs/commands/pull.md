# santai pull

Pull a Santai project from Santai Hub to your local machine.

## Usage

```bash
santai pull NAME [OPTIONS]
```

## Arguments

| Argument | Description |
|----------|-------------|
| `NAME` | Project name to pull from the Hub |

## Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--dest` | `-d` | Same as `NAME` | Destination directory for the pulled project |

## Prerequisites

- Must be logged in (`santai login`)

## Behavior

1. Looks up the project by name on Santai Hub
2. Downloads the project archive
3. Extracts to the destination directory

## Examples

Pull a project (creates a directory with the project name):

```bash
santai pull my-research-kb
```

Pull to a specific directory:

```bash
santai pull my-research-kb --dest ~/projects/research
```

## Error Handling

| Error | Cause |
|-------|-------|
| Not logged in | Run `santai login` first |
| Destination already exists | Choose a different path or remove the existing directory |
| Project not found | The named project doesn't exist on your Hub account |
| Session expired | Re-authenticate with `santai login` |
| Download failed | Network issue or expired URL — try again |
