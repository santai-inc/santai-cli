"""Helpers for communicating with the Santai Hub backend."""

from __future__ import annotations

import json
import logging
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

try:
    _CLI_VERSION = version("santai-cli")
except PackageNotFoundError:
    _CLI_VERSION = "0.0.0"

USER_AGENT = f"santai-cli/{_CLI_VERSION}"

# Directories that hold user-created content — prefer these as the headline file.
_CONTENT_DIRS: frozenset[str] = frozenset({"media", "notes"})

# Boilerplate filenames that should never be the headline even when added.
_SCAFFOLD_NAMES: frozenset[str] = frozenset(
    {
        ".env.example",
        ".gitignore",
        ".eslintrc",
        ".prettierrc",
        ".editorconfig",
        "requirements.txt",
        "requirements-dev.txt",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "makefile",
        "dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "setup.py",
        "pyproject.toml",
        "setup.cfg",
        "tsconfig.json",
        "vite.config.js",
        "vite.config.ts",
        "claude.md",
    }
)


def _headline_sort_key(path_str: str) -> tuple[int, int, str]:
    """Sort key that surfaces user content files before scaffolding/dotfiles."""
    p = Path(path_str)
    name_lower = p.name.lower()
    in_content_dir = bool(p.parts) and p.parts[0] in _CONTENT_DIRS
    is_low_priority = name_lower.startswith(".") or name_lower in _SCAFFOLD_NAMES
    tier = 0 if in_content_dir else (2 if is_low_priority else 1)
    return (tier, len(p.parts), name_lower)


def get_backend_url(hub_url: str) -> str:
    if ":3000" in hub_url:
        return hub_url.replace(":3000", ":3001")
    # Production hub: API routes live under /api
    return hub_url.rstrip("/") + "/api"


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
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return str(data["id"]) if "id" in data else None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None


def fetch_prev_files(
    backend: str, token: str, base_id: str, image_exts: set[str]
) -> tuple[set[str], dict[str, str]]:
    """Return (all_paths, text_content) from the latest cloud save for diffing.

    Falls back to empty sets/dicts on any error so callers can treat it as
    'no previous save' without crashing.
    """
    import urllib.error
    import urllib.request

    auth = {"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}

    # 1. Get the latest save key from the cloud-saves list
    try:
        saves_req = urllib.request.Request(
            f"{backend}/ai/edit/cloud-saves/{base_id}", headers=auth
        )
        with urllib.request.urlopen(saves_req, timeout=15) as resp:
            data = json.loads(resp.read())
        saves = (
            data if isinstance(data, list) else data.get("saves", data.get("data", []))
        )
        if not saves:
            return set(), {}
        latest_key = saves[0].get("key")
        if not latest_key:
            return set(), {}
    except Exception:
        logging.debug("fetch_prev_files: failed to fetch saves list", exc_info=True)
        return set(), {}

    # 2. Load file content for that save
    try:
        load_req = urllib.request.Request(
            f"{backend}/ai/edit/load-from-cloud",
            data=json.dumps({"manifestKey": latest_key}).encode(),
            method="POST",
            headers={**auth, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(load_req, timeout=60) as resp:
            result = json.loads(resp.read())
        if not result.get("success"):
            return set(), {}
        files: list = result.get("files", [])
        all_paths = {f["path"] for f in files if f.get("path")}
        text_content = {
            f["path"]: f.get("content", "")
            for f in files
            if f.get("path") and Path(f["path"]).suffix.lower() not in image_exts
        }
        return all_paths, text_content
    except Exception:
        logging.debug("fetch_prev_files: failed to load file content", exc_info=True)
        return set(), {}


def make_diff_title(
    prev_paths: set[str],
    curr_paths: set[str],
    prev_text: dict[str, str],
    curr_text: dict[str, str],
) -> str:
    """Generate a human-readable summary of what changed between two file snapshots."""
    added = sorted(curr_paths - prev_paths, key=_headline_sort_key)
    deleted = sorted(prev_paths - curr_paths, key=_headline_sort_key)
    modified = sorted(
        (
            p
            for p in curr_paths & prev_paths
            if p in prev_text and p in curr_text and curr_text[p] != prev_text[p]
        ),
        key=_headline_sort_key,
    )

    # Flatten all changes; headline is the first, the rest become "and N more".
    all_changes = (
        [("Add", p) for p in added]
        + [("Update", p) for p in modified]
        + [("Delete", p) for p in deleted]
    )
    if not all_changes:
        return ""
    verb, first = all_changes[0]
    label = Path(first).name
    rest = len(all_changes) - 1
    return f"{verb} {label}" if not rest else f"{verb} {label} and {rest} more"


def resolve_base_id(backend: str, token: str, name: str, username: str) -> str | None:
    """Return the base ID for the authenticated user's base with the given name."""
    import urllib.error
    import urllib.request
    from urllib.parse import quote

    req = urllib.request.Request(
        f"{backend}/bases?author={quote(username)}",
        headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None

    for base in data.get("data", []):
        if base.get("name") == name:
            return str(base["id"])
    return None
