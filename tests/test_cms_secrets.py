import json
import os
import random
import shutil
import string
import subprocess
import sys
from base64 import b64encode
from pathlib import Path, PurePosixPath
from uuid import UUID

import pytest

from atlas import cms_secrets, cms_source
from atlas.cms_secrets import verify_repository

requires_gitleaks = pytest.mark.skipif(
    shutil.which("gitleaks") is None, reason="Gitleaks is not installed"
)


def git(repo, *args, env=None):
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], env=env, stderr=subprocess.DEVNULL
    )


@pytest.fixture
def repo(tmp_path, monkeypatch):
    for key in os.environ:
        if key.startswith("GIT_"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "--quiet", "--template=")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.org")
    return root


@pytest.fixture
def token():
    return "jina_" + "aA0bB1cC2dD3eE4fF5" * 3


def commit(repo):
    git(repo, "commit", "--quiet", "-m", "Snapshot")


@requires_gitleaks
@pytest.mark.parametrize(
    ("field", "length", "punctuation"),
    [
        ("PASSWORD", 16, ",:"),
        ("DB2_PASSWORD", 32, ">)"),
        ("WPA_PASSWORD", 20, "&="),
        ("CLIENT_SECRET", 32, "$?"),
        ("APP_PASSWD", 16, "#$"),
    ],
)
def test_unquoted_environment_passwords(repo, field, length, punctuation):
    random_source = random.Random(length)
    value = (
        "a"
        + punctuation
        + "".join(
            random_source.choices(string.ascii_letters + string.digits, k=length - 3)
        )
    )
    config = repo / "settings.env"
    config.write_text(f"  export {field} = {value} # local setup\r\n")
    (repo / "bare.txt").write_text(value)
    (repo / "quoted.txt").write_text(f'password = "{value}"')
    git(repo, "add", "settings.env", "bare.txt", "quoted.txt")

    with pytest.raises(ValueError) as error:
        verify_repository(repo, staged=True)
    report = str(error.value)
    assert "settings.env: atlas-unquoted-password" in report
    assert "quoted.txt: atlas-literal-password" in report
    assert "bare.txt" not in report
    assert value not in report


@requires_gitleaks
def test_unquoted_rule_distinguishes_literals_from_references():
    paths = {
        name: PurePosixPath(name + ".txt")
        for name in ("shell", "python", "redis-example", "unrelated-password")
    }
    placeholder = "redis_" + "password"
    report = cms_source.secret_findings(
        {
            paths["shell"]: "PASSWORD=$LOCAL_VALUE\nCLIENT_SECRET=${LOCAL_TOKEN}\n",
            paths["python"]: 'PASSWORD=os.getenv("LOCAL_VALUE")\n',
            paths["redis-example"]: f"REDIS__PASSWORD={placeholder}\n",
            paths["unrelated-password"]: f"DATABASE_PASSWORD={placeholder}\n",
        }
    )
    assert set(report) == {paths["unrelated-password"]}
    assert report[paths["unrelated-password"]].rules == {"atlas-unquoted-password"}


@requires_gitleaks
def test_known_formats_and_context_dependent_values(token):
    raw = random.Random(42).randbytes(32)
    encoded = b64encode(raw).decode("ascii")
    hex_key = raw.hex()
    stripe = "sk_" + "live_" + "Ab3xefY9" * 4
    identifier = UUID(bytes=raw[:16], version=4)
    report = cms_source.secret_findings(
        {
            PurePosixPath("jwt.txt"): f"JWT_SECRET={encoded}\n",
            PurePosixPath("encryption.txt"): f"ENCRYPTION_KEY={hex_key}\n",
            PurePosixPath("stripe.txt"): stripe,
            PurePosixPath("jina.txt"): token,
            PurePosixPath("jina-example.txt"): 'JINA_API_KEY="your_jina_api_key_here"',
            PurePosixPath("id.txt"): f'id: "{identifier}"',
            PurePosixPath("bare.txt"): f"{identifier}\n{encoded}\n{hex_key}\n",
        }
    )
    assert {path.name: finding.rules for path, finding in report.items()} == {
        "jwt.txt": {"generic-api-key"},
        "encryption.txt": {"generic-api-key"},
        "stripe.txt": {"stripe-access-token"},
        "jina.txt": {"atlas-jina-api-key"},
    }


