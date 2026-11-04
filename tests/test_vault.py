import json
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
from atlas.vault import SERVICE_NAME, VaultError, get_secret


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
def audit_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep every CLI test away from the real local audit log."""
    monkeypatch.setattr("atlas.vault_audit.ROOT_PATH", tmp_path)
    monkeypatch.delenv("ATLAS_VAULT_SESSION_ID", raising=False)
    return tmp_path / ".atlas" / "logs" / "vault.jsonl"


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
    runner: CliRunner, backend: LocalKeyring, manifest: Path, audit_log: Path
) -> None:
    """From a manifest declaring API_TOKEN, exercise its complete lifecycle."""
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
    records = [json.loads(line) for line in audit_log.read_text().splitlines()]
    assert [record["operation"] for record in records] == [
        "set",
        "get",
        "check",
        "rm",
        "check",
    ]
    assert [record["outcome"] for record in records] == [
        "success",
        "success",
        "success",
        "success",
        "failure",
    ]
    assert [record["exit_code"] for record in records] == [0, 0, 0, 0, 1]
    assert all(record["secret_names"] == ["API_TOKEN"] for record in records)
    assert "private value" not in audit_log.read_text()


def test_check_reports_available_and_missing_secrets_and_skips_comments(
    runner: CliRunner, backend: LocalKeyring, manifest: Path
) -> None:
    """Manifest containing comments and one missing (not stored in vault)."""
    manifest.write_text(
        "# Required secrets\n\n"
        "PRESENT=\n"
        "\t# Indented comment\n"
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
    ["TOKEN\n", "TOKEN=private manifest value\n", "=\n"],
    ids=["missing-equals", "nonempty-value", "empty-name"],
)
def test_invalid_manifest_fails_before_accessing_keyring(
    runner: CliRunner,
    manifest: Path,
    get_backend: Mock,
    contents: str,
    audit_log: Path,
) -> None:
    """Incorrect manifest entry syntax examples (one-liner each)."""
    manifest.write_text(contents)

    result = runner.invoke(app, ["vault", "check"])
    assert result.exit_code == 2, result.output
    assert "KEY_NAME=" in result.stderr
    get_backend.assert_not_called()  # vault not accessed
    record = json.loads(audit_log.read_text())
    assert record["outcome"] == "failure"
    assert record["secret_names"] == []
    assert "private manifest value" not in result.output
    assert "private manifest value" not in audit_log.read_text()


def test_missing_manifest_raises_file_not_found_before_accessing_keyring(
    runner: CliRunner, manifest: Path, get_backend: Mock
) -> None:
    """Missing manifest (no write) fails vault check w/o vault access."""
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
    """Examples of empty manifests. OK w/o vault access."""
    manifest.write_text(contents)

    result = runner.invoke(app, ["vault", "check"])
    assert result.exit_code == 0, result.output
    assert result.stdout == "No secrets declared.\n"
    get_backend.assert_not_called()


@pytest.mark.parametrize(
    ("arguments", "stdin"),
    [
        (["vault", "set", "TOKEN"], "value\n"),  # cant expose value in tty
        (["vault", "set", "TOKEN", "--stdin"], "\n"),  # non-empty value required
    ],
    ids=["missing-stdin-option", "empty-secret"],
)
def test_set_rejects_noninteractive_or_empty_input(
    runner: CliRunner, backend: LocalKeyring, arguments: list[str], stdin: str
) -> None:
    """Invalid vault set input examples (exit code 2). Note: '\n\n' passes!"""
    result = runner.invoke(app, arguments, input=stdin)
    assert result.exit_code == 2, result.output
    assert backend.values == {}


def test_deletion_requires_explicit_noninteractive_confirmation(
    runner: CliRunner, backend: LocalKeyring
) -> None:
    """Deletion requires confirmation (interactive, or --yes / -y)."""
    backend.set_password(SERVICE_NAME, "TOKEN", "keep this")

    result = runner.invoke(app, ["vault", "rm", "TOKEN"])
    assert result.exit_code == 2, result.output
    assert backend.get_password(SERVICE_NAME, "TOKEN") == "keep this"


@pytest.mark.parametrize("command", ["get", "rm"])
def test_missing_secret_returns_one_without_stdout(
    runner: CliRunner, command: str
) -> None:
    """Missing key gives exit code 1 for read/delete commands."""
    result = runner.invoke(app, ["vault", command, "MISSING"])
    assert result.exit_code == 1, result.output
    assert result.stdout == ""  # error msg goes to stderr
    assert result.stderr == "Error: Secret 'MISSING' was not found.\n"


def test_hidden_prompt_and_deletion_confirmation(
    runner: CliRunner,
    backend: LocalKeyring,
    monkeypatch: pytest.MonkeyPatch,
    audit_log: Path,
) -> None:
    """Simulating vault set & rm confirmation from terminal."""
    # Note: in prev tests, CliRunner does not create a terminal
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
    records = [json.loads(line) for line in audit_log.read_text().splitlines()]
    assert [record["outcome"] for record in records] == [
        "success",
        "cancelled",
        "success",
    ]
    assert all(record["exit_code"] == 0 for record in records)
    assert "confirmed token" not in audit_log.read_text()


def test_hidden_input_failure_stops_without_echo_fallback(
    runner: CliRunner, backend: LocalKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simulating inability to hide input in terminal (exit code 2)."""
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
    """Missing backend exit code 2."""
    get_backend.return_value = unavailable_backend

    result = runner.invoke(app, ["vault", "get", "TOKEN"])
    assert result.exit_code == 2, result.output
    assert "No usable keyring" in result.output


