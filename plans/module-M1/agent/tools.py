"""Tool schemas and sandboxed execution for the M1 agent."""

from __future__ import annotations

import json
import os
import signal
import subprocess
from pathlib import Path
from typing import Any

TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": (
                "Run a shell command in the sandbox root. Returns exit code, stdout, "
                "and stderr. Commands are killed after the timeout. Use this to list "
                "files, run scripts, and run tests. Prefer relative paths."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute, e.g. 'python3 check.py'.",
                    }
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a UTF-8 text file relative to the sandbox root. Large files "
                "are truncated. Read a file before editing it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path, e.g. 'src/app.py'.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write UTF-8 text to a file relative to the sandbox root, creating "
                "parent directories. The write replaces the entire file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path, e.g. 'src/app.py'.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete new file contents.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
]


class ToolError(Exception):
    """A tool call that should be reported back to the model."""


def _sandbox_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(key, None)
    env["PYTHONUNBUFFERED"] = "1"
    env["NO_COLOR"] = "1"
    return env


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = limit * 3 // 4
    tail = limit - head
    omitted = len(text) - limit
    return f"{text[:head]}\n...[{omitted} chars truncated]...\n{text[-tail:]}"


class ToolExecutor:
    def __init__(
        self,
        workspace: Path,
        *,
        timeout_s: int = 30,
        max_output_chars: int = 8000,
    ) -> None:
        self.workspace = Path(workspace).resolve()
        self.timeout_s = timeout_s
        self.max_output_chars = max_output_chars

    def _resolve(self, path: str) -> Path:
        if not isinstance(path, str) or not path.strip():
            raise ToolError("path must be a non-empty string")
        candidate = Path(path)
        if candidate.is_absolute():
            raise ToolError("absolute paths are not allowed; use a relative path")
        target = (self.workspace / candidate).resolve()
        if target != self.workspace and self.workspace not in target.parents:
            raise ToolError("path escapes the sandbox")
        return target

    def _bash(self, args: dict[str, Any]) -> str:
        command = args.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ToolError("command must be a non-empty string")
        process = subprocess.Popen(
            command,
            shell=True,
            cwd=self.workspace,
            env=_sandbox_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=self.timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            stdout, stderr = process.communicate()

        code = 124 if timed_out else process.returncode
        stdout = _truncate(stdout or "", self.max_output_chars)
        stderr = _truncate(stderr or "", self.max_output_chars)
        suffix = f"\n[command timed out after {self.timeout_s}s]" if timed_out else ""
        return f"exit_code={code}\nstdout:\n{stdout}\nstderr:\n{stderr}{suffix}"

    def _read_file(self, args: dict[str, Any]) -> str:
        path = self._resolve(str(args.get("path", "")))
        if not path.exists():
            raise ToolError(f"file not found: {path.relative_to(self.workspace)}")
        if not path.is_file():
            raise ToolError(f"not a file: {path.relative_to(self.workspace)}")
        return _truncate(
            path.read_text(encoding="utf-8", errors="replace"), self.max_output_chars
        )

    def _write_file(self, args: dict[str, Any]) -> str:
        content = args.get("content")
        if not isinstance(content, str):
            raise ToolError("content must be a string")
        if len(content) > 200_000:
            raise ToolError("content is too large (limit 200000 characters)")
        path = self._resolve(str(args.get("path", "")))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        relative = path.relative_to(self.workspace).as_posix()
        return f"Wrote {len(content)} characters to {relative}"

    def execute(self, name: str, arguments: str | None) -> str:
        """Execute one tool call. Errors are returned to the model, never raised."""
        try:
            parsed = json.loads(arguments or "{}")
            if not isinstance(parsed, dict):
                raise ToolError("arguments must be a JSON object")
            if name == "bash":
                return self._bash(parsed)
            if name == "read_file":
                return self._read_file(parsed)
            if name == "write_file":
                return self._write_file(parsed)
            raise ToolError(f"unknown tool: {name}")
        except ToolError as error:
            return f"ERROR: {error}"
        except json.JSONDecodeError as error:
            return f"ERROR: invalid JSON arguments: {error}"
        except Exception as error:  # pragma: no cover - defensive boundary
            return f"ERROR: {type(error).__name__}: {error}"
