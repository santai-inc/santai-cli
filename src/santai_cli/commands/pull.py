"""Pull a Santai project from the cloud."""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from santai_cli.commands.auth import DEFAULT_HUB_URL, load_credentials

console = Console()


def _get_backend_url(hub_url: str) -> str:
    return hub_url.replace(":3000", ":3001") if ":3000" in hub_url else hub_url


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def pull(
    name: Annotated[
        str,
        typer.Argument(help="Project name to pull"),
    ],
    dest: Annotated[
        str | None,
        typer.Option("--dest", "-d", help="Destination directory"),
    ] = None,
) -> None:
    """Pull a Santai project from the cloud."""
    import urllib.error
    import urllib.request

    creds = load_credentials()
    if not creds:
        console.print("Not logged in. Run [bold]santai login[/bold] first.")
        raise typer.Exit(1)

    dest_path = Path(dest or name).resolve()

    if dest_path.exists():
        console.print(f"[red]Error: '{dest_path}' already exists.[/red]")
        raise typer.Exit(1)

    hub = creds.get("hub_url", DEFAULT_HUB_URL)
    backend = _get_backend_url(hub)

    console.print(f"Looking up [bold]{name}[/bold]...")

    req = urllib.request.Request(
        f"{backend}/santai-repos/download/{name}",
        headers={"Authorization": f"Bearer {creds['token']}"},
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            console.print(
                "[yellow]Session expired. Run [bold]santai login[/bold] to re-authenticate.[/yellow]"
            )
            raise typer.Exit(1)
        if e.code == 404:
            console.print(f"[red]Project '{name}' not found.[/red]")
            raise typer.Exit(1)
        console.print(f"[red]Pull failed (HTTP {e.code})[/red]")
        raise typer.Exit(1)
    except (urllib.error.URLError, TimeoutError):
        console.print("[red]Could not reach the hub. Check your connection.[/red]")
        raise typer.Exit(1)

    download_url = data.get("downloadUrl")
    if not download_url:
        console.print("[red]No download URL received.[/red]")
        raise typer.Exit(1)

    size = data.get("size", 0)
    console.print(f"  Found ({_format_size(size)}). Downloading...")

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        dl_req = urllib.request.Request(download_url)
        with urllib.request.urlopen(dl_req, timeout=120) as resp:
            tmp_path.write_bytes(resp.read())

        console.print("Extracting...")

        dest_path.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(tmp_path, "r") as zf:
            # Validate all members before extracting to prevent zip-slip attacks
            for member in zf.infolist():
                member_path = (dest_path / member.filename).resolve()
                if not str(member_path).startswith(str(dest_path.resolve())):
                    console.print(
                        "[red]Error: Zip contains unsafe path "
                        f"'{member.filename}'[/red]"
                    )
                    raise typer.Exit(1)
                # Reject symlinks (type_flag 'l' via external_attr or compress_type)
                if member.external_attr >> 28 == 0xA:
                    console.print(
                        f"[red]Error: Zip contains symlink '{member.filename}'[/red]"
                    )
                    raise typer.Exit(1)
            zf.extractall(dest_path)

        console.print(f"[green]Pulled [bold]{name}[/bold] to {dest_path}[/green]")
    except (urllib.error.URLError, TimeoutError):
        console.print(
            "[red]Download failed. The URL may have expired — try again.[/red]"
        )
        if dest_path.exists() and not any(dest_path.iterdir()):
            dest_path.rmdir()
        raise typer.Exit(1)
    except zipfile.BadZipFile:
        console.print("[red]Downloaded file is not a valid zip.[/red]")
        if dest_path.exists() and not any(dest_path.iterdir()):
            dest_path.rmdir()
        raise typer.Exit(1)
    finally:
        tmp_path.unlink(missing_ok=True)
