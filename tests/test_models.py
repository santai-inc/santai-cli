"""Tests for live model discovery, filtering, and label rendering."""

from unittest.mock import AsyncMock, patch

import pytest

from santai_cli.core.chat import _is_openai_reasoning_model
from santai_cli.core.config import ChatConfig, ProviderConfig
from santai_cli.core.models import (
    ModelDiscoveryError,
    _filter_openai_chat_models,
    discover_models_or_fallback,
    display_label_for_model,
    populate_live_models,
    prettify_model_id,
)

# === _is_openai_reasoning_model ===


@pytest.mark.parametrize(
    "model",
    [
        "o1",
        "o1-mini",
        "o1-preview",
        "o1-pro",
        "o3",
        "o3-mini",
        "o4-mini",
        "gpt-5",
        "gpt-5-mini",
        "gpt-5-nano",
        "gpt-5-pro",
    ],
)
def test_is_openai_reasoning_model_true(model: str) -> None:
    assert _is_openai_reasoning_model(model) is True


@pytest.mark.parametrize(
    "model",
    [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4.1",
        "gpt-4.1-mini",
        "chatgpt-4o-latest",
        "gpt-3.5-turbo",
        "claude-sonnet-4-6",
        "openai-something",
    ],
)
def test_is_openai_reasoning_model_false(model: str) -> None:
    assert _is_openai_reasoning_model(model) is False


# === _filter_openai_chat_models ===


def test_filter_keeps_only_allowlisted() -> None:
    catalog = [
        # In allowlist
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4.1",
        "gpt-5-mini",
        "o3-mini",
        "o4-mini",
        # Out of allowlist (should all be dropped)
        "gpt-5",  # not in allowlist (failed on test account)
        "gpt-5-pro",  # Responses API only
        "gpt-5-codex",
        "gpt-5-search-api",
        "gpt-3.5-turbo",
        "gpt-3.5-turbo-instruct",
        "gpt-4",
        "gpt-4-turbo",
        "gpt-4o-realtime-preview",
        "gpt-4o-audio-preview",
        "gpt-4o-2024-11-20",  # dated snapshot
        "o1-pro",
        "tts-1",
        "dall-e-3",
        "text-embedding-3-small",
    ]
    result = _filter_openai_chat_models(catalog)

    assert set(result) == {
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4.1",
        "gpt-5-mini",
        "o3-mini",
        "o4-mini",
    }


def test_filter_returns_sorted_descending() -> None:
    result = _filter_openai_chat_models(["gpt-4o", "o3-mini", "gpt-4.1"])
    assert result == sorted(result, reverse=True)


def test_filter_empty_input() -> None:
    assert _filter_openai_chat_models([]) == []


# === populate_live_models ===


@pytest.mark.asyncio
async def test_populate_success_default_in_catalog_keeps_default() -> None:
    cfg = ChatConfig(
        providers={
            "p": ProviderConfig(
                name="P", api_key="k", model="m1", available_models=["fb1"]
            )
        }
    )
    with patch(
        "santai_cli.core.models.discover_models",
        new=AsyncMock(return_value=["m1", "m2", "m3"]),
    ):
        await populate_live_models(cfg)

    pc = cfg.providers["p"]
    assert pc.model == "m1"
    assert pc.available_models == ["m1", "m2", "m3"]


@pytest.mark.asyncio
async def test_populate_success_default_missing_repoints_default() -> None:
    """Common with proxies that don't serve the env-var configured default."""
    cfg = ChatConfig(
        providers={
            "p": ProviderConfig(
                name="P", api_key="k", model="gpt-4o", available_models=["fb1"]
            )
        }
    )
    with patch(
        "santai_cli.core.models.discover_models",
        new=AsyncMock(return_value=["gpt-5big-santai", "gpt-5.5"]),
    ):
        await populate_live_models(cfg)

    pc = cfg.providers["p"]
    assert pc.model == "gpt-5big-santai"  # repointed to first discovered
    assert pc.available_models == ["gpt-5big-santai", "gpt-5.5"]
    assert "gpt-4o" not in pc.available_models  # no phantom entry


@pytest.mark.asyncio
async def test_populate_failure_default_in_fallback_kept() -> None:
    cfg = ChatConfig(
        providers={
            "p": ProviderConfig(
                name="P",
                api_key="k",
                model="fb1",
                available_models=["fb1", "fb2"],
            )
        }
    )
    with patch(
        "santai_cli.core.models.discover_models",
        new=AsyncMock(side_effect=ModelDiscoveryError("unavailable")),
    ):
        await populate_live_models(cfg)

    pc = cfg.providers["p"]
    assert pc.model == "fb1"
    assert pc.available_models == ["fb1", "fb2"]


