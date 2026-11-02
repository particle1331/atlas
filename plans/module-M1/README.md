# M1: agent loop and baseline

A from-scratch tool-calling agent, 20 deterministic tasks, and a frozen
baseline. No agent framework.

Start with the [Week 1 learning guide](LEARNING_GUIDE.md) for six study
sessions, exercises, and checkpoints using the existing lab and saved traces.

## Setup

```sh
cd plans/module-M1
uv sync
```

Provide a DeepSeek API key in the repository-root `.env` (copy
`.env.example` and fill in `DEEPSEEK_API_KEY=`), in the environment:

```sh
export DEEPSEEK_API_KEY=...
```

or through the Atlas vault from the repository root:

```sh
uv run at vault set DEEPSEEK_API_KEY
```

The loop loads the nearest `.env`, then reads `DEEPSEEK_API_KEY` from the
environment, then falls back to `atlas.vault` via `keyring`.
`DEEPSEEK_BASE_URL` defaults to `https://api.deepseek.com`.

## Verify the task suite (no API calls)

```sh
uv run python verify_tasks.py --verbose
```

Every `check.sh` must fail on `starter/` and pass on `solution/`. Do this before
spending API tokens.

## Run the baseline

```sh
uv run python run_eval.py --runs 3
```

Outputs:

- `results/baseline.json`: machine-readable summary.
- `results/baseline.md`: human-readable table.
- `results/logs/eval-<timestamp>.jsonl`: one record per run, including the full
  message trace, per-turn usage, cost, and tool calls.

Smoke-test one task first:

```sh
uv run python run_eval.py --task 001 --runs 1 --verbose
```

Inspect failures for the D6 writeup:

```sh
uv run python inspect_run.py results/logs/eval-<timestamp>.jsonl --list
uv run python inspect_run.py results/logs/eval-<timestamp>.jsonl --id 001-fix-off-by-one#1
```

## Agent design

`agent/loop.py` calls DeepSeek with native tool calls and stops on:

- a response with no tool call (the model's final answer),
- `--max-turns` (default 20),
- `--token-budget` total tokens (default 60000),
- an API error after the SDK's retries.

`agent/tools.py` exposes `bash`, `read_file`, and `write_file`. Paths are
resolved inside the sandbox, `bash` has a timeout and kills its process group,
and tool output is truncated before it reaches the context. `run_eval.py` copies
only `starter/` into a temp directory, so the agent cannot see or edit
`check.sh` or `solution/`.

`agent/log.py` computes cost from DeepSeek's cache-hit, cache-miss, and output
token counts. DeepSeek does not support a `seed` parameter, so the baseline
records model and temperature and uses three runs to measure variance.

## Tasks

Each task has:

```text
tasks/NNN-name/
  prompt.md      # the task given to the agent
  starter/       # copied into a temp sandbox
  solution/      # reference solution, never shown to the agent
  check.sh       # runs in the sandbox; exit 0 means pass
```

The 20 tasks cover bug fixes, implementations, file I/O, a shell script, a
failing unit test, CLI arguments, and a data transformation. They are small
enough to finish within 20 turns.
