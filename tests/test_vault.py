from getpass import GetPassWarning
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from keyring.backend import KeyringBackend
from keyring.backends.fail import Keyring as FailKeyring
from keyring.backends.null import Keyring as NullKeyring
from keyring.errors import PasswordDeleteError
from typer.testing import CliRunner

from atlas.cli import app
from atlas.vault import SERVICE_NAME


class LocalKeyring(KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.values.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.values[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        try:
            del self.values[(service, username)]
        except KeyError as error:
            raise PasswordDeleteError from error


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def backend() -> LocalKeyring:
    return LocalKeyring()


@pytest.fixture(autouse=True)
def get_backend(monkeypatch: pytest.MonkeyPatch, backend: LocalKeyring) -> Mock:
    get_backend = Mock(return_value=backend)
    monkeypatch.setattr("atlas.vault.keyring.get_keyring", get_backend)
    return get_backend


@pytest.fixture
def manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate the vault's project root without creating the manifest."""
    monkeypatch.setattr("atlas.vault.ROOT_PATH", tmp_path)
    return tmp_path / ".env.example"


def test_round_trip_and_removal_preserve_the_manifest(
    runner: CliRunner, backend: LocalKeyring, manifest: Path
) -> None:
    contents = "API_TOKEN=\n"
    manifest.write_text(contents)

    result = runner.invoke(
        app, ["vault", "set", "API_TOKEN", "--stdin"], input="private value\n"
    )
    assert result.exit_code == 0, result.output
    assert "private value" not in result.output
    assert result.stdout == ""
    assert backend.values == {(SERVICE_NAME, "API_TOKEN"): "private value"}

    result = runner.invoke(app, ["vault", "get", "API_TOKEN"])
    assert result.exit_code == 0, result.output
    assert result.stdout == "private value"

    result = runner.invoke(app, ["vault", "check"])
    assert result.exit_code == 0, result.output
    assert result.stdout == " [ok]  API_TOKEN\n■ 1/1 secrets found.\n"
    assert "private value" not in result.output

    result = runner.invoke(app, ["vault", "rm", "API_TOKEN", "--yes"])
    assert result.exit_code == 0, result.output
    assert backend.values == {}

    result = runner.invoke(app, ["vault", "check"])
    assert result.exit_code == 1, result.output
    assert result.stdout == " [no]  API_TOKEN\n◩ 1/1 secrets missing.\n"
    assert manifest.read_text() == contents


def test_check_reports_available_and_missing_secrets_and_skips_comments(
    runner: CliRunner, backend: LocalKeyring, manifest: Path
) -> None:
    manifest.write_text(
        "# Required secrets\n\n"
        "PRESENT=\n \t\n  # Indented comment\n"
        "SECOND=\n"
        "# IGNORED=example\n"
        "MISSING=\n"
    )
    backend.set_password(SERVICE_NAME, "PRESENT", "stored token")
    backend.set_password(SERVICE_NAME, "SECOND", "another stored token")

    result = runner.invoke(app, ["vault", "check"])
    assert result.exit_code == 1, result.output
    assert result.stdout == (
        " [ok]  PRESENT\n" 
        " [ok]  SECOND\n" 
        " [no]  MISSING\n" 
        "◩ 1/3 secrets missing.\n"  # typer.secho adds trailing newline
    )
    assert "stored token" not in result.output


@pytest.mark.parametrize(
    "contents",
    ["TOKEN\n", "TOKEN=example\n", "=\n"],
    ids=["missing-equals", "nonempty-value", "empty-name"],
)
def test_invalid_manifest_fails_before_accessing_keyring(
    runner: CliRunner, manifest: Path, get_backend: Mock, contents: str
) -> None:
    manifest.write_text(contents)

    result = runner.invoke(app, ["vault", "check"])
    assert result.exit_code == 2, result.output
    assert "KEY_NAME=" in result.stderr
    get_backend.assert_not_called()     # backend not accessed


def test_missing_manifest_raises_file_not_found_before_accessing_keyring(
    runner: CliRunner, manifest: Path, get_backend: Mock
) -> None:
    result = runner.invoke(app, ["vault", "check"])
    assert result.exit_code == 1, result.output
    assert isinstance(result.exception, FileNotFoundError)
    get_backend.assert_not_called()


@pytest.mark.parametrize(
    "contents",
    ["", "\n \t\n", "# Required secrets\n  # No entries yet\n"],
    ids=["empty", "blank-lines", "comments-only"],
)
def test_empty_manifest_succeeds_without_accessing_keyring(
    runner: CliRunner, manifest: Path, get_backend: Mock, contents: str
) -> None:
    manifest.write_text(contents)

    result = runner.invoke(app, ["vault", "check"])
    assert result.exit_code == 0, result.output
    assert result.stdout == "No secrets declared.\n"
    get_backend.assert_not_called()


@pytest.mark.parametrize(
    ("arguments", "stdin"),
    [
        (["vault", "set", "TOKEN"], "value\n"),
        (["vault", "set", "TOKEN", "--stdin"], "\n"),
    ],
    ids=["missing-stdin-option", "empty-secret"],
)
def test_set_rejects_noninteractive_or_empty_input(
    runner: CliRunner, backend: LocalKeyring, arguments: list[str], stdin: str
) -> None:
    result = runner.invoke(app, arguments, input=stdin)
    assert result.exit_code == 2, result.output
    assert backend.values == {}


def test_deletion_requires_explicit_noninteractive_confirmation(
    runner: CliRunner, backend: LocalKeyring
) -> None:
    backend.set_password(SERVICE_NAME, "TOKEN", "keep this")

    result = runner.invoke(app, ["vault", "rm", "TOKEN"])
    assert result.exit_code == 2, result.output
    assert backend.get_password(SERVICE_NAME, "TOKEN") == "keep this"


@pytest.mark.parametrize("command", ["get", "rm"])
def test_missing_secret_returns_one_without_stdout(
    runner: CliRunner, command: str
) -> None:
    result = runner.invoke(app, ["vault", command, "MISSING"])
    assert result.exit_code == 1, result.output
    assert result.stdout == ""


def test_hidden_prompt_and_deletion_confirmation(
    runner: CliRunner, backend: LocalKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    terminal = SimpleNamespace(stdin=SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr("atlas.vault.sys", terminal)

    result = runner.invoke(
        app,
        ["vault", "set", "TOKEN"],
        input="first attempt\nmismatch\nconfirmed token\nconfirmed token\n",
    )
    assert result.exit_code == 0, result.output
    assert backend.get_password(SERVICE_NAME, "TOKEN") == "confirmed token"
    for value in ("first attempt", "mismatch", "confirmed token"):
        assert value not in result.output

    result = runner.invoke(app, ["vault", "rm", "TOKEN"], input="n\n")
    assert result.exit_code == 0, result.output
    assert backend.get_password(SERVICE_NAME, "TOKEN") is not None

    result = runner.invoke(app, ["vault", "rm", "TOKEN"], input="y\n")
    assert result.exit_code == 0, result.output
    assert backend.get_password(SERVICE_NAME, "TOKEN") is None


def test_hidden_input_failure_stops_without_echo_fallback(
    runner: CliRunner, backend: LocalKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    terminal = SimpleNamespace(stdin=SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr("atlas.vault.sys", terminal)
    monkeypatch.setattr("atlas.vault.typer.prompt", Mock(side_effect=GetPassWarning))

    result = runner.invoke(app, ["vault", "set", "TOKEN"])
    assert result.exit_code == 2, result.output
    assert backend.values == {}


@pytest.mark.parametrize(
    "unavailable_backend", [NullKeyring(), FailKeyring()], ids=["null", "fail"]
)
def test_unavailable_backends_are_rejected(
    runner: CliRunner, get_backend: Mock, unavailable_backend: KeyringBackend
) -> None:
    get_backend.return_value = unavailable_backend

    result = runner.invoke(app, ["vault", "get", "TOKEN"])
    assert result.exit_code == 2, result.output
    assert "No usable keyring" in result.output


def test_backend_exceptions_cannot_print_secret_values(
    runner: CliRunner, backend: LocalKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        backend, 
        "set_password", Mock(side_effect=RuntimeError("private credential"))
    )

    result = runner.invoke(app, 
        ["vault", "set", "TOKEN", "--stdin"], 
        input="private credential"
    )
    assert result.exit_code == 2, result.output
    assert "RuntimeError" in result.output
    assert "private credential" not in result.output
