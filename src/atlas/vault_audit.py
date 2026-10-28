"""Local macOS Vault audit records with a rolling 30-day retention window."""

import fcntl
import json
import os
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import typer

from atlas.config import ROOT_PATH

RETENTION = timedelta(days=30)


@dataclass
class AuditEvent:
    operation: str
    secret_names: list[str] = field(default_factory=list)
    outcome: str = "success"
    exit_code: int = 0


@contextmanager
def _lock(path: Path) -> Generator[None, None, None]:
    """Keep concurrent pruning and appends in one transaction."""
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(descriptor, "a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _update_log(event: AuditEvent | None = None) -> None:
    """Prune expired records and atomically publish an optional new record."""
    try:
        directory = ROOT_PATH / ".atlas" / "logs"
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = directory / "vault.jsonl"
        with _lock(directory / ".vault.lock"):
            now = datetime.now(UTC)
            cutoff = now - RETENTION
            records = []
            if path.exists():
                with path.open(encoding="utf-8", errors="replace") as source:
                    for line in source:
                        try:
                            record = json.loads(line)
                            timestamp = datetime.fromisoformat(record["timestamp"])
                            if (
                                timestamp.tzinfo is not None
                                and cutoff <= timestamp <= now
                            ):
                                records.append(record)
                        except (ValueError, TypeError, KeyError):
                            # Malformed or undated records cannot satisfy retention.
                            continue
            if event is not None:
                records.append(
                    {
                        "timestamp": now.isoformat(),
                        **asdict(event),
                        "pid": os.getpid(),
                        "session_id": os.environ.get("ATLAS_VAULT_SESSION_ID", "")[:256]
                        or None,
                    }
                )

            descriptor, temporary = tempfile.mkstemp(
                prefix=".vault-", suffix=".tmp", dir=directory
            )
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
                    for record in records:
                        destination.write(json.dumps(record) + "\n")
                os.replace(temporary, path)
            finally:
                Path(temporary).unlink(missing_ok=True)
    except OSError as error:
        # A diagnostic log must not break secret delivery or expose error details.
        typer.secho(
            f"Warning: Could not update Vault audit log ({type(error).__name__}).",
            err=True,
            fg=typer.colors.YELLOW,
        )


@contextmanager
def audit(operation: str, name: str | None = None) -> Generator[AuditEvent, None, None]:
    """Record command outcomes without capturing values or exception messages."""
    _update_log()
    event = AuditEvent(operation, [name] if name is not None else [])
    try:
        yield event
    except typer.Exit as error:
        event.exit_code = error.exit_code
        if error.exit_code:
            event.outcome = "failure"
        raise
    except (typer.Abort, KeyboardInterrupt):
        event.outcome = "cancelled"
        event.exit_code = 1
        raise
    except Exception:
        event.outcome = "failure"
        event.exit_code = 1
        raise
    finally:
        _update_log(event)
