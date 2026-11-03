"""Atlas command line interface."""

import typer

from atlas.cms import app as cms_app
from atlas.notebook_cli import app as notebook_app
from atlas.pdf_cli import app as pdf_app
from atlas.vault import app as vault_app

app = typer.Typer(
    no_args_is_help=True,
    help="Atlas tools.",
    pretty_exceptions_show_locals=False,
)
app.add_typer(vault_app, name="vault")
app.add_typer(cms_app, name="cms")
app.add_typer(notebook_app, name="notebook")
app.add_typer(pdf_app, name="pdf")


def main() -> None:
    app()
