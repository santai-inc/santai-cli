"""Live model discovery shared by the CLI, TUI, and web UI."""

import asyncio
import logging
import re

import anthropic
import httpx
import openai

from santai_cli.core.config import ChatConfig, ProviderConfig

logger = logging.getLogger(__name__)

# Strict allowlist: OpenAI's catalog ships many variants that fail in subtle
# ways (search-preview/codex/instruct/realtime/audio/o1-pro, gpt-3.5-turbo's
# 4096 output cap). Add a model only after verifying it works with chat
# completions, tools, and an 8192-token output cap.
_OPENAI_CHAT_ALLOWLIST: set[str] = {
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4o",
    "gpt-4o-mini",
    "chatgpt-4o-latest",
    "o1",
    "o1-mini",
    "o3",
    "o3-mini",
    "o4-mini",
}

# Proxy models that misbehave with this CLI's tool-use loop.
_PROXY_BLOCKED_MODELS: set[str] = {
    "deepseekr1-bedrock",  # fakes tool calls as plain text
    "llama3.3-bedrock",  # fakes tool calls as plain text
    "llama3.1-bedrock",  # no tool use in streaming mode
    "llama3.2-1B-bedrock",  # no tool use in streaming mode
    "qwen3-coder-bedrock",  # invalid model identifier
    "jamba.2-bedrock",  # deprecated
    "grok2-xai",  # deprecated
}


def _filter_openai_chat_models(model_ids: list[str]) -> list[str]:
    return sorted(
        (mid for mid in model_ids if mid in _OPENAI_CHAT_ALLOWLIST),
        reverse=True,
    )


class ModelDiscoveryError(Exception):
    """Raised on live model discovery failure; `kind` is invalid_key/unavailable."""

    def __init__(self, kind: str, message: str = "") -> None:
        super().__init__(message or kind)
        self.kind = kind


async def discover_models(
    provider_name: str,
    pc: ProviderConfig,
    *,
    timeout: float = 5.0,
) -> list[str]:
    """Return the live, filtered model catalog for a provider.

    Raises ModelDiscoveryError on failure. For proxy providers (base_url set)
    the proxy's /v1/models endpoint is used.
    """
    if pc.base_url:
        try:
            base = pc.base_url.rstrip("/")
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(
                    f"{base}/v1/models",
                    headers={"Authorization": f"Bearer {pc.api_key}"},
                )
                resp.raise_for_status()
                ids = [m["id"] for m in resp.json().get("data", [])]
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                raise ModelDiscoveryError("invalid_key") from e
            raise ModelDiscoveryError("unavailable") from e
        except Exception as e:
            raise ModelDiscoveryError("unavailable") from e

        if not ids:
            raise ModelDiscoveryError("unavailable")
        return [m for m in ids if m not in _PROXY_BLOCKED_MODELS]

    if provider_name == "anthropic":
        try:
            client = anthropic.AsyncAnthropic(api_key=pc.api_key)
            page = await client.models.list(limit=100)
            return [m.id for m in page.data]
        except anthropic.AuthenticationError as e:
            raise ModelDiscoveryError("invalid_key") from e
        except Exception as e:
            raise ModelDiscoveryError("unavailable") from e

    if provider_name == "openai":
        try:
            client = openai.AsyncOpenAI(api_key=pc.api_key)
            page = await client.models.list()
            return _filter_openai_chat_models([m.id for m in page.data])
        except openai.AuthenticationError as e:
            raise ModelDiscoveryError("invalid_key") from e
        except Exception as e:
            raise ModelDiscoveryError("unavailable") from e

    return pc.available_models


async def discover_models_or_fallback(
    provider_name: str,
    pc: ProviderConfig,
    *,
    timeout: float = 5.0,
) -> tuple[list[str], str | None]:
    """Like discover_models but returns (models, error_kind) instead of raising.

    On failure, returns (pc.available_models, "invalid_key" | "unavailable").
    """
    try:
        return await discover_models(provider_name, pc, timeout=timeout), None
    except ModelDiscoveryError as e:
        logger.debug("Model discovery failed for %s (%s)", provider_name, e.kind)
        return pc.available_models, e.kind


async def populate_live_models(config: ChatConfig) -> None:
    """Replace each provider's available_models with its live catalog.

    Runs providers concurrently; per-provider failures fall back silently.
    The configured default model is kept at the front of the list so the
    /model picker always has something to mark as default.
    """
    providers = list(config.providers.items())
    if not providers:
        return
    results = await asyncio.gather(
        *(discover_models_or_fallback(name, pc) for name, pc in providers)
    )
    for (_, pc), (models, _err) in zip(providers, results, strict=True):
        if models:
            if pc.model and pc.model not in models:
                models = [pc.model, *models]
            pc.available_models = models


def display_label_for_model(model_id: str) -> str:
    """Human-readable label for a model ID; falls back to prettify_model_id."""
    return _MODEL_DISPLAY_NAMES.get(model_id) or prettify_model_id(model_id)


