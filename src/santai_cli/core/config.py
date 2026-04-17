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
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
}

# Popular models available per provider (for interactive selection)
AVAILABLE_MODELS: dict[str, list[str]] = {
    "anthropic": [
        "claude-sonnet-4-20250514",
        "claude-opus-4-20250514",
        "claude-haiku-4-20250514",
    ],
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "o3-mini",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
    ],
}


@dataclass
class ProviderConfig:
    """Configuration for a single AI provider."""

    name: str
    api_key: str
    model: str
    available_models: list[str] = field(default_factory=list)


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
        """
        choices: list[tuple[str, str, str]] = []
        for provider_name, config in self.providers.items():
            for model in config.available_models:
                # Mark the configured/default model
                marker = " *" if model == config.model else ""
                label = f"{provider_name}: {model}{marker}"
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
            load_dotenv(env_path)
    else:
        # Try loading from cwd
        load_dotenv()

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
        config.providers["openai"] = ProviderConfig(
            name="OpenAI",
            api_key=openai_key,
            model=openai_model,
            available_models=AVAILABLE_MODELS["openai"],
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


def _strip_frontmatter(content: str) -> str:
    """Strip YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return content.strip()

    end = content.find("---", 3)
    if end == -1:
        return content.strip()

    return content[end + 3 :].strip()
