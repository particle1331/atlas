"""Manage local secrets through the system keyring."""

import re
import shutil
import subprocess
import sys
import warnings
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from getpass import GetPassWarning
from typing import Annotated

import keyring
import typer
from keyring.backend import KeyringBackend
from keyring.backends.fail import Keyring as FailKeyring
from keyring.backends.null import Keyring as NullKeyring

from atlas.config import ROOT_PATH
from atlas.vault_audit import audit

SERVICE_NAME = "atlas.vault"
app = typer.Typer(no_args_is_help=True, help="Store secrets in system keyring.")
Name = Annotated[str, typer.Argument(help="Name of the secret, such as API_TOKEN.")]


class VaultError(RuntimeError):
    """The system keyring could not complete a vault operation."""


def _exit(message: str, *, code: int = 2):
    typer.secho(f"Error: {message}", err=True, fg=typer.colors.BRIGHT_RED)
    raise typer.Exit(code)


def _get_backend() -> KeyringBackend:
    try:
        backend = keyring.get_keyring()
    except Exception as error:
        raise VaultError(
            f"Could not initialize keyring ({type(error).__name__})."
        ) from None
    if isinstance(backend, (FailKeyring, NullKeyring)):
        raise VaultError("No usable keyring is configured.")
    return backend


def _call_keyring[T](function: Callable[..., T], *args: str) -> T:
    try:
        return function(SERVICE_NAME, *args)
    except Exception as error:
        raise VaultError(
            f"Keyring operation failed ({type(error).__name__})."
        ) from None


def get_secret(name: str) -> str | None:
    """Return the stored value, or None if absent. Raise VaultError on failure."""
    return _call_keyring(_get_backend().get_password, name)


@contextmanager
def _cli_keyring_errors() -> Iterator[None]:
    try:
        yield
    except VaultError as error:
        _exit(str(error))


def _copy_to_clipboard(value: str) -> None:
    copy_command = "pbcopy"
    if shutil.which(copy_command) is None:
        _exit("macOS clipboard command 'pbcopy' was not found.")
    try:
        subprocess.run(copy_command, input=value, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        _exit(f"Clipboard operation failed ({type(error).__name__}).")


def _read_env_example() -> list[Name]:
    with open(ROOT_PATH / ".env.example", "r") as f:
        keys = []
        for line in f.readlines():
            l = line.strip()
            if len(l) == 0 or l.startswith("#"):
                continue

            if "=" not in l:
                _exit("Each line of .env.example shoud be `KEY_NAME=`")

            key, value = l.split("=", maxsplit=1)
            if value != "" or len(key) == 0:
                _exit("Each line of .env.example shoud be `KEY_NAME=`")

            keys.append(key)
        return keys


@app.command("get")
def get_command(name: Name) -> None:
    """Copy a secret to the clipboard or write it to stdout when piped."""
    with audit("get", name), _cli_keyring_errors():
        value = get_secret(name)
        if value is None:
            _exit(f"Secret {name!r} was not found.", code=1)
        if sys.stdout.isatty():
            _copy_to_clipboard(value)
            typer.echo(f"Copied {name} to clipboard.", err=True)
        else:
            sys.stdout.write(value)


@app.command("set")
def set_secret(
    name: Name,
    from_stdin: Annotated[
        bool,
        typer.Option("--stdin", help="Read the value from stdin instead of prompting."),
    ] = False,
) -> None:
    """Create or replace a secret using a hidden prompt or stdin."""
    with audit("set", name), _cli_keyring_errors():
        backend = _get_backend()
        if from_stdin:
            value = sys.stdin.read()
            value = value.removesuffix("\n").removesuffix("\r")
        else:
            if not sys.stdin.isatty():
                _exit(
                    "Terminal is required for hidden input. Use --stdin for piped input."
                )
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", GetPassWarning)
                    value = typer.prompt(
                        "Secret", hide_input=True, confirmation_prompt=True, err=True
                    )

            except GetPassWarning:
                # Never allow getpass to fall back to input that may be echoed.
                _exit("Could not hide terminal input. Use --stdin to pipe the secret.")

        if not value:
            _exit("The secret must not be empty.")

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
    with audit("rm", name) as event, _cli_keyring_errors():
        backend = _get_backend()
        if _call_keyring(backend.get_password, name) is None:
            _exit(f"Secret {name!r} was not found.", code=1)

        if not yes:
            if not sys.stdin.isatty():
                # Noninteractive deletion requires an explicit confirmation flag.
                _exit("Use --yes to confirm deletion when stdin is not a terminal.")

            if not typer.confirm(f"Delete {name!r} from the keyring?", err=True):
                event.outcome = "cancelled"
                typer.echo("Cancelled.", err=True)
                return

        _call_keyring(backend.delete_password, name)
        typer.echo(f"Removed {name}.", err=True)


@app.command("check")
def check_secrets() -> None:
    """Check that every name in .env.example has a keyring entry."""
    with audit("check") as event, _cli_keyring_errors():
        names = _read_env_example()
        event.secret_names = names
        if not names:
            typer.echo(f"No secrets declared.")
            return

        backend = _get_backend()
        missing = 0
        for name in names:
            value = _call_keyring(backend.get_password, name)
            if value is None:
                missing += 1
                typer.secho(f" [no]  {name}", fg=typer.colors.BRIGHT_RED)
            else:
                typer.secho(f" [ok]  {name}", fg=typer.colors.BRIGHT_GREEN)

        if missing:
            message = f"◩ {missing}/{len(names)} secrets missing."
            typer.secho(message, fg=typer.colors.YELLOW)
            raise typer.Exit(1)
        else:
            message = f"■ {len(names)}/{len(names)} secrets found."
            typer.secho(message, fg=typer.colors.BRIGHT_GREEN)
            raise typer.Exit(0)
