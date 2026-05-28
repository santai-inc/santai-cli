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
from santai_cli.core.hub import (
    USER_AGENT,
    create_base,
    fetch_prev_files,
    get_backend_url,
    make_diff_title,
    resolve_base_id,
)
from santai_cli.core.project import (
    IGNORED_DIRECTORIES,
    IMAGE_EXTENSIONS,
    SENSITIVE_FILES,
)

console = Console()

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _should_include(path: Path, ignored_files: set[str]) -> bool:
    return (
        not any(part in IGNORED_DIRECTORIES for part in path.parts)
        and path.name not in ignored_files
    )


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
    include_env: Annotated[
        bool,
        typer.Option(
            "--include-env",
            help="Include .env file in the upload (contains API keys)",
        ),
    ] = False,
) -> None:
    """Push the current Santai project to the cloud."""
    import urllib.error
    import urllib.request

    project_dir = Path.cwd()

    creds = load_credentials()
    if not creds:
        console.print("Not logged in. Run [bold]santai login[/bold] first.")
        raise typer.Exit(1)

    # Determine which files to exclude
    ignored_files = set(SENSITIVE_FILES)
    env_path = project_dir / ".env"
    if not include_env and env_path.is_file():
        include_env = typer.confirm(
            "A .env file was found (may contain API keys). Include it in the upload?",
            default=False,
        )
    if include_env:
        ignored_files.discard(".env")

    project_name = name or project_dir.name
    hub = creds.get("hub_url", DEFAULT_HUB_URL)
    backend = get_backend_url(hub)

    console.print(f"Looking up [bold]{project_name}[/bold]...")

    base_id = resolve_base_id(
        backend, creds["token"], project_name, creds.get("username", "")
    )
    if not base_id:
        console.print(f"  Not found — creating [bold]{project_name}[/bold]...")
        base_id = create_base(backend, creds["token"], project_name)
        if not base_id:
            console.print(f"[red]Failed to create project '{project_name}'.[/red]")
            raise typer.Exit(1)

    # Fetch previous save for diff title generation
    prev_paths, prev_text = fetch_prev_files(
        backend, creds["token"], base_id, IMAGE_EXTENSIONS
    )

    console.print(f"Packaging [bold]{project_name}[/bold]...")

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        curr_paths: set[str] = set()
        curr_text: dict[str, str] = {}

        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(project_dir.rglob("*")):
                if not file_path.is_file():
                    continue
                rel = file_path.relative_to(project_dir)
                if not _should_include(rel, ignored_files):
                    continue
                rel_str = str(rel)
                curr_paths.add(rel_str)
                zf.write(file_path, rel)
                if file_path.suffix.lower() not in IMAGE_EXTENSIONS:
                    try:
                        curr_text[rel_str] = file_path.read_text(errors="replace")
                    except Exception:
                        curr_text[rel_str] = ""

        zip_size = tmp_path.stat().st_size

        if zip_size > MAX_UPLOAD_BYTES:
            console.print(
                f"[red]Error: Archive is {_format_size(zip_size)}, "
                f"exceeds the 50 MB limit.[/red]"
            )
            raise typer.Exit(1)

        console.print(f"  Archive size: {_format_size(zip_size)}")
        console.print("Uploading...")

        diff = make_diff_title(prev_paths, curr_paths, prev_text, curr_text)
        n = len(curr_paths)
        _snap = f"Snapshot · {n} file{'s' if n != 1 else ''}"
        push_title = diff if diff else ("Initial push" if not prev_paths else _snap)

        zip_bytes = tmp_path.read_bytes()

        boundary = "----SantaiUploadBoundary"
        body_parts: list[bytes] = []

        def _field(field_name: str, value: str) -> list[bytes]:
            return [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{field_name}"\r\n\r\n'.encode(),
                value.encode(),
                b"\r\n",
            ]

        body_parts.extend(_field("title", push_title))
        body_parts.append(f"--{boundary}\r\n".encode())
        filename = f"{quote(project_name)}.zip"
        body_parts.append(
            f'Content-Disposition: form-data; name="file"; '
            f'filename="{filename}"\r\n'.encode()
        )
        body_parts.append(b"Content-Type: application/zip\r\n\r\n")
        body_parts.append(zip_bytes)
        body_parts.append(b"\r\n")
        body_parts.append(f"--{boundary}--\r\n".encode())

        body = b"".join(body_parts)

        req = urllib.request.Request(
            f"{backend}/bases/{base_id}/upload",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {creds['token']}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": USER_AGENT,
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
                console.print(
                    f"[green]Pushed [bold]{project_name}[/bold] "
                    f"(version {data.get('version', '?')})[/green]"
                )
        except urllib.error.HTTPError as e:
            if e.code == 401:
                console.print(
                    "[yellow]Session expired. Run [bold]santai login[/bold] "
                    "to re-authenticate.[/yellow]"
                )
                raise typer.Exit(1) from e
            body_text = e.read().decode(errors="replace")
            try:
                err_data = json.loads(body_text)
                msg = err_data.get("error", body_text)
            except json.JSONDecodeError:
                msg = body_text
            console.print(f"[red]Push failed (HTTP {e.code}): {msg}[/red]")
            raise typer.Exit(1) from e
        except (urllib.error.URLError, TimeoutError) as e:
            console.print("[red]Could not reach the hub. Check your connection.[/red]")
            raise typer.Exit(1) from e
    finally:
        tmp_path.unlink(missing_ok=True)
