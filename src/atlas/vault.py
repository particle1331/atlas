"""Manage local secrets through the system keyring."""

import re
import sys
import warnings
from collections.abc import Callable
from getpass import GetPassWarning
from pathlib import Path
from typing import Annotated, NoReturn

import keyring
import typer
from dotenv.parser import parse_stream
from keyring.backend import KeyringBackend
from keyring.backends.fail import Keyring as FailKeyring
from keyring.backends.null import Keyring as NullKeyring

SERVICE_NAME = "atlas.vault"
ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")

app = typer.Typer(no_args_is_help=True, help="Store secrets in your system keyring.")
Name = Annotated[str, typer.Argument(help="Name of the secret, such as API_TOKEN.")]


def _fail(message: str, code: int = 2) -> NoReturn:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code)


def _backend() -> KeyringBackend:
    try:
        backend = keyring.get_keyring()
    except Exception as error:
        _fail(
            f"Could not initialize the system keyring ({type(error).__name__}). "
            "Run `keyring diagnose` to inspect its configuration."
        )
    if isinstance(backend, (FailKeyring, NullKeyring)):
        _fail("No usable keyring is configured. Run `keyring diagnose` for details.")
    return backend


def _call_keyring[T](function: Callable[..., T], *args: str) -> T:
    try:
        return function(SERVICE_NAME, *args)
    except Exception as error:
        # Backend exception messages can contain credentials. Report only the type.
        _fail(
            f"System keyring operation failed ({type(error).__name__}). "
            "Run `keyring diagnose` to inspect its configuration."
        )


def _expected_names(manifest: Path) -> list[str]:
    names: dict[str, None] = {}
    try:
        with manifest.open(encoding="utf-8-sig") as stream:
            for binding in parse_stream(stream):
                if binding.error:
                    _fail(f"Invalid .env syntax at {manifest}:{binding.original.line}.")
                if binding.key is None:
                    continue
                if ENV_NAME.fullmatch(binding.key) is None:
                    _fail(
                        f"Invalid environment variable name at "
                        f"{manifest}:{binding.original.line}."
                    )
                names[binding.key] = None
    except (OSError, UnicodeError):
        _fail(f"Could not read {manifest}. Check that the file exists and is UTF-8.")
    return list(names)


@app.command("get")
def get_secret(name: Name) -> None:
    """Write a stored secret to stdout."""
    value = _call_keyring(_backend().get_password, name)
    if value is None:
        _fail(f"Secret {name!r} was not found.", code=1)
    typer.echo(value, nl=sys.stdout.isatty() and not value.endswith("\n"))


@app.command("set")
def set_secret(
    name: Name,
    from_stdin: Annotated[
        bool,
        typer.Option("--stdin", help="Read the value from stdin instead of prompting."),
    ] = False,
) -> None:
    """Create or replace a secret using a hidden prompt or stdin."""
    backend = _backend()
    if from_stdin:
        value = sys.stdin.read()
        # Accommodate line-oriented input while preserving other whitespace.
        value = value.removesuffix("\n").removesuffix("\r")
    else:
        if not sys.stdin.isatty():
            _fail(
                "A terminal is required for hidden input. Use --stdin for piped input."
            )
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", GetPassWarning)
                value = typer.prompt(
                    "Secret", hide_input=True, confirmation_prompt=True, err=True
                )
        except GetPassWarning:
            _fail("Could not hide terminal input. Use --stdin to provide the secret.")
    if not value:
        _fail("The secret must not be empty.")
    _call_keyring(backend.set_password, name, value)
    typer.echo(f"Stored {name}.", err=True)


@app.command("rm")
def remove_secret(
    name: Name,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Skip the deletion confirmation.")
    ] = False,
) -> None:
    """Delete a local secret value from the keyring."""
    backend = _backend()
    if _call_keyring(backend.get_password, name) is None:
        _fail(f"Secret {name!r} was not found.", code=1)
    if not yes:
        if not sys.stdin.isatty():
            _fail("Use --yes to confirm deletion when stdin is not a terminal.")
        if not typer.confirm(f"Delete {name!r} from the keyring?", err=True):
            typer.echo("Cancelled.", err=True)
            return
    _call_keyring(backend.delete_password, name)
    typer.echo(f"Removed {name}.", err=True)


@app.command("check")
def check_secrets(
    manifest: Annotated[
        Path,
        typer.Option(
            "--manifest", help="File declaring the expected environment names."
        ),
    ] = Path(".env.example"),
) -> None:
    """Check that every name in .env.example has a keyring entry."""
    names = _expected_names(manifest)
    if not names:
        typer.echo(f"No secrets declared in {manifest}.")
        return
    backend = _backend()
    missing = 0
    for name in names:
        value = _call_keyring(backend.get_password, name)
        if value is None:
            missing += 1
            typer.echo(f"missing  {name}")
        else:
            typer.echo(f"ok       {name}")
    typer.echo(f"{len(names) - missing}/{len(names)} secrets available.")
    if missing:
        raise typer.Exit(1)
