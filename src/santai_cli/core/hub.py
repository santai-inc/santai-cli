"""Helpers for communicating with the Santai Hub backend."""

from __future__ import annotations

import json
from urllib.parse import urlencode


def get_backend_url(hub_url: str) -> str:
    return hub_url.replace(":3000", ":3001") if ":3000" in hub_url else hub_url


def resolve_base_id(backend: str, token: str, username: str, name: str) -> str | None:
    """Return the base ID for (username, name), or None if not found."""
    import urllib.error
    import urllib.request

    qs = urlencode({"author": username, "search": name, "limit": "20"})
    req = urllib.request.Request(
        f"{backend}/bases/?{qs}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None

    for base in data.get("data", []):
        if base.get("name") == name and base.get("author") == username:
            return str(base["id"])
    return None