@requires_gitleaks
def test_repository_scan_checks_worktree_index_and_head(repo, token):
    (repo / ".gitignore").write_text("ignored*\n")
    for name in ("head-only", "index-only", "worktree-only", "ignored-tracked"):
        (repo / name).write_text(token if name == "head-only" else "clean")
    git(repo, "add", "--force", "--all")
    commit(repo)
    # Neither the deleted HEAD file nor the index copy survives in the checkout.
    git(repo, "rm", "--quiet", "head-only")
    (repo / "index-only").write_text(token)
    git(repo, "add", "index-only")
    (repo / "index-only").write_text("clean")
    for name in ("worktree-only", "ignored-tracked", "ignored-untracked"):
        (repo / name).write_text(token)
    (repo / ".env.example").write_text(f'JINA_API_KEY="{token}"\n')

    with pytest.raises(ValueError) as error:
        verify_repository(repo)
    report = str(error.value)
    for name in (
        "head-only",
        "index-only",
        "worktree-only",
        "ignored-tracked",
        ".env.example",
    ):
        assert f"{name}: atlas-jina-api-key" in report
    assert "ignored-untracked" not in report
    assert token not in report


@requires_gitleaks
def test_unborn_head_scans_raw_notebook_and_browser_text(repo, token):
    notebook = {
        "nbformat": 4,
        "cells": [
            {
                "cell_type": "code",
                "source": ["pass"],
                "outputs": [
                    {
                        "output_type": "stream",
                        "text": ["jina_\x1b[31m", token[5:], "\x1b[0m"],
                    }
                ],
            }
        ],
    }
    raw = json.dumps(notebook)
    assert token not in raw
    (repo / "browser.ipynb").write_text(raw)
    (repo / "raw.ipynb").write_text(
        json.dumps({"nbformat": 4, "cells": [], "metadata": {"example": token}})
    )

    with pytest.raises(ValueError) as error:
        verify_repository(repo)
    report = str(error.value)
    assert "browser.ipynb: atlas-jina-api-key" in report
    assert "raw.ipynb: atlas-jina-api-key" in report
    assert token not in report


@requires_gitleaks
def test_binary_and_unusual_filenames_are_scanned_and_redacted(repo, token):
    folder = repo / "café"
    folder.mkdir()
    (folder / f"{token}.bin").write_bytes(b"\x00\xff")
    (repo / f"notes\n{token}.txt").write_text("ordinary text")
    (repo / ":path-with-\t-tab").write_text(token)
    (repo / "ordinary.bin").write_bytes(b"\0" + token.encode())
    git(repo, "add", "--all")

    with pytest.raises(ValueError) as error:
        verify_repository(repo)
    report = str(error.value)
    assert "café/***.bin: atlas-jina-api-key" in report
    assert "  ***: atlas-jina-api-key" in report
    assert r":path-with-\t-tab: atlas-jina-api-key" in report
    assert "ordinary.bin" not in report
    assert token not in report


@requires_gitleaks
def test_symlinks_are_scanned_as_text_but_never_followed(repo, token):
    outside = repo.parent / "outside"
    outside.mkdir()
    (outside / "file").write_text(token)
    (repo / "direct").symlink_to(outside / "file")
    folder = repo / "folder"
    folder.mkdir()
    (folder / "file").write_text("ordinary text")
    (repo / "stored-link").symlink_to(token)
    git(repo, "add", "--all")
    commit(repo)
    (folder / "file").unlink()
    folder.rmdir()
    folder.symlink_to(outside, target_is_directory=True)
    (repo / "stored-link").unlink()
    (repo / "worktree-link").symlink_to(token)

    with pytest.raises(ValueError) as error:
        verify_repository(repo)
    report = str(error.value)
    assert "stored-link: atlas-jina-api-key" in report
    assert "worktree-link: atlas-jina-api-key" in report
    assert "folder/file" not in report
    assert "direct" not in report
    assert token not in report


@requires_gitleaks
def test_staged_scan_reads_full_prospective_index_only(repo, token):
    (repo / "remove").write_text(token)
    (repo / "unchanged").write_text(token)
    git(repo, "add", "--all")
    commit(repo)
    git(repo, "rm", "--quiet", "remove")
    (repo / "untracked").write_text(token)
    (repo / "other").write_text("ordinary text")
    git(repo, "add", "other")
    (repo / "other").write_text(token)

    with pytest.raises(ValueError) as error:
        verify_repository(repo, staged=True)
    assert str(error.value).splitlines()[1:] == ["  unchanged: atlas-jina-api-key"]
    git(repo, "rm", "--quiet", "unchanged")
    verify_repository(repo, staged=True)
    (repo / "other").write_text("clean")
    (repo / "untracked").unlink()
    commit(repo)
    verify_repository(repo)  # Earlier commits are not part of the scan.


