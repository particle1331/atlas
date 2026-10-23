"""Atlas command line interface."""

import typer

from atlas.vault import app as vault_app

app = typer.Typer(
    no_args_is_help=True,
    help="Atlas tools.",
    pretty_exceptions_show_locals=False,
)
app.add_typer(vault_app, name="vault")


def main() -> None:
    app()
