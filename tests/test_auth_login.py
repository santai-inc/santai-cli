"""Tests for the login code exchange that keeps the session token out of the URL."""

import base64
import hashlib
import json
from io import BytesIO
from unittest.mock import patch

import pytest

from santai_cli.commands.auth import complete_callback, exchange_code, new_pkce_pair


class _Response(BytesIO):
    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _reply(payload: dict[str, object]) -> _Response:
    return _Response(json.dumps(payload).encode())


def test_exchange_code_posts_the_code_with_the_verifier() -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(req: object, timeout: int = 0) -> _Response:
        captured["url"] = req.full_url  # type: ignore[attr-defined]
        captured["method"] = req.get_method()  # type: ignore[attr-defined]
        captured["body"] = req.data  # type: ignore[attr-defined]
        return _reply({"token": "sess-token", "user": {"username": "ada"}})

    with patch("urllib.request.urlopen", fake_urlopen):
        creds = exchange_code("https://hub.sant.ai/", "one-time-code", "the-verifier")

    assert creds == {"token": "sess-token", "username": "ada"}
    assert captured["method"] == "POST"
    assert captured["url"] == "https://hub.sant.ai/api/auth/cli/exchange"
    body = captured["body"]
    assert isinstance(body, bytes)
    assert json.loads(body) == {
        "code": "one-time-code",
        "code_verifier": "the-verifier",
    }


# get_backend_url() would strip a local hub to :3001, where this route is not mounted.
def test_exchange_code_keeps_the_api_prefix_for_a_local_hub() -> None:
    seen: list[str] = []

    def fake_urlopen(req: object, timeout: int = 0) -> _Response:
        seen.append(req.full_url)  # type: ignore[attr-defined]
        return _reply({"token": "t", "user": {"username": "ada"}})

    with patch("urllib.request.urlopen", fake_urlopen):
        exchange_code("http://localhost:3000", "c", "v")

    assert seen == ["http://localhost:3000/api/auth/cli/exchange"]


def test_exchange_code_rejects_a_reply_with_no_token() -> None:
    reply = lambda req, timeout=0: _reply({"user": {}})  # noqa: E731
    with patch("urllib.request.urlopen", reply), pytest.raises(ValueError):
        exchange_code("https://hub.sant.ai", "spent-code", "v")


def test_callback_exchanges_the_code_it_was_handed() -> None:
    reply = lambda req, timeout=0: _reply(  # noqa: E731
        {"token": "sess-token", "user": {"username": "ada"}}
    )
    with patch("urllib.request.urlopen", reply):
        creds = complete_callback("code=one-time-code", "https://hub.sant.ai", "v")

    assert creds == {"token": "sess-token", "username": "ada"}


# The pre-PKCE callback carried the session token itself. Honouring that again would let
# anything that can reach the loopback port choose the token we save.
def test_callback_refuses_a_token_in_the_query_string() -> None:
    def never_called(req: object, timeout: int = 0) -> _Response:
        raise AssertionError("the exchange endpoint should not be reached")

    with (
        patch("urllib.request.urlopen", never_called),
        pytest.raises(ValueError, match="no login code"),
    ):
        complete_callback(
            "token=attacker-session&username=ada", "https://hub.sant.ai", "v"
        )


def test_callback_reports_a_failed_exchange_rather_than_raising_oserror() -> None:
    def boom(req: object, timeout: int = 0) -> _Response:
        raise OSError("connection refused")

    with (
        patch("urllib.request.urlopen", boom),
        pytest.raises(ValueError, match="could not exchange the login code"),
    ):
        complete_callback("code=c", "https://hub.sant.ai", "v")


def test_pkce_challenge_is_the_sha256_of_the_verifier() -> None:
    verifier, challenge = new_pkce_pair()

    digest = hashlib.sha256(verifier.encode()).digest()
    assert challenge == base64.urlsafe_b64encode(digest).decode().rstrip("=")
    # The hub pins both: 43 base64url characters for the challenge, RFC 7636's floor
    # of 43 for the verifier.
    assert len(challenge) == 43
    assert 43 <= len(verifier) <= 128
    assert verifier != new_pkce_pair()[0]
