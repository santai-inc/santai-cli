"""Configuration management for Santai CLI."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "anthropic-claude-bedrock4.5-haiku",
    "openai": "gpt-5big-santai",
    "xai": "grok3-xai",
    "google": "gemini-3",
    "deepseek": "deepseekr1-bedrock",
    "moonshot": "Kimi-K2.5",
    "amazon": "novapro-bedrock",
    "meta": "llama3.3-bedrock",
}

MODEL_DISPLAY_NAMES: dict[str, str] = {
    "anthropic-claude-bedrock4.6opus": "Claude 4.6 Opus",
    "anthropic-claude-bedrock4.6": "Claude 4.6 Sonnet",
    "anthropic-claude-bedrock4.5": "Claude 4.5 Sonnet",
    "anthropic-claude-bedrock4.5-haiku": "Claude 4.5 Haiku",
    "gpt-5big-santai": "GPT-5 Large",
    "gpt-5.4-santai": "GPT-5.4",
    "gpt-5mini-santai": "GPT-5 Mini",
    "grok3-xai": "Grok 3",
    "gemini-3": "Gemini 3 Pro",
    "deepseekr1-bedrock": "DeepSeek R1",
    "Kimi-K2.5": "Kimi K2.5",
    "novapro-bedrock": "Nova Pro",
    "llama3.3-bedrock": "Llama 3.3",
}

AVAILABLE_MODELS: dict[str, list[str]] = {
    "anthropic": [
        "anthropic-claude-bedrock4.6opus",
        "anthropic-claude-bedrock4.6",
        "anthropic-claude-bedrock4.5",
        "anthropic-claude-bedrock4.5-haiku",
    ],
    "openai": [
        "gpt-5big-santai",
        "gpt-5.4-santai",
        "gpt-5mini-santai",
    ],
    "xai": ["grok3-xai"],
    "google": ["gemini-3"],
    "deepseek": ["deepseekr1-bedrock"],
    "moonshot": ["Kimi-K2.5"],
    "amazon": ["novapro-bedrock"],
    "meta": ["llama3.3-bedrock"],
}


@dataclass
class ProviderConfig:
    """Configuration for a single AI provider."""

    name: str
    api_key: str
    model: str
    available_models: list[str] = field(default_factory=list)
    base_url: str | None = None
    display_names: dict[str, str] = field(default_factory=dict)


@dataclass
class ChatConfig:
    """Full chat configuration with all available providers."""

    providers: dict[str, ProviderConfig] = field(default_factory=dict)

    @property
    def has_any_provider(self) -> bool:
        return len(self.providers) > 0

    def get_model_choices(self) -> list[tuple[str, str, str]]:
        choices: list[tuple[str, str, str]] = []
        for provider_name, config in self.providers.items():
            for model in config.available_models:
                marker = " *" if model == config.model else ""
                display = config.display_names.get(model, model)
                label = f"{provider_name}: {display}{marker}"
                choices.append((label, provider_name, model))
        return choices


def load_config(project_root: Path | None = None) -> ChatConfig:
    if project_root:
        env_path = project_root / ".env"
        if env_path.is_file():
            load_dotenv(env_path, override=True)
    else:
        load_dotenv(override=True)

    config = ChatConfig()

    def _key(env_var: str) -> str:
        return os.environ.get(env_var, "").strip()

    def _register(
        key_env: str,
        provider_id: str,
        display_name: str,
        model_env: str,
        base_url: str | None = None,
        base_url_env: str | None = None,
    ) -> None:
        api_key = _key(key_env)
        if not api_key or api_key.startswith("your-"):
            return
        model = _key(model_env) or DEFAULT_MODELS[provider_id]
        url = base_url
        if base_url_env:
            url = _key(base_url_env) or base_url
        config.providers[provider_id] = ProviderConfig(
            name=display_name,
            api_key=api_key,
            model=model,
            available_models=AVAILABLE_MODELS[provider_id],
            base_url=url,
            display_names=MODEL_DISPLAY_NAMES,
        )

    _register("ANTHROPIC_API_KEY", "anthropic", "Anthropic", "ANTHROPIC_MODEL")
    _register(
        "OPENAI_API_KEY",
        "openai",
        "OpenAI",
        "OPENAI_MODEL",
        base_url_env="OPENAI_API_BASE_URL",
    )
    _register(
        "XAI_API_KEY",
        "xai",
        "xAI",
        "XAI_MODEL",
        base_url="https://api.x.ai/v1",
        base_url_env="XAI_API_BASE_URL",
    )
    _register(
        "GOOGLE_API_KEY",
        "google",
        "Google",
        "GOOGLE_MODEL",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        base_url_env="GOOGLE_API_BASE_URL",
    )
    _register(
        "DEEPSEEK_API_KEY",
        "deepseek",
        "DeepSeek",
        "DEEPSEEK_MODEL",
        base_url="https://api.deepseek.com",
        base_url_env="DEEPSEEK_API_BASE_URL",
    )
    _register(
        "MOONSHOT_API_KEY",
        "moonshot",
        "Moonshot",
        "MOONSHOT_MODEL",
        base_url="https://api.moonshot.cn/v1",
        base_url_env="MOONSHOT_API_BASE_URL",
    )
    _register(
        "AMAZON_API_KEY",
        "amazon",
        "Amazon",
        "AMAZON_MODEL",
        base_url_env="AMAZON_API_BASE_URL",
    )
    _register(
        "LLAMA_API_KEY",
        "meta",
        "Meta",
        "LLAMA_MODEL",
        base_url_env="LLAMA_API_BASE_URL",
    )

    return config


def get_agent_profiles(agents_dir: Path | None = None) -> list[tuple[str, str]]:
    if agents_dir is None:
        agents_dir = Path(__file__).parent.parent / "agents"
    if not agents_dir.is_dir():
        return []
    profiles: list[tuple[str, str]] = []
    for md_file in sorted(agents_dir.glob("*.md")):
        if md_file.stem.upper() in ("README", "HOW_TO_USE"):
            continue
        description = _extract_description(md_file)
        profiles.append((md_file.stem, description))
    return profiles


def load_agent_prompt(agent_name: str, agents_dir: Path | None = None) -> str | None:
    if agents_dir is None:
        agents_dir = Path(__file__).parent.parent / "agents"
    agent_file = agents_dir / f"{agent_name}.md"
    if not agent_file.is_file():
        return None
    content = agent_file.read_text(encoding="utf-8")
    return _strip_frontmatter(content)


def _extract_description(md_file: Path) -> str:
    try:
        content = md_file.read_text(encoding="utf-8")
    except OSError:
        return ""
    if not content.startswith("---"):
        return ""
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
    if not content.startswith("---"):
        return content.strip()
    end = content.find("---", 3)
    if end == -1:
        return content.strip()
    return content[end + 3 :].strip()
