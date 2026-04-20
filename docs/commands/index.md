# Command Reference

Santai CLI provides commands for managing your project. Each command is described in detail on its own page.

## Commands

| Command | Description |
|---------|-------------|
| [`santai init`](init.md) | Initialize a new Santai project |
| [`santai copy`](copy.md) | Copy a project with fresh git history |
| [`santai cherry-pick`](cherry_pick.md) | Cherry-pick specific files between projects |
| [`santai merge`](merge.md) | Merge two Santai projects into one |
| [`santai chat`](chat.md) | Start an interactive AI chat session |
| [`santai ui`](ui.md) | Launch the TUI dashboard |
| [`santai web`](web.md) | Launch the web dashboard |
| [`santai push`](push.md) | Push project to Santai Hub |
| [`santai pull`](pull.md) | Pull project from Santai Hub |
| [`santai login`](auth.md) | Authenticate with Santai Hub |
| [`santai logout`](auth.md) | Log out of Santai Hub |
| [`santai whoami`](auth.md) | Show current authenticated user |

## Global Options

```bash
santai --help           # Show help
santai --help --verbose # Show extended help with keybindings and tips
```

The `--verbose` / `-v` flag on the top-level help renders a Rich-formatted help page with all commands, keybindings, quick start instructions, project structure, and tips.
