#!/usr/bin/env python3
"""List runs or print one full trace from an eval JSONL log."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_records(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def print_list(records: list[dict[str, Any]]) -> None:
    for record in records:
        agent = record.get("agent", {})
        status = "PASS" if record.get("passed") else "FAIL"
        print(
            f"{status:4} {record.get('id', '?'):40} "
            f"stop={agent.get('stop_reason', '?'):12} "
            f"turns={agent.get('turns', '?')!s:3} "
            f"cost=${agent.get('cost_usd', 0.0):.4f}"
        )


def print_trace(record: dict[str, Any]) -> None:
    agent = record.get("agent", {})
    print(f"id: {record.get('id')}")
    print(f"passed: {record.get('passed')}")
    print(f"stop: {agent.get('stop_reason')}")
    print(f"error: {agent.get('error')}")
    print(f"turns: {agent.get('turns')}")
    print(f"usage: {agent.get('usage')}")
    print(f"cost_usd: {agent.get('cost_usd')}")
    print(f"check_exit: {record.get('check_exit')}")
    print(f"check_stdout: {record.get('check_stdout', '').strip()}")
    print(f"check_stderr: {record.get('check_stderr', '').strip()}")
    print("\n--- messages ---")
    for index, message in enumerate(agent.get("messages", [])):
        role = message.get("role", "?")
        print(f"\n[{index}] {role}")
        content = message.get("content")
        if content:
            print(content)
        for call in message.get("tool_calls", []) or []:
            function = call.get("function", {})
            print(f"tool_call {function.get('name')}: {function.get('arguments')}")
        if message.get("tool_call_id"):
            print(f"tool_call_id: {message['tool_call_id']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="results/logs/eval-*.jsonl")
    parser.add_argument("--id", help="Run id to print, e.g. 001-fix-off-by-one#1")
    parser.add_argument("--list", action="store_true", help="List runs instead.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    records = load_records(args.log)
    if args.list or not args.id:
        print_list(records)
        return 0
    matches = [record for record in records if record.get("id") == args.id]
    if not matches:
        print(f"No run with id {args.id!r}.")
        return 1
    print_trace(matches[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