@pytest.mark.asyncio
async def test_populate_failure_default_missing_prepended_to_fallback() -> None:
    """Discovery failed, env-var default not in hardcoded list — prepend it."""
    cfg = ChatConfig(
        providers={
            "p": ProviderConfig(
                name="P",
                api_key="k",
                model="custom-model",
                available_models=["fb1"],
            )
        }
    )
    with patch(
        "santai_cli.core.models.discover_models",
        new=AsyncMock(side_effect=ModelDiscoveryError("unavailable")),
    ):
        await populate_live_models(cfg)

    pc = cfg.providers["p"]
    assert pc.model == "custom-model"
    assert pc.available_models == ["custom-model", "fb1"]


@pytest.mark.asyncio
async def test_populate_no_providers_is_noop() -> None:
    cfg = ChatConfig(providers={})
    await populate_live_models(cfg)
    assert cfg.providers == {}


@pytest.mark.asyncio
async def test_populate_runs_providers_concurrently() -> None:
    """Two providers with both succeeding should each get their own catalog."""
    cfg = ChatConfig(
        providers={
            "anthropic": ProviderConfig(
                name="A", api_key="k", model="claude", available_models=["claude"]
            ),
            "openai": ProviderConfig(
                name="O", api_key="k", model="gpt-4o", available_models=["gpt-4o"]
            ),
        }
    )

    async def fake_discover(name: str, pc: ProviderConfig, *, timeout: float = 5.0):
        return ["claude", "claude-opus"] if name == "anthropic" else ["gpt-4o"]

    with patch("santai_cli.core.models.discover_models", new=fake_discover):
        await populate_live_models(cfg)

    assert cfg.providers["anthropic"].available_models == ["claude", "claude-opus"]
    assert cfg.providers["openai"].available_models == ["gpt-4o"]


# === discover_models_or_fallback ===


@pytest.mark.asyncio
async def test_discover_or_fallback_returns_models_on_success() -> None:
    pc = ProviderConfig(name="O", api_key="k", model="gpt-4o", available_models=["fb"])
    with patch(
        "santai_cli.core.models.discover_models",
        new=AsyncMock(return_value=["gpt-4o", "gpt-4.1"]),
    ):
        models, err = await discover_models_or_fallback("openai", pc)
    assert models == ["gpt-4o", "gpt-4.1"]
    assert err is None


@pytest.mark.asyncio
async def test_discover_or_fallback_returns_hardcoded_on_invalid_key() -> None:
    pc = ProviderConfig(
        name="O", api_key="k", model="gpt-4o", available_models=["fb1", "fb2"]
    )
    with patch(
        "santai_cli.core.models.discover_models",
        new=AsyncMock(side_effect=ModelDiscoveryError("invalid_key")),
    ):
        models, err = await discover_models_or_fallback("openai", pc)
    assert models == ["fb1", "fb2"]
    assert err == "invalid_key"


# === display_label_for_model / prettify_model_id ===


@pytest.mark.parametrize(
    "model_id,expected",
    [
        ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
        ("claude-haiku-4-5-20251001", "Claude Haiku 4.5"),
        ("gpt-4o", "GPT-4o"),
        ("o3-mini", "o3-mini"),
        ("us.amazon.nova-pro-v1:0", "Nova Pro"),
        ("novapro-bedrock", "Nova Pro"),
    ],
)
def test_display_label_known_ids(model_id: str, expected: str) -> None:
    assert display_label_for_model(model_id) == expected


def test_display_label_unknown_id_uses_prettifier() -> None:
    # Falls through to prettify_model_id
    assert display_label_for_model("some-unknown-proxy-model") == (
        "Some Unknown Proxy Model"
    )


@pytest.mark.parametrize(
    "model_id,expected",
    [
        ("claude-3-5-haiku-20241022", "Claude Haiku 3.5"),
        ("claude-3-7-sonnet-20250219", "Claude Sonnet 3.7"),
        ("anthropic-claude-bedrock4.5-haiku", "Claude Haiku 4.5"),
        ("gemini-2.5-pro", "Gemini 2.5 Pro"),
        ("gpt-4o-2024-11-20", "GPT 4o"),
    ],
)
def test_prettify_model_id(model_id: str, expected: str) -> None:
    assert prettify_model_id(model_id) == expected