@requires_gitleaks
def test_staged_scan_honors_commit_index_override(repo, monkeypatch, token):
    (repo / "shared").write_text("ordinary text")
    git(repo, "add", "shared")
    commit(repo)
    temporary_index = repo / ".git" / "commit-index"
    monkeypatch.setenv("GIT_INDEX_FILE", str(temporary_index))
    git(repo, "read-tree", "HEAD")
    (repo / "shared").write_text(token)
    git(repo, "add", "shared")
    (repo / "shared").write_text("ordinary text")

    verify_repository(repo)
    with pytest.raises(ValueError, match="shared: atlas-jina-api-key"):
        verify_repository(repo, staged=True)


@requires_gitleaks
def test_native_hook_checks_path_commits_and_commit_all(repo, monkeypatch, token):
    # Run the checked-in hook with a shim that replaces uv's environment setup
    # with the test interpreter, preserving Git's real hook/index environment.
    bin_dir = repo.parent / "bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    uv.write_text(
        "#!/bin/sh\n"
        'test "$*" = "run --locked at cms scan-secrets --staged" || exit 2\n'
        'exec "$ATLAS_TEST_PYTHON" -m atlas cms --root "$PWD" scan-secrets --staged\n'
    )
    uv.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("ATLAS_TEST_PYTHON", sys.executable)
    for name in ("tracked", "old"):
        (repo / name).write_text(token if name == "old" else "ordinary text")
    git(repo, "add", "--all")
    commit(repo)

    hooks_path = Path(__file__).resolve().parents[1] / ".githooks"
    git(repo, "config", "core.hooksPath", str(hooks_path))
    (repo / "old").write_text("ordinary text")
    (repo / "staged").write_text(token)
    git(repo, "add", "staged")
    # A path-only commit can remove the HEAD finding without including the
    # secret staged for another commit.
    git(repo, "commit", "-qm", "Clean the old value", "--", "old")
    assert git(repo, "ls-tree", "--name-only", "HEAD", "staged") == b""
    git(repo, "rm", "--cached", "--force", "staged")
    (repo / "tracked").write_text(token)
    result = subprocess.run(
        ["git", "commit", "-qam", "Try to include a secret"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "tracked: atlas-jina-api-key" in result.stderr
    assert token not in result.stderr


def test_identical_views_and_filenames_are_batched(repo, monkeypatch):
    file = repo / "file.txt"
    file.write_text("first")
    git(repo, "add", "file.txt")
    commit(repo)
    file.write_text("second")
    git(repo, "add", "file.txt")
    calls = []

    def scan(files):
        calls.append(files)
        return {}

    monkeypatch.setattr(cms_secrets, "secret_findings", scan)
    verify_repository(repo)
    assert len(calls) == 1
    assert calls[0][PurePosixPath("file.txt")] in {"first", "second"}
    assert sorted(calls[0].values()) == ["first", "second"]


@pytest.mark.parametrize("failure", ["missing", "crash", "malformed"])
def test_scanner_failure_does_not_report_raw_output(repo, monkeypatch, failure, token):
    (repo / "file").write_text(token)
    scanner = repo.parent / "gitleaks"
    if failure != "missing":
        response = f"printf '%s' '{token}'"
        if failure == "crash":
            response += " >&2\nexit 2"
        scanner.write_text(f"#!/bin/sh\n{response}\n")
        scanner.chmod(0o700)
    monkeypatch.setattr(
        cms_source.shutil,
        "which",
        lambda _: str(scanner) if scanner.exists() else None,
    )
    expected = "Install Gitleaks" if failure == "missing" else "The secret scan failed"
    with pytest.raises(ValueError, match=expected) as error:
        verify_repository(repo)
    assert token not in str(error.value)


def test_missing_git_blob_fails_closed(repo, token):
    name = f"{token}.txt"
    file = repo / name
    file.write_text("ordinary text")
    git(repo, "add", "--all")
    oid = git(repo, "rev-parse", f":{name}").decode().strip()
    (repo / ".git" / "objects" / oid[:2] / oid[2:]).unlink()
    file.unlink()
    with pytest.raises(ValueError, match="Git could not read the repository") as error:
        verify_repository(repo)
    assert token not in str(error.value)
