"""A minimal tool-calling agent loop with explicit stop conditions."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from agent.log import (
    DEFAULT_MODEL,
    add_usage,
    compute_cost,
    usage_to_dict,
    utc_now,
)
from agent.tools import TOOL_SPECS, ToolExecutor
from dotenv import load_dotenv
from openai import OpenAI

DEFAULT_SYSTEM_PROMPT = """\
You are a careful coding agent working alone in a sandbox directory.

You have three tools:
- bash: run a shell command in the sandbox root.
- read_file: read a UTF-8 text file relative to the sandbox root.
- write_file: write a UTF-8 text file relative to the sandbox root.

Rules:
- Work only inside the sandbox. Use relative paths.
- Inspect files before changing them.
- Make the smallest change that satisfies the task.
- Run commands to verify your work when possible.
- Do not ask questions. When finished, reply with a short summary and no tool calls.
"""


def get_api_key() -> str:
    load_dotenv()
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    try:
        import keyring

        key = (keyring.get_password("atlas.vault", "DEEPSEEK_API_KEY") or "").strip()
    except Exception:
        key = ""
    if not key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is not set. Add it to the repo-root .env, export "
            "it, or store it with `uv run at vault set DEEPSEEK_API_KEY` from "
            "the Atlas repo root."
        )
    return key


def get_client(api_key: str | None = None) -> OpenAI:
    return OpenAI(
        api_key=api_key or get_api_key(),
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        max_retries=5,
        timeout=120.0,
    )


def _assistant_message(message: Any) -> dict[str, Any]:
    data: dict[str, Any] = {"role": "assistant", "content": message.content}
    tool_calls = getattr(message, "tool_calls", None) or []
    if tool_calls:
        data["tool_calls"] = [
            {
                "id": call.id,
                "type": getattr(call, "type", "function"),
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
            for call in tool_calls
        ]
    reasoning = getattr(message, "reasoning_content", None)
    if reasoning:
        data["reasoning_content"] = reasoning
    return data


def run_agent(
    task_prompt: str,
    workspace: Path,
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    max_turns: int = 20,
    token_budget: int = 60_000,
    tool_timeout_s: int = 30,
    max_output_chars: int = 8000,
    max_tokens: int = 4096,
    system_prompt: str | None = None,
    thinking: bool = False,
    client: OpenAI | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    """Run the agent until a stop condition. Never raises for API/tool failures."""
    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    llm = client or get_client()
    executor = ToolExecutor(
        workspace, timeout_s=tool_timeout_s, max_output_chars=max_output_chars
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt or DEFAULT_SYSTEM_PROMPT},
        {"role": "user", "content": task_prompt},
    ]
    totals: dict[str, int] = {}
    turn_log: list[dict[str, Any]] = []
    total_cost = 0.0
    turns = 0
    tool_call_count = 0
    stop_reason = "max_turns"
    error: str | None = None
    started_at = utc_now()
    start = time.perf_counter()

    while turns < max_turns:
        if token_budget > 0 and totals.get("total_tokens", 0) >= token_budget:
            stop_reason = "token_budget"
            break
        turns += 1
        request_at = utc_now()
        turn_start = time.perf_counter()
        try:
            response = llm.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOL_SPECS,
                tool_choice="auto",
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body={
                    "thinking": {"type": "enabled" if thinking else "disabled"}
                },
            )
        except Exception as exc:
            stop_reason = "api_error"
            error = f"{type(exc).__name__}: {exc}"
            break

        latency_s = time.perf_counter() - turn_start
        usage = usage_to_dict(getattr(response, "usage", None))
        cost, cost_detail = compute_cost(model, usage, at=request_at)
        add_usage(totals, usage)
        total_cost += cost

        message = response.choices[0].message
        messages.append(_assistant_message(message))
        calls = getattr(message, "tool_calls", None) or []
        turn_log.append(
            {
                "turn": turns,
                "latency_s": round(latency_s, 4),
                "usage": usage,
                "cost_usd": cost,
                "cost_detail": cost_detail,
                "tool_calls": [call.function.name for call in calls],
            }
        )
        if verbose:
            print(
                f"  turn {turns}: {len(calls)} tool call(s), "
                f"{usage.get('total_tokens', 0)} tokens, "
                f"${cost:.6f}, {latency_s:.1f}s",
                flush=True,
            )

        if not calls:
            stop_reason = "no_tool_call"
            break

        for index, call in enumerate(calls):
            result = executor.execute(call.function.name, call.function.arguments)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id or f"call_{turns}_{index}",
                    "content": result,
                }
            )
            tool_call_count += 1

    return {
        "messages": messages,
        "turns": turns,
        "tool_calls": tool_call_count,
        "stop_reason": stop_reason,
        "error": error,
        "usage": totals,
        "cost_usd": total_cost,
        "latency_s": round(time.perf_counter() - start, 3),
        "turn_log": turn_log,
        "model": model,
        "temperature": temperature,
        "max_turns": max_turns,
        "token_budget": token_budget,
        "thinking": thinking,
        "started_at": started_at.isoformat(),
        "finished_at": utc_now().isoformat(),
    }
