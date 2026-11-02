#!/usr/bin/env python3
"""Run the frozen M1 baseline: every task, N times, with logs and cost."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.log import (
    PRICING_SNAPSHOT,
    append_jsonl,
    git_commit,
    sha256_text,
    sha256_tree,
    utc_now,
)
from agent.loop import get_client, run_agent

ROOT = Path(__file__).resolve().parent
TASKS_DIR = ROOT / "tasks"
RESULTS_DIR = ROOT / "results"


def discover_tasks(pattern: str | None = None) -> list[Path]:
    tasks = sorted(
        path
        for path in TASKS_DIR.iterdir()
        if path.is_dir()
        and (path / "prompt.md").is_file()
        and (path / "starter").is_dir()
        and (path / "check.sh").is_file()
    )
    if pattern:
        tasks = [path for path in tasks if pattern in path.name]
    return tasks


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def task_fingerprint(task_dir: Path) -> dict[str, str]:
    return {
        "prompt_sha256": sha256_text((task_dir / "prompt.md").read_text("utf-8")),
        "starter_sha256": sha256_tree(task_dir / "starter"),
        "check_sha256": sha256_text((task_dir / "check.sh").read_text("utf-8")),
    }


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


def prepare_sandbox(task_dir: Path) -> Path:
    sandbox = Path(tempfile.mkdtemp(prefix=f"m1-{task_dir.name}-"))
    shutil.copytree(task_dir / "starter", sandbox, dirs_exist_ok=True)
    return sandbox


def config_dict(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "model": args.model,
        "temperature": args.temperature,
        "max_turns": args.max_turns,
        "token_budget": args.token_budget,
        "tool_timeout_s": args.tool_timeout,
        "check_timeout_s": args.check_timeout,
        "max_output_chars": args.max_output_chars,
        "max_tokens": args.max_tokens,
        "thinking": args.thinking,
        "seed_supported": False,
        "pricing_snapshot": PRICING_SNAPSHOT,
    }


def run_one(
    task_dir: Path,
    run_index: int,
    args: argparse.Namespace,
    client: Any,
    log_path: Path,
) -> dict[str, Any]:
    sandbox = prepare_sandbox(task_dir)
    fingerprint = task_fingerprint(task_dir)
    started_at = utc_now()
    try:
        prompt = (task_dir / "prompt.md").read_text("utf-8")
        try:
            agent_result = run_agent(
                prompt,
                sandbox,
                model=args.model,
                temperature=args.temperature,
                max_turns=args.max_turns,
                token_budget=args.token_budget,
                tool_timeout_s=args.tool_timeout,
                max_output_chars=args.max_output_chars,
                max_tokens=args.max_tokens,
                thinking=args.thinking,
                client=client,
                verbose=args.verbose,
            )
        except Exception as exc:
            agent_result = {
                "stop_reason": "exception",
                "error": f"{type(exc).__name__}: {exc}",
                "turns": 0,
                "tool_calls": 0,
                "usage": {},
                "cost_usd": 0.0,
                "latency_s": 0.0,
                "turn_log": [],
                "messages": [],
            }
        check_code, check_stdout, check_stderr = run_check(
            task_dir, sandbox, args.check_timeout
        )
        record = {
            "id": f"{task_dir.name}#{run_index}",
            "task": task_dir.name,
            "run": run_index,
            "passed": check_code == 0,
            "check_exit": check_code,
            "check_stdout": check_stdout[-4000:],
            "check_stderr": check_stderr[-4000:],
            "started_at": started_at.isoformat(),
            "finished_at": utc_now().isoformat(),
            "task_fingerprint": fingerprint,
            "config": config_dict(args),
            "agent": agent_result,
        }
        append_jsonl(log_path, record)
        return record
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


def cache_totals(records: list[dict[str, Any]]) -> tuple[int, int]:
    hit_tokens = 0
    miss_tokens = 0
    for record in records:
        usage = record["agent"].get("usage", {})
        hit = int(usage.get("prompt_cache_hit_tokens", 0))
        miss = usage.get("prompt_cache_miss_tokens")
        if miss is None:
            miss = max(int(usage.get("prompt_tokens", 0)) - hit, 0)
        hit_tokens += hit
        miss_tokens += max(int(miss), 0)
    return hit_tokens, miss_tokens


def aggregate(
    records: list[dict[str, Any]],
    tasks: list[Path],
    args: argparse.Namespace,
    log_path: Path,
) -> dict[str, Any]:
    per_task: dict[str, Any] = {}
    for task in tasks:
        task_records = [record for record in records if record["task"] == task.name]
        passes = [record["passed"] for record in task_records]
        per_task[task.name] = {
            "runs": len(task_records),
            "passes": sum(passes),
            "pass_rate": sum(passes) / len(passes) if passes else 0.0,
            "mean_cost_usd": (
                statistics.fmean(
                    record["agent"].get("cost_usd", 0.0) for record in task_records
                )
                if task_records
                else 0.0
            ),
            "median_turns": (
                statistics.median(
                    record["agent"].get("turns", 0) for record in task_records
                )
                if task_records
                else 0
            ),
            "fingerprint": task_fingerprint(task),
        }

    per_run_rates = []
    for run_index in range(1, args.runs + 1):
        run_records = [record for record in records if record["run"] == run_index]
        if run_records:
            per_run_rates.append(
                sum(record["passed"] for record in run_records) / len(run_records)
            )

    total_runs = len(records)
    total_cost = sum(record["agent"].get("cost_usd", 0.0) for record in records)
    cache_hit_tokens, cache_miss_tokens = cache_totals(records)
    prompt_tokens = cache_hit_tokens + cache_miss_tokens
    stop_reasons = Counter(
        record["agent"].get("stop_reason", "unknown") for record in records
    )
    failures = [
        {
            "id": record["id"],
            "task": record["task"],
            "run": record["run"],
            "stop_reason": record["agent"].get("stop_reason"),
            "error": record["agent"].get("error"),
            "turns": record["agent"].get("turns"),
            "check_exit": record["check_exit"],
            "check_stderr": record["check_stderr"][-1000:],
        }
        for record in records
        if not record["passed"]
    ]

    return {
        "generated_at": utc_now().isoformat(),
        "git_commit": git_commit(ROOT),
        "log_file": display_path(log_path),
        "pricing_snapshot": PRICING_SNAPSHOT,
        "config": config_dict(args),
        "summary": {
            "tasks": len(tasks),
            "runs_per_task": args.runs,
            "total_runs": total_runs,
            "total_passes": sum(record["passed"] for record in records),
            "mean_pass_rate": (
                statistics.fmean(per_run_rates) if per_run_rates else 0.0
            ),
            "pass_rate_std": (
                statistics.stdev(per_run_rates) if len(per_run_rates) > 1 else 0.0
            ),
            "per_run_pass_rates": per_run_rates,
            "total_cost_usd": total_cost,
            "mean_cost_per_task_usd": total_cost / total_runs if total_runs else 0.0,
            "median_turns": (
                statistics.median(record["agent"].get("turns", 0) for record in records)
                if records
                else 0
            ),
            "median_latency_s": (
                statistics.median(
                    record["agent"].get("latency_s", 0.0) for record in records
                )
                if records
                else 0.0
            ),
            "total_tokens": sum(
                record["agent"].get("usage", {}).get("total_tokens", 0)
                for record in records
            ),
            "prompt_tokens": prompt_tokens,
            "cache_hit_tokens": cache_hit_tokens,
            "cache_miss_tokens": cache_miss_tokens,
            "cache_hit_rate": (
                cache_hit_tokens / prompt_tokens if prompt_tokens else 0.0
            ),
            "stop_reasons": dict(stop_reasons),
        },
        "per_task": per_task,
        "failures": failures,
        "runs": [
            {
                "id": record["id"],
                "task": record["task"],
                "run": record["run"],
                "passed": record["passed"],
                "stop_reason": record["agent"].get("stop_reason"),
                "turns": record["agent"].get("turns"),
                "tool_calls": record["agent"].get("tool_calls"),
                "cost_usd": record["agent"].get("cost_usd"),
                "latency_s": record["agent"].get("latency_s"),
                "total_tokens": record["agent"].get("usage", {}).get("total_tokens", 0),
                "check_exit": record["check_exit"],
            }
            for record in records
        ],
    }


def write_markdown(baseline: dict[str, Any], path: Path) -> None:
    summary = baseline["summary"]
    config = baseline["config"]
    lines = [
        "# M1 baseline",
        "",
        f"- Generated: {baseline['generated_at']}",
        f"- Git commit: `{baseline['git_commit']}`",
        f"- Model: `{config['model']}` (temperature {config['temperature']}, "
        f"thinking {config['thinking']})",
        f"- Runs per task: {summary['runs_per_task']}",
        f"- Mean pass rate: {summary['mean_pass_rate']:.1%} "
        f"(std {summary['pass_rate_std']:.1%} across runs)",
        f"- Cost per task: ${summary['mean_cost_per_task_usd']:.4f}",
        f"- Median turns: {summary['median_turns']}",
        f"- Total cost: ${summary['total_cost_usd']:.4f}",
        f"- Cache hit rate: {summary['cache_hit_rate']:.1%} "
        f"({summary['cache_hit_tokens']:,} hit / {summary['prompt_tokens']:,} prompt tokens)",
        f"- Stop reasons: `{summary['stop_reasons']}`",
        "",
        "## Per task",
        "",
        "| Task | Pass rate | Mean cost | Median turns |",
        "| --- | ---: | ---: | ---: |",
    ]
    for task_name, stats in baseline["per_task"].items():
        lines.append(
            f"| {task_name} | {stats['pass_rate']:.0%} | "
            f"${stats['mean_cost_usd']:.4f} | {stats['median_turns']} |"
        )
    lines.extend(
        [
            "",
            "## Failures",
            "",
            f"{len(baseline['failures'])} failed runs. Full traces: "
            f"`{baseline['log_file']}`.",
            "",
        ]
    )
    for failure in baseline["failures"][:30]:
        lines.append(
            f"- `{failure['id']}`: {failure['stop_reason']}, "
            f"check exit {failure['check_exit']}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3, help="Runs per task.")
    parser.add_argument("--task", default=None, help="Only tasks whose name matches.")
    parser.add_argument("--model", default="deepseek-flash")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-turns", type=int, default=20)
    parser.add_argument(
        "--token-budget",
        type=int,
        default=60_000,
        help="Stop a run after this many total tokens (0 disables).",
    )
    parser.add_argument("--tool-timeout", type=int, default=30)
    parser.add_argument("--check-timeout", type=int, default=60)
    parser.add_argument("--max-output-chars", type=int, default=8000)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--thinking", action="store_true")
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "baseline.json")
    parser.add_argument("--log-dir", type=Path, default=RESULTS_DIR / "logs")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    return args


def main() -> int:
    args = parse_args()
    tasks = discover_tasks(args.task)
    if not tasks:
        print("No tasks found.")
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.log_dir.mkdir(parents=True, exist_ok=True)
    eval_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = args.log_dir / f"eval-{eval_id}.jsonl"
    try:
        client = get_client()
    except RuntimeError as exc:
        print(f"Error: {exc}")
        return 1

    print(
        f"Running {len(tasks)} tasks x {args.runs} runs with {args.model} "
        f"(temperature {args.temperature})"
    )
    records: list[dict[str, Any]] = []
    for task in tasks:
        for run_index in range(1, args.runs + 1):
            print(f"[{task.name} {run_index}/{args.runs}]", flush=True)
            record = run_one(task, run_index, args, client, log_path)
            records.append(record)
            status = "PASS" if record["passed"] else "FAIL"
            agent = record["agent"]
            print(
                f"  {status} stop={agent.get('stop_reason')} "
                f"turns={agent.get('turns')} "
                f"cost=${agent.get('cost_usd', 0.0):.4f} "
                f"latency={agent.get('latency_s', 0.0):.1f}s",
                flush=True,
            )

    baseline = aggregate(records, tasks, args, log_path)
    args.out.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
    markdown_path = args.out.with_suffix(".md")
    write_markdown(baseline, markdown_path)

    summary = baseline["summary"]
    print("\nBaseline")
    print(f"  mean pass rate: {summary['mean_pass_rate']:.1%}")
    print(f"  cost per task:  ${summary['mean_cost_per_task_usd']:.4f}")
    print(f"  median turns:   {summary['median_turns']}")
    print(f"  total cost:     ${summary['total_cost_usd']:.4f}")
    if not 0.20 <= summary["mean_pass_rate"] <= 0.80:
        print(
            "  WARNING: mean pass rate is outside the planned 20%-80% band; "
            "retune task difficulty."
        )
    print(f"  results:        {args.out}")
    print(f"  markdown:       {markdown_path}")
    print(f"  traces:         {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
