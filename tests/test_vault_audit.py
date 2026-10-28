import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from stat import S_IMODE

import pytest
import typer

from atlas import vault_audit


@pytest.fixture
def audit_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(vault_audit, "ROOT_PATH", tmp_path)
    monkeypatch.delenv("ATLAS_VAULT_SESSION_ID", raising=False)
    return tmp_path / ".atlas" / "logs" / "vault.jsonl"


def test_retention_prunes_before_access_and_keeps_exactly_30_days(
    audit_log: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime(2026, 10, 28, 12, tzinfo=UTC)

    class Clock(datetime):
        @staticmethod
        def now(tz: object) -> datetime:
            return now

    monkeypatch.setattr(vault_audit, "datetime", Clock)
    cutoff = now - timedelta(days=30)
    audit_log.parent.mkdir(parents=True)
    audit_log.write_text(
        "\n".join(
            json.dumps(record)
            for record in [
                {
                    "timestamp": (cutoff - timedelta(microseconds=1)).isoformat(),
                    "operation": "expired",
                },
                {"timestamp": cutoff.isoformat(), "operation": "boundary"},
                {"timestamp": now.isoformat(), "operation": "recent"},
                {
                    "timestamp": (now + timedelta(seconds=1)).isoformat(),
                    "operation": "future",
                },
                {"timestamp": now.replace(tzinfo=None).isoformat()},
                {"timestamp": "bad date"},
                {"timestamp": None},
                {"undated": True},
                [],
            ]
        )
        + "\nnot json\n"
    )

    with vault_audit.audit("get", "TOKEN"):
        records = [json.loads(line) for line in audit_log.read_text().splitlines()]
        assert [record["operation"] for record in records] == ["boundary", "recent"]

    records = [json.loads(line) for line in audit_log.read_text().splitlines()]
    assert [record["operation"] for record in records] == ["boundary", "recent", "get"]
    now += timedelta(days=31)

    with vault_audit.audit("check"):
        assert audit_log.read_text() == ""

    assert json.loads(audit_log.read_text())["operation"] == "check"


def test_record_metadata_is_structured_and_session_label_is_optional(
    audit_log: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    label = 'session-123\n{"outcome":"forged"}'
    name = 'TOKEN\n{"operation":"forged"}'
    monkeypatch.setenv("ATLAS_VAULT_SESSION_ID", label)

    with vault_audit.audit("get", name):
        pass

    lines = audit_log.read_text().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record == {
        "timestamp": record["timestamp"],
        "operation": "get",
        "secret_names": [name],
        "outcome": "success",
        "exit_code": 0,
        "pid": os.getpid(),
        "session_id": label,
    }
    assert datetime.fromisoformat(record["timestamp"]).utcoffset() == timedelta(0)

    monkeypatch.delenv("ATLAS_VAULT_SESSION_ID")
    with vault_audit.audit("check"):
        pass
    records = [json.loads(line) for line in audit_log.read_text().splitlines()]
    assert records[-1]["session_id"] is None


@pytest.mark.parametrize(
    "error,outcome,exit_code",
    [
        (typer.Abort(), "cancelled", 1),
        (KeyboardInterrupt(), "cancelled", 1),
        (RuntimeError("private error content"), "failure", 1),
    ],
)
def test_aborts_and_unexpected_errors_do_not_leak_messages(
    audit_log: Path, error: BaseException, outcome: str, exit_code: int
) -> None:
    with pytest.raises(type(error)):
        with vault_audit.audit("set", "TOKEN"):
            raise error

    record = json.loads(audit_log.read_text())
    assert record["outcome"] == outcome
    assert record["exit_code"] == exit_code
    assert "private error content" not in audit_log.read_text()


def test_parallel_processes_preserve_every_record(
    audit_log: Path, tmp_path: Path
) -> None:
    script = """
import sys
from pathlib import Path
from atlas import vault_audit

vault_audit.ROOT_PATH = Path(sys.argv[1])
for index in range(3):
    with vault_audit.audit("get", f"worker-{sys.argv[2]}-{index}"):
        pass
"""

    def run_worker(worker: int) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-c", script, str(tmp_path), str(worker)],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(run_worker, range(4)))

    assert all(not result.stderr for result in results)
    records = [json.loads(line) for line in audit_log.read_text().splitlines()]
    assert len(records) == 12
    assert {record["secret_names"][0] for record in records} == {
        f"worker-{worker}-{index}" for worker in range(4) for index in range(3)
    }
    assert not list(audit_log.parent.glob("*.tmp"))
    assert S_IMODE(audit_log.stat().st_mode) == 0o600