def test_backend_exceptions_cannot_print_secret_values(
    runner: CliRunner,
    backend: LocalKeyring,
    monkeypatch: pytest.MonkeyPatch,
    audit_log: Path,
) -> None:
    """Credentials must not be printed (output = stderr + stdout)."""
    monkeypatch.setattr(
        backend, "set_password", Mock(side_effect=RuntimeError("private credential"))
    )

    result = runner.invoke(
        app, ["vault", "set", "TOKEN", "--stdin"], input="private credential"
    )
    assert result.exit_code == 2, result.output
    assert "RuntimeError" in result.output
    assert "private credential" not in result.output
    assert "private credential" not in audit_log.read_text()
    record = json.loads(audit_log.read_text())
    assert record["operation"] == "set"
    assert record["outcome"] == "failure"
    assert record["exit_code"] == 2


def test_get_secret_serves_python_callers(
    backend: LocalKeyring, capsys: pytest.CaptureFixture[str]
) -> None:
    """The reader returns values, and reports a missing entry as None."""
    backend.values[(SERVICE_NAME, "TOKEN")] = "private value"

    assert get_secret("TOKEN") == "private value"
    assert get_secret("MISSING") is None
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_get_secret_raises_vault_error_for_unavailable_backend(
    get_backend: Mock,
) -> None:
    """Keyring initialization failures surface as VaultError to callers."""
    get_backend.side_effect = RuntimeError("unavailable")

    with pytest.raises(VaultError, match="Could not initialize keyring"):
        get_secret("TOKEN")


def test_get_secret_raises_vault_error_for_backend_failure(
    backend: LocalKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keyring read failures surface as VaultError without leaking details."""
    monkeypatch.setattr(
        backend, "get_password", Mock(side_effect=RuntimeError("private credential"))
    )

    with pytest.raises(VaultError, match="Keyring operation failed") as error:
        get_secret("TOKEN")
    assert "private credential" not in str(error.value)


def test_logging_failure_does_not_change_secret_output(
    runner: CliRunner, backend: LocalKeyring, audit_log: Path
) -> None:
    """An unwritable log warns on stderr and preserves piped secret delivery."""
    audit_log.parent.parent.write_text("not a directory")
    backend.set_password(SERVICE_NAME, "TOKEN", "private value")

    result = runner.invoke(app, ["vault", "get", "TOKEN"])

    assert result.exit_code == 0, result.output
    assert result.stdout == "private value"
    assert "Could not update Vault audit log" in result.stderr
    assert "private value" not in result.stderr
