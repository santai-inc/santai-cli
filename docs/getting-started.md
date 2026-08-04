# Getting Started

This guide walks you through installing santai, creating your first project, and exploring it with the built-in tools.

## Installation

### Using uv (recommended)

```bash
uv tool install santai-cli
```

### Using pip

```bash
pip install santai-cli
```

### From source

```bash
git clone https://github.com/santai-inc/santai-cli.git
cd santai-cli
uv sync
uv run santai --help
```

## Creating Your First Project

Initialize a new Santai project:

```bash
santai init my-project
```

This creates the following structure:

```
my-project/
├── .git/
├── .gitignore
├── .env.example
├── .pre-commit-config.yaml
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── rumdl.toml
├── media/
│   └── .gitkeep
├── notes/
│   └── .gitkeep
└── chat-history/
    └── .gitkeep
```

You can also initialize in the current directory:

```bash
mkdir my-project && cd my-project
santai init .
```

!!! note
    The target directory must be empty or non-existent. Santai will not overwrite existing files.

## Adding Content

### Notes

Drop markdown or text files into `notes/` for quick reference:

```bash
echo "# Meeting Notes\nDiscussed the new API design." > notes/api-meeting.md
```

### Media

Place reference documents in `media/`:

```bash
cp ~/design-spec.pdf media/
echo "# Architecture Overview\nThe system uses a microservices pattern..." > media/architecture.md
```

## Exploring Your Project

### Terminal UI

Launch the TUI dashboard to get an overview of your project:

```bash
santai ui
```

This opens an interactive terminal dashboard with:

- Directory tree browser
- Project statistics
- Notes panel
- Interactive file graph showing links between documents

Key bindings:

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Refresh all panels |
| `g` | Toggle fullscreen graph |
| `/` | Search the graph |
| `f` | Filter graph by directory |
| `t` | Open theme selector |
| `n` | Add a new note |
| `p` | Cycle color palette |
| `c` | Clear graph search/filter |
| `x` | Open the chat panel |

### Web Dashboard

For a browser-based experience:

```bash
santai web
```

This starts a local server at `http://127.0.0.1:8000` and opens your browser automatically. Use `--no-open` to skip the browser launch, or `--port` to change the port.

### AI Chat

Set up your API keys first (see [Configuration](configuration.md)), then start chatting:

```bash
santai chat
```

You'll be prompted to select a model. Use `--model` to skip the selection:

```bash
santai chat --model claude-sonnet-4-6
santai chat --model gpt-4o
```

Load an agent profile for specialized behavior:

```bash
santai chat --agent research
```

## Next Steps

- [Command Reference](commands/index.md) — Detailed docs for every command
- [Configuration](configuration.md) — Set up API keys and customize models
- [Agent Profiles](agents.md) — Learn about the built-in AI agent profiles
- [Use Cases](use-cases.md) — Common workflows and recipes