_MODEL_DISPLAY_NAMES: dict[str, str] = {
    "claude-opus-4-7": "Claude Opus 4.7",
    "claude-sonnet-4-6": "Claude Sonnet 4.6",
    "claude-haiku-4-5-20251001": "Claude Haiku 4.5",
    "claude-3-7-sonnet-20250219": "Claude Sonnet 3.7",
    "claude-3-5-sonnet-20241022": "Claude Sonnet 3.5",
    "claude-3-5-haiku-20241022": "Claude Haiku 3.5",
    "anthropic-4.5": "Claude Sonnet 4.5",
    "anthropic-claude-bedrock4.5": "Claude Sonnet 4.5",
    "anthropic-claude-bedrock4.6": "Claude Sonnet 4.6",
    "anthropic-claude-bedrock4.6opus": "Claude Opus 4.6",
    "anthropic-claude-bedrock4.7opus": "Claude Opus 4.7",
    "anthropic-claude-bedrock4.5-haiku": "Claude Haiku 4.5",
    "anthropic-claude-opus-4.5-bedrock": "Claude Opus 4.5",
    "anthropic-claude-bedrock4.0": "Claude Sonnet 4.5",
    "anthropic-claude-bedrock3.7": "Claude Sonnet 4.5",
    "us.amazon.nova-pro-v1:0": "Nova Pro",
    "novapro-bedrock": "Nova Pro",
    "grok3-xai": "Grok 3",
    "gemini-flash-2": "Gemini 2.0 Flash",
    "gemini-3": "Gemini 3 Pro Preview",
    "Kimi-K2.5": "Kimi K2.5",
    "gpt-4o": "GPT-4o",
    "gpt-4o-mini": "GPT-4o mini",
    "gpt-4.1": "GPT-4.1",
    "gpt-4.1-mini": "GPT-4.1 mini",
    "gpt-4.1-nano": "GPT-4.1 nano",
    "chatgpt-4o-latest": "GPT-4o",
    "o1": "o1",
    "o1-mini": "o1-mini",
    "o1-preview": "o1-preview",
    "o3": "o3",
    "o3-mini": "o3-mini",
    "o4-mini": "o4-mini",
    "gpt-5big-santai": "GPT-5",
    "gpt-5.4-santai": "GPT-5.4",
    "gpt-5mini-santai": "GPT-5 Mini",
    "gpt-5.5": "GPT-5.5",
    "gpt-5.5-pro": "GPT-5.5 Pro",
}

_ACRONYMS = {"gpt", "xai", "ai", "llm", "aws", "us"}
_NOISE = {"anthropic", "bedrock", "amazon"}


def prettify_model_id(model_id: str) -> str:
    """Convert a raw model ID to a human-readable label.

    'anthropic-claude-bedrock4.5-haiku' -> 'Claude Haiku 4.5'
    'claude-3-5-haiku-20241022'         -> 'Claude Haiku 3.5'
    'us.amazon.nova-pro-v1:0'           -> 'Nova Pro'
    """
    model_id = re.sub(r":\d+$", "", model_id)
    model_id = re.sub(r"-\d{8}$", "", model_id)
    model_id = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", model_id)
    model_id = re.sub(r"-latest$", "", model_id)

    raw_parts: list[str] = []
    for seg in re.split(r"[-_]", model_id):
        if (
            "." in seg
            and not re.match(r"^(v?\d|bedrock)", seg, re.IGNORECASE)
            and not re.search(r"\d\.", seg)
        ):
            raw_parts.extend(seg.split("."))
        else:
            raw_parts.append(seg)

    # Collapse consecutive single-digit numerics into a dotted version:
    # ['claude','3','5','haiku'] -> ['claude','3.5','haiku']
    collapsed: list[str] = []
    i = 0
    while i < len(raw_parts):
        if (
            re.fullmatch(r"\d", raw_parts[i])
            and i + 1 < len(raw_parts)
            and re.fullmatch(r"\d+", raw_parts[i + 1])
        ):
            collapsed.append(f"{raw_parts[i]}.{raw_parts[i + 1]}")
            i += 2
        else:
            collapsed.append(raw_parts[i])
            i += 1
    raw_parts = collapsed

    words: list[str] = []
    trailing_versions: list[str] = []
    is_claude = bool(raw_parts) and raw_parts[0].lower() == "claude"
    for part in raw_parts:
        if not part:
            continue
        low = part.lower()
        if low in _NOISE:
            continue
        bm = re.match(r"^bedrock([\d.]+)([a-zA-Z]*)$", part, re.IGNORECASE)
        if bm:
            trailing_versions.append(bm.group(1))
            if bm.group(2):
                words.append(bm.group(2).capitalize())
            continue
        if re.match(r"^v?\d", low):
            if is_claude:
                trailing_versions.append(part)
            else:
                words.append(part)
            continue
        am = re.match(r"^([a-zA-Z]+)(\d.*)$", part)
        if am:
            prefix, ver = am.group(1), am.group(2)
            words.append(
                prefix.upper() if prefix.lower() in _ACRONYMS else prefix.capitalize()
            )
            words.append(ver)
            continue
        if low in _ACRONYMS:
            words.append(part.upper())
        else:
            words.append(part.capitalize())
    return " ".join(words + trailing_versions)
