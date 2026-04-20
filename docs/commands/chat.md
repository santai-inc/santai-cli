# santai chat

Start an interactive AI chat session with support for multiple providers, model selection, and agent profiles.

## Usage

```bash
santai chat [OPTIONS]
```

## Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--agent` | `-a` | None | Agent profile name to use as system prompt |
| `--model` | `-m` | None | Model to use (skips interactive selection) |

## Prerequisites

At least one AI provider API key must be configured in a `.env` file. See [Configuration](../configuration.md) for details.

## Interactive Model Selection

When launched without `--model`, santai presents an interactive numbered list of available models based on your configured API keys:

```
Available models:

  Anthropic:
    1. claude-sonnet-4-20250514 *
    2. claude-opus-4-20250514
    3. claude-haiku-4-20250514

  OpenAI:
    4. gpt-4o *
    5. gpt-4o-mini
    6. o3-mini
    7. gpt-4.1
    8. gpt-4.1-mini
    9. gpt-4.1-nano

Select a model (number):
```

Models marked with `*` are the configured defaults. If only one provider is configured with a single model, it is auto-selected.

## REPL Commands

Once in the chat session, these slash commands are available:

| Command | Description |
|---------|-------------|
| `/quit`, `/exit`, `/q` | Exit the chat |
| `/clear` | Clear conversation history (keeps system prompt) |
| `/agent` | List available agents |
| `/agent <name>` | Switch to a different agent (clears conversation history) |
| `/model` | Re-select the model interactively |
| `/help` | Show available commands |

## Agent Profiles

Load an agent profile to set a specialized system prompt:

```bash
santai chat --agent research
santai chat --agent documentation
santai chat --agent wiki
```

See [Agent Profiles](../agents.md) for details on each agent.

## Examples

Start a chat with the default model selection:

```bash
santai chat
```

Start with a specific model:

```bash
santai chat --model gpt-4o
santai chat --model claude-sonnet-4-20250514
```

Use an agent profile with a specific model:

```bash
santai chat --agent research --model gpt-4o
```

Switch agents mid-session:

```
You: /agent wiki
Switched to agent: wiki
Conversation history cleared.

You: What pages should I add to the wiki?
```

## Streaming

Responses are streamed in real-time with Rich markdown rendering at 12fps. The chat supports long-running responses with a maximum token limit of 4096 per response.

## Error Handling

The chat provides friendly error messages for common issues:

- **401 / Authentication error** — Invalid API key
- **429 / Rate limit** — Too many requests, wait and retry
- **Model not found** — The specified model is not available
- **No API keys configured** — Instructions for setting up `.env`
