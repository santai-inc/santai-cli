"""Push a Santai project to the cloud."""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

import typer
from rich.console import Console

from santai_cli.commands.auth import DEFAULT_HUB_URL, load_credentials
from santai_cli.core.project import is_santai_project

console = Console()

IGNORED_DIRECTORIES = {
    ".git",
    ".ruff_cache",
    ".rumdl_cache",
    "__pycache__",
    ".venv",
    "node_modules",
}

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _should_include(path: Path) -> bool:
    return not any(part in IGNORED_DIRECTORIES for part in path.parts)


def _get_backend_url(hub_url: str) -> str:
    return hub_url.replace(":3000", ":3001") if ":3000" in hub_url else hub_url


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def push(
    name: Annotated[
        str | None,
        typer.Argument(help="Project name (defaults to directory name)"),
    ] = None,
) -> None:
    """Push the current Santai project to the cloud."""
    import urllib.error
    import urllib.request

    project_dir = Path.cwd()

    if not is_santai_project(project_dir):
        console.print("[red]Error: Not a Santai project.[/red]")
        console.print(
            "[yellow]A Santai project must have resources/, codebases/, history/, "
            "and notes/ directories.[/yellow]"
        )
        raise typer.Exit(1)

    creds = load_credentials()
    if not creds:
        console.print("Not logged in. Run [bold]santai login[/bold] first.")
        raise typer.Exit(1)

    project_name = name or project_dir.name
    hub = creds.get("hub_url", DEFAULT_HUB_URL)
    backend = _get_backend_url(hub)

    console.print(f"Packaging [bold]{project_name}[/bold]...")

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(project_dir.rglob("*")):
                if not file_path.is_file():
                    continue
                rel = file_path.relative_to(project_dir)
                if not _should_include(rel):
                    continue
                zf.write(file_path, rel)

        zip_size = tmp_path.stat().st_size

        if zip_size > MAX_UPLOAD_BYTES:
            console.print(
                f"[red]Error: Archive is {_format_size(zip_size)}, "
                f"exceeds the 50 MB limit.[/red]"
            )
            raise typer.Exit(1)

        console.print(f"  Archive size: {_format_size(zip_size)}")
        console.print("Uploading...")

        zip_bytes = tmp_path.read_bytes()

        boundary = "----SantaiUploadBoundary"
        body_parts: list[bytes] = []

        body_parts.append(f"--{boundary}\r\n".encode())
        body_parts.append(
            f'Content-Disposition: form-data; name="repoZip"; filename="{quote(project_name)}.zip"\r\n'.encode()
        )
        body_parts.append(b"Content-Type: application/zip\r\n\r\n")
        body_parts.append(zip_bytes)
        body_parts.append(b"\r\n")

        body_parts.append(f"--{boundary}\r\n".encode())
        body_parts.append(
            b'Content-Disposition: form-data; name="repoName"\r\n\r\n'
        )
        body_parts.append(project_name.encode())
        body_parts.append(b"\r\n")

        body_parts.append(f"--{boundary}--\r\n".encode())

        body = b"".join(body_parts)

        req = urllib.request.Request(
            f"{backend}/santai-repos/upload",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {creds['token']}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
                console.print(
                    f"[green]Pushed [bold]{project_name}[/bold] "
                    f"({_format_size(data.get('size', zip_size))})[/green]"
                )
        except urllib.error.HTTPError as e:
            if e.code == 401:
                console.print(
                    "[yellow]Session expired. Run [bold]santai login[/bold] to re-authenticate.[/yellow]"
                )
                raise typer.Exit(1)
            body_text = e.read().decode(errors="replace")
            try:
                err_data = json.loads(body_text)
                msg = err_data.get("error", body_text)
            except json.JSONDecodeError:
                msg = body_text
            console.print(f"[red]Push failed (HTTP {e.code}): {msg}[/red]")
            raise typer.Exit(1)
        except (urllib.error.URLError, TimeoutError):
            console.print("[red]Could not reach the hub. Check your connection.[/red]")
            raise typer.Exit(1)
    finally:
        tmp_path.unlink(missing_ok=True)
