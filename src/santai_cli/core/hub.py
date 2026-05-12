"""Helpers for communicating with the Santai Hub backend."""

from __future__ import annotations

import json


def get_backend_url(hub_url: str) -> str:
    return hub_url.replace(":3000", ":3001") if ":3000" in hub_url else hub_url


def create_base(backend: str, token: str, name: str) -> str | None:
    """Create a new base with the given name and return its ID, or None on failure."""
    import urllib.error
    import urllib.request

    body = json.dumps({"name": name}).encode()
    req = urllib.request.Request(
        f"{backend}/bases/init",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return str(data["id"]) if "id" in data else None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None


def resolve_base_id(backend: str, token: str, name: str) -> str | None:
    """Return the base ID for the authenticated user's base with the given name."""
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        f"{backend}/me/bases",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None

    for base in data.get("bases", []):
        if base.get("name") == name:
            return str(base["id"])
    return None
