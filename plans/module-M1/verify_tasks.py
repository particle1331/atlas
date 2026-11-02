#!/usr/bin/env python3
"""Verify each check fails on starter files and passes on the reference solution."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TASKS_DIR = ROOT / "tasks"


def discover_tasks(pattern: str | None = None) -> list[Path]:
    tasks = sorted(
        path
        for path in TASKS_DIR.iterdir()
        if path.is_dir()
        and (path / "prompt.md").is_file()
        and (path / "starter").is_dir()
        and (path / "solution").is_dir()
        and (path / "check.sh").is_file()
    )
    if pattern:
        tasks = [path for path in tasks if pattern in path.name]
    return tasks


def sandbox_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(key, None)
    env["PYTHONUNBUFFERED"] = "1"
    env["NO_COLOR"] = "1"
    return env


def run_check(task_dir: Path, sandbox: Path, timeout_s: int) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            ["bash", str(task_dir / "check.sh")],
            cwd=sandbox,
            env=sandbox_env(),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", "replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", "replace")
        return 124, stdout, f"{stderr}\ncheck timed out after {timeout_s}s"
    return result.returncode, result.stdout, result.stderr


def check_variant(
    task_dir: Path, use_solution: bool, timeout_s: int
) -> tuple[int, str, str]:
    sandbox = Path(tempfile.mkdtemp(prefix=f"m1-verify-{task_dir.name}-"))
    try:
        shutil.copytree(task_dir / "starter", sandbox, dirs_exist_ok=True)
        if use_solution:
            shutil.copytree(task_dir / "solution", sandbox, dirs_exist_ok=True)
        return run_check(task_dir, sandbox, timeout_s)
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default=None, help="Only tasks whose name matches.")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tasks = discover_tasks(args.task)
    if not tasks:
        print("No tasks found.")
        return 1

    failures: list[str] = []
    for task in tasks:
        starter_code, starter_out, starter_err = check_variant(
            task, use_solution=False, timeout_s=args.timeout
        )
        solution_code, solution_out, solution_err = check_variant(
            task, use_solution=True, timeout_s=args.timeout
        )
        starter_ok = starter_code != 0
        solution_ok = solution_code == 0
        status = "OK" if starter_ok and solution_ok else "BROKEN"
        print(f"{status:7} {task.name}")
        if not starter_ok:
            failures.append(
                f"{task.name}: check passed on starter files "
                f"(exit {starter_code})\n{starter_out}\n{starter_err}"
            )
        if not solution_ok:
            failures.append(
                f"{task.name}: check failed on reference solution "
                f"(exit {solution_code})\n{solution_out}\n{solution_err}"
            )
        if args.verbose:
            print(f"  starter exit: {starter_code}")
            print(f"  solution exit: {solution_code}")

    if failures:
        print(f"\n{len(failures)} task verification failure(s):\n")
        for failure in failures:
            print(failure)
            print()
        return 1

    print(f"\nOK: {len(tasks)} tasks fail on starter and pass on solution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
