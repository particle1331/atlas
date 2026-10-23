import unittest
from contextlib import chdir
from getpass import GetPassWarning
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from keyring.backend import KeyringBackend
from keyring.backends.fail import Keyring as FailKeyring
from keyring.backends.null import Keyring as NullKeyring
from keyring.errors import PasswordDeleteError
from typer.testing import CliRunner

from atlas.cli import app
from atlas.vault import SERVICE_NAME


class MemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.values.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.values[service, username] = password

    def delete_password(self, service: str, username: str) -> None:
        try:
            del self.values[service, username]
        except KeyError as error:
            raise PasswordDeleteError from error


class VaultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()
        self.backend = MemoryKeyring()
        self.backend_patch = patch(
            "atlas.vault.keyring.get_keyring", return_value=self.backend
        )
        self.get_backend = self.backend_patch.start()
        self.addCleanup(self.backend_patch.stop)

    def test_round_trip_and_removal_preserve_the_manifest(self) -> None:
        with TemporaryDirectory() as directory, chdir(directory):
            manifest = Path(".env.example")
            contents = "# Project requirements\nAPI_TOKEN=example\n"
            manifest.write_text(contents)

            result = self.runner.invoke(
                app, ["vault", "set", "API_TOKEN", "--stdin"], input="private value\n"
            )
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertNotIn("private value", result.output)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                self.backend.values, {(SERVICE_NAME, "API_TOKEN"): "private value"}
            )

            result = self.runner.invoke(app, ["vault", "get", "API_TOKEN"])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(result.stdout, "private value")

            result = self.runner.invoke(app, ["vault", "check"])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("ok       API_TOKEN", result.output)
            self.assertNotIn("private value", result.output)

            result = self.runner.invoke(app, ["vault", "rm", "API_TOKEN", "--yes"])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(self.backend.values, {})

            result = self.runner.invoke(app, ["vault", "check"])
            self.assertEqual(result.exit_code, 1, result.output)
            self.assertIn("missing  API_TOKEN", result.output)
            self.assertEqual(manifest.read_text(), contents)

    def test_check_handles_dotenv_syntax_and_duplicates(self) -> None:
        with TemporaryDirectory() as directory, chdir(directory):
            Path("requirements.env").write_text(
                "# comment\n"
                'export PRESENT="${DO_NOT_EXPAND}"\n'
                "PRESENT=ignored\n"
                'MULTILINE="first\nsecond"\n'
                "MISSING=\n"
            )
            self.backend.set_password(SERVICE_NAME, "PRESENT", "stored token")
            self.backend.set_password(SERVICE_NAME, "MULTILINE", "stored multiline")

            result = self.runner.invoke(
                app, ["vault", "check", "--manifest", "requirements.env"]
            )
            self.assertEqual(result.exit_code, 1, result.output)
            self.assertEqual(result.output.count("PRESENT"), 1)
            self.assertIn("ok       MULTILINE", result.output)
            self.assertIn("missing  MISSING", result.output)
            self.assertIn("2/3 secrets available.", result.output)
            self.assertNotIn("stored token", result.output)
            self.assertNotIn("DO_NOT_EXPAND", result.output)

    def test_invalid_manifest_fails_before_accessing_keyring(self) -> None:
        with TemporaryDirectory() as directory, chdir(directory):
            Path(".env.example").write_text('TOKEN="private unterminated value\n')
            result = self.runner.invoke(app, ["vault", "check"])
            self.assertEqual(result.exit_code, 2, result.output)
            self.assertIn("Invalid .env syntax", result.output)
            self.assertNotIn("private unterminated", result.output)
            self.get_backend.assert_not_called()

    def test_missing_or_empty_manifest_has_explicit_behavior(self) -> None:
        with TemporaryDirectory() as directory, chdir(directory):
            result = self.runner.invoke(app, ["vault", "check"])
            self.assertEqual(result.exit_code, 2, result.output)
            Path(".env.example").write_text("# No required secrets yet\n")
            result = self.runner.invoke(app, ["vault", "check"])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("No secrets declared", result.output)
            self.get_backend.assert_not_called()

    def test_input_and_deletion_require_explicit_noninteractive_options(self) -> None:
        result = self.runner.invoke(app, ["vault", "set", "TOKEN"], input="value\n")
        self.assertEqual(result.exit_code, 2, result.output)
        self.assertEqual(self.backend.values, {})

        result = self.runner.invoke(
            app, ["vault", "set", "TOKEN", "--stdin"], input="\n"
        )
        self.assertEqual(result.exit_code, 2, result.output)
        self.assertEqual(self.backend.values, {})

        self.backend.set_password(SERVICE_NAME, "TOKEN", "keep this")
        result = self.runner.invoke(app, ["vault", "rm", "TOKEN"])
        self.assertEqual(result.exit_code, 2, result.output)
        self.assertEqual(self.backend.get_password(SERVICE_NAME, "TOKEN"), "keep this")

    def test_missing_secret_returns_one_without_stdout(self) -> None:
        for command in ("get", "rm"):
            with self.subTest(command=command):
                result = self.runner.invoke(app, ["vault", command, "MISSING"])
                self.assertEqual(result.exit_code, 1, result.output)
                self.assertEqual(result.stdout, "")

    def test_hidden_prompt_and_deletion_confirmation(self) -> None:
        terminal = SimpleNamespace(stdin=SimpleNamespace(isatty=lambda: True))
        with patch("atlas.vault.sys", terminal):
            result = self.runner.invoke(
                app,
                ["vault", "set", "TOKEN"],
                input="first attempt\nmismatch\nconfirmed token\nconfirmed token\n",
            )
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(
                self.backend.get_password(SERVICE_NAME, "TOKEN"), "confirmed token"
            )
            for value in ("first attempt", "mismatch", "confirmed token"):
                self.assertNotIn(value, result.output)

            result = self.runner.invoke(app, ["vault", "rm", "TOKEN"], input="n\n")
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIsNotNone(self.backend.get_password(SERVICE_NAME, "TOKEN"))

            result = self.runner.invoke(app, ["vault", "rm", "TOKEN"], input="y\n")
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIsNone(self.backend.get_password(SERVICE_NAME, "TOKEN"))

    def test_hidden_input_failure_stops_without_echo_fallback(self) -> None:
        terminal = SimpleNamespace(stdin=SimpleNamespace(isatty=lambda: True))
        with (
            patch("atlas.vault.sys", terminal),
            patch("atlas.vault.typer.prompt", side_effect=GetPassWarning),
        ):
            result = self.runner.invoke(app, ["vault", "set", "TOKEN"])
        self.assertEqual(result.exit_code, 2, result.output)
        self.assertEqual(self.backend.values, {})

    def test_unavailable_backends_are_rejected(self) -> None:
        for backend in (NullKeyring(), FailKeyring()):
            with self.subTest(backend=type(backend)):
                self.get_backend.return_value = backend
                result = self.runner.invoke(app, ["vault", "get", "TOKEN"])
                self.assertEqual(result.exit_code, 2, result.output)
                self.assertIn("No usable keyring", result.output)

    def test_backend_exceptions_cannot_print_secret_values(self) -> None:
        with patch.object(
            self.backend, "set_password", side_effect=RuntimeError("private credential")
        ):
            result = self.runner.invoke(
                app, ["vault", "set", "TOKEN", "--stdin"], input="private credential"
            )
        self.assertEqual(result.exit_code, 2, result.output)
        self.assertIn("RuntimeError", result.output)
        self.assertNotIn("private credential", result.output)


if __name__ == "__main__":
    unittest.main()
