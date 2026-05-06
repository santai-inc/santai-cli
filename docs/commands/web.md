# santai web

Launch a web-based dashboard for browsing your project in a browser.

## Usage

```bash
santai web [OPTIONS]
```

## Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--port` | `-p` | `8000` | Port to run the server on |
| `--no-open` | — | `False` | Don't automatically open the browser |

## Requirements

Must be run from within a valid Santai project directory.

## Features

The web dashboard provides:

- **Project overview** — Directory statistics and file type breakdown
- **History browser** — Rendered history entries
- **Notes viewer** — Browse all notes
- **File graph** — Interactive visualization of document links
- **AI chat workspace** — Streaming AI chat in a dedicated right rail with model and agent selection
- **In-place file preview** — Clicking a file opens it in the main workspace with a clear `Back` control, an `X` to close, and optional fullscreen for focused reading

## API Endpoints

The web dashboard exposes a REST API that powers the frontend:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stats` | GET | Project statistics |
| `/api/history` | GET | All history entries |
| `/api/notes` | GET | All notes |
| `/api/graph` | GET | File graph nodes and edges |
| `/api/chat` | POST | Chat with SSE streaming |
| `/api/chat/models` | GET | Available chat models |
| `/api/chat/agents` | GET | Available agent profiles |

## Examples

Launch on the default port (opens browser automatically):

```bash
santai web
```

Launch on a custom port without opening the browser:

```bash
santai web --port 3000 --no-open
```

Stop the server with `Ctrl+C`.

!!! tip
    The web dashboard is useful for sharing your project view with others or for a more visual browsing experience compared to the TUI.
