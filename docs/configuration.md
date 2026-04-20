# Configuration

Santai CLI uses environment variables for AI chat configuration. These are loaded from a `.env` file in your project root.

## Setting Up the `.env` File

When you run `santai init`, a `.env.example` template is created. Copy it and fill in your keys:

```bash
cp .env.example .env
```

Then edit `.env` with your API keys:

```bash
# At least one provider key is required
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Optional: override default models
ANTHROPIC_MODEL=claude-sonnet-4-20250514
OPENAI_MODEL=gpt-4o
```

!!! warning
    The `.env` file is gitignored by default. Never commit API keys to version control.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | At least one provider | — | Your Anthropic API key |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-20250514` | Default Anthropic model |
| `OPENAI_API_KEY` | At least one provider | — | Your OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o` | Default OpenAI model |
| `SANTAI_HUB_URL` | No | `http://localhost:3000` | Santai Hub URL for push/pull/auth |

You need at least one provider key configured for AI chat. You can configure both to have access to models from both providers.

## Available Models

### Anthropic

| Model | Notes |
|-------|-------|
| `claude-sonnet-4-20250514` | Default |
| `claude-opus-4-20250514` | |
| `claude-haiku-4-20250514` | |

### OpenAI

| Model | Notes |
|-------|-------|
| `gpt-4o` | Default |
| `gpt-4o-mini` | |
| `o3-mini` | |
| `gpt-4.1` | |
| `gpt-4.1-mini` | |
| `gpt-4.1-nano` | |

## Overriding the Default Model

Set the `ANTHROPIC_MODEL` or `OPENAI_MODEL` environment variable to change which model is selected by default in the interactive picker:

```bash
# .env
ANTHROPIC_MODEL=claude-opus-4-20250514
OPENAI_MODEL=gpt-4.1
```

You can also bypass the interactive picker entirely with the `--model` flag:

```bash
santai chat --model gpt-4o-mini
```

## API Key Validation

Santai performs basic validation on API keys:

- Keys starting with `your-` are rejected (these are placeholders from the `.env.example` template)
- Invalid or expired keys will produce a clear authentication error when you attempt to chat

## Where the `.env` Is Loaded From

The `.env` file is loaded from the project root directory (the directory containing your Santai project directories). If no Santai project is detected, it falls back to the current working directory.
