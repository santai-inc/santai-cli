"""Configuration management for Santai CLI.

Loads environment variables from .env files and provides
API key validation and model configuration for AI chat providers.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Default models per provider
DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-4o",
}

# Fallback model lists used when the provider's /v1/models API call fails.
# The live API is always preferred — these are last-resort defaults only.
# IDs must match what the provider API returns (including date suffixes where
# the provider requires them, e.g. claude-haiku-4-5-20251001).
AVAILABLE_MODELS: dict[str, list[str]] = {
    "anthropic": [
        "claude-opus-4-7",
        "claude-sonnet-4-6",
        "claude-haiku-4-5-20251001",
    ],
    "openai": [
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4o",
        "gpt-4o-mini",
        "o3-mini",
        "o4-mini",
    ],
}


@dataclass
class ProviderConfig:
    """Configuration for a single AI provider."""

    name: str
    api_key: str = field(repr=False)
    model: str
    available_models: list[str] = field(default_factory=list)
    base_url: str | None = None


@dataclass
class ChatConfig:
    """Full chat configuration with all available providers."""

    providers: dict[str, ProviderConfig] = field(default_factory=dict)

    @property
    def has_any_provider(self) -> bool:
        """Check if at least one provider is configured."""
        return len(self.providers) > 0

    def get_model_choices(self) -> list[tuple[str, str, str]]:
        """Return a list of (display_label, provider, model) for interactive selection.

        Each configured provider contributes its available models to the list.
        Labels combine a friendly display name with the raw model ID so users
        can see both what they're picking and the underlying identifier.
        """
        # Imported lazily to avoid a circular import (models.py imports from
        # config.py for ProviderConfig).
        from santai_cli.core.models import display_label_for_model

        choices: list[tuple[str, str, str]] = []
        for provider_name, config in self.providers.items():
            for model in config.available_models:
                marker = " *" if model == config.model else ""
                display = display_label_for_model(model)
                if display == model:
                    label = f"{provider_name}: {model}{marker}"
                else:
                    label = f"{display}  ({provider_name}/{model}){marker}"
                choices.append((label, provider_name, model))
        return choices


def load_config(project_root: Path | None = None) -> ChatConfig:
    """Load chat configuration from environment.

    Looks for a .env file in the project root (if provided) and falls
    back to environment variables. Returns a ChatConfig with all
    providers that have valid API keys set.

    Args:
        project_root: Optional path to the santai project root.
                      If provided, loads .env from this directory.

    Returns:
        ChatConfig with discovered providers.
    """
    # Load .env from project root if available
    if project_root:
        env_path = project_root / ".env"
        if env_path.is_file():
            load_dotenv(env_path, override=True)
    else:
        # Try loading from cwd
        load_dotenv(override=True)

    config = ChatConfig()

    # Check Anthropic
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if anthropic_key and not anthropic_key.startswith("your-"):
        anthropic_model = os.environ.get(
            "ANTHROPIC_MODEL", DEFAULT_MODELS["anthropic"]
        ).strip()
        config.providers["anthropic"] = ProviderConfig(
            name="Anthropic",
            api_key=anthropic_key,
            model=anthropic_model,
            available_models=AVAILABLE_MODELS["anthropic"],
        )

    # Check OpenAI
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key and not openai_key.startswith("your-"):
        openai_model = os.environ.get("OPENAI_MODEL", DEFAULT_MODELS["openai"]).strip()
        openai_base_url = os.environ.get("OPENAI_API_BASE_URL", "").strip() or None
        config.providers["openai"] = ProviderConfig(
            name="OpenAI",
            api_key=openai_key,
            model=openai_model,
            available_models=AVAILABLE_MODELS["openai"],
            base_url=openai_base_url,
        )

    return config


def get_agent_profiles(agents_dir: Path | None = None) -> list[tuple[str, str]]:
    """Get available agent profiles from the agents directory.

    Returns a list of (name, description) tuples. The name is the
    filename stem (e.g. 'code-review') and description is extracted
    from the YAML frontmatter if present.

    Args:
        agents_dir: Path to the agents directory. If None, uses the
                    bundled agents directory from the package.

    Returns:
        List of (name, description) tuples sorted by name.
    """
    if agents_dir is None:
        agents_dir = Path(__file__).parent.parent / "agents"

    if not agents_dir.is_dir():
        return []

    profiles: list[tuple[str, str]] = []
    for md_file in sorted(agents_dir.glob("*.md")):
        # Skip README and HOW_TO_USE
        if md_file.stem.upper() in ("README", "HOW_TO_USE"):
            continue

        description = _extract_description(md_file)
        profiles.append((md_file.stem, description))

    return profiles


def load_agent_prompt(agent_name: str, agents_dir: Path | None = None) -> str | None:
    """Load the system prompt for a named agent.

    Reads the agent markdown file and strips YAML frontmatter,
    returning only the body content as the system prompt.

    Args:
        agent_name: Agent name (e.g. 'code-review').
        agents_dir: Path to agents directory. Uses bundled default if None.

    Returns:
        The agent's system prompt text, or None if agent not found.
    """
    if agents_dir is None:
        agents_dir = Path(__file__).parent.parent / "agents"

    agent_file = agents_dir / f"{agent_name}.md"
    if not agent_file.is_file():
        return None

    content = agent_file.read_text(encoding="utf-8")
    return _strip_frontmatter(content)


def _extract_description(md_file: Path) -> str:
    """Extract the description from YAML frontmatter of an agent file."""
    try:
        content = md_file.read_text(encoding="utf-8")
    except OSError:
        return ""

    if not content.startswith("---"):
        return ""

    # Find closing ---
    end = content.find("---", 3)
    if end == -1:
        return ""

    frontmatter = content[3:end]
    for line in frontmatter.splitlines():
        line = line.strip()
        if line.startswith("description:"):
            return line[len("description:") :].strip()

    return ""


def save_api_keys(
    project_root: Path | None,
    anthropic_key: str = "",
    openai_key: str = "",
) -> Path:
    """Save API keys to a .env file, preserving any existing content.

    Reads the existing .env (if present), replaces or adds the key lines,
    and writes the file back. Lines for keys that are empty strings are
    left unchanged (or omitted if not already present).

    Args:
        project_root: Santai project root. Falls back to cwd if None.
        anthropic_key: Anthropic API key value (empty string to skip).
        openai_key: OpenAI API key value (empty string to skip).

    Returns:
        Path to the written .env file.
    """
    env_dir = project_root if project_root else Path.cwd()
    env_path = env_dir / ".env"

    # Read existing content or start from a template
    if env_path.is_file():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    else:
        lines = [
            "# Santai CLI - AI Chatbot Configuration",
            "# Generated by `santai chat` interactive setup.",
        ]

    keys_to_set: dict[str, str] = {}
    if anthropic_key:
        keys_to_set["ANTHROPIC_API_KEY"] = anthropic_key
    if openai_key:
        keys_to_set["OPENAI_API_KEY"] = openai_key

    # Replace existing lines that match the keys
    updated_keys: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        replaced = False
        for key, value in keys_to_set.items():
            # Match lines like KEY=..., # KEY=..., or commented placeholders
            stripped = line.lstrip("# ").strip()
            if stripped.startswith(f"{key}="):
                new_lines.append(f"{key}={value}")
                updated_keys.add(key)
                replaced = True
                break
        if not replaced:
            new_lines.append(line)

    # Append any keys that weren't already in the file
    for key, value in keys_to_set.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return env_path


def _strip_frontmatter(content: str) -> str:
    """Strip YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return content.strip()

    end = content.find("---", 3)
    if end == -1:
        return content.strip()

    return content[end + 3 :].strip()
