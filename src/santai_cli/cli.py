"""Santai CLI application."""

import typer

from santai_cli.commands import history, init, ui, web

app = typer.Typer(
    name="santai",
    help="Santai project management CLI",
    no_args_is_help=True,
)

app.command(name="init")(init.init)
app.command(name="history")(history.history)
app.command(name="ui")(ui.ui)
app.command(name="web")(web.web)

if __name__ == "__main__":
    app()
