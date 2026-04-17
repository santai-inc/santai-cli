"""Authentication commands for Santai Hub."""

from __future__ import annotations

import json
import socket
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Annotated
from urllib.parse import parse_qs, urlparse

import typer
from rich.console import Console

console = Console()

CREDENTIALS_DIR = Path.home() / ".config" / "santai"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"
DEFAULT_HUB_URL = "http://localhost:3000"


def _get_hub_url() -> str:
    import os

    return os.environ.get("SANTAI_HUB_URL", DEFAULT_HUB_URL)


def _save_credentials(token: str, username: str, hub_url: str) -> None:
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_FILE.write_text(
        json.dumps({"token": token, "username": username, "hub_url": hub_url}),
        encoding="utf-8",
    )
    CREDENTIALS_FILE.chmod(0o600)


def load_credentials() -> dict[str, str] | None:
    if not CREDENTIALS_FILE.is_file():
        return None
    try:
        data = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
        if "token" in data:
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _clear_credentials() -> None:
    if CREDENTIALS_FILE.is_file():
        CREDENTIALS_FILE.unlink()


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def login(
    hub_url: Annotated[
        str | None,
        typer.Option("--hub-url", help="Santai Hub URL"),
    ] = None,
) -> None:
    """Authenticate with Santai Hub via the browser."""
    hub = hub_url or _get_hub_url()
    port = _find_free_port()

    result: dict[str, str] = {}
    error: list[str] = []
    server_ready = threading.Event()
    got_callback = threading.Event()

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/callback":
                self.send_response(404)
                self.end_headers()
                return

            params = parse_qs(parsed.query)
            token = params.get("token", [None])[0]
            username = params.get("username", [None])[0]

            if not token:
                error.append("No token received")
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h2>Authentication failed.</h2>"
                    b"<p>No token received. You can close this tab.</p></body></html>"
                )
                got_callback.set()
                return

            result["token"] = token
            result["username"] = username or ""
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>Authenticated!</h2>"
                b"<p>You can close this tab and return to your terminal.</p></body></html>"
            )
            got_callback.set()

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", port), CallbackHandler)

    def run_server() -> None:
        server_ready.set()
        server.handle_request()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    server_ready.wait()

    auth_url = f"{hub}/auth/cli?callback_port={port}"
    console.print(f"Opening browser to authenticate...")
    console.print(f"  [dim]{auth_url}[/dim]\n")
    webbrowser.open(auth_url)
    console.print("Waiting for authentication (press Ctrl+C to cancel)...")

    try:
        got_callback.wait(timeout=120)
    except KeyboardInterrupt:
        console.print("\n[yellow]Login cancelled.[/yellow]")
        server.server_close()
        raise typer.Exit(1)

    server.server_close()

    if error:
        console.print(f"[red]Login failed: {error[0]}[/red]")
        raise typer.Exit(1)

    if not result.get("token"):
        console.print("[red]Login timed out. Please try again.[/red]")
        raise typer.Exit(1)

    _save_credentials(result["token"], result.get("username", ""), hub)
    console.print(f"[green]Logged in as {result.get('username', 'unknown')}[/green]")


def logout() -> None:
    """Log out of Santai Hub."""
    creds = load_credentials()
    if not creds:
        console.print("Not currently logged in.")
        return
    _clear_credentials()
    console.print("[green]Logged out successfully.[/green]")


def whoami() -> None:
    """Show the currently authenticated user."""
    creds = load_credentials()
    if not creds:
        console.print("Not logged in. Run [bold]santai login[/bold] to authenticate.")
        raise typer.Exit(1)

    hub = creds.get("hub_url", DEFAULT_HUB_URL)
    console.print(f"Logged in as [bold]{creds.get('username', 'unknown')}[/bold]")
    console.print(f"  Hub: [dim]{hub}[/dim]")
