# santai ui

Launch the terminal UI (TUI) dashboard for visual project exploration.

## Usage

```bash
santai ui [OPTIONS]
```

## Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--theme` | `-t` | `btop` | Theme to use: `claude`, `catppuccin`, `btop`, `light` |

## Requirements

Must be run from within an existing directory.

## Dashboard Panels

The TUI provides a multi-panel dashboard:

- **Directory tree** — Browse all files across your project directories
- **Project statistics** — File counts per directory, total size, file type distribution, recent files
- **Notes panel** — Quick view of your notes with previews
- **File graph** — Force-directed graph visualization showing links between your documents, rendered with Braille characters

## Keybindings

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Refresh all panels |
| `g` | Toggle fullscreen graph |
| `/` | Open graph search |
| `f` | Filter graph by directory |
| `t` | Open theme selector |
| `n` | Add a new note |
| `p` | Cycle color palette within current theme |
| `c` | Clear graph search/filter |
| `x` | Open the chat panel |
| `Esc` | Back / exit fullscreen graph |

## Themes

Four themes are available:

| Theme | Description |
|-------|-------------|
| `btop` (default) | Inspired by the btop system monitor |
| `claude` | Anthropic Claude-inspired colors |
| `catppuccin` | Catppuccin pastel theme |
| `light` | Light background theme |

Switch themes at launch:

```bash
santai ui --theme catppuccin
```

Or press `t` within the TUI to switch interactively.

## Chat Panel

Press `x` to open a modal chat screen within the TUI. This uses the same chat engine as `santai chat`, supporting model selection and agent profiles.

## Examples

Launch with the default theme:

```bash
santai ui
```

Launch with the light theme:

```bash
santai ui --theme light
```
