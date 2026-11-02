# M1: agent loop and baseline

Status: **complete. The final baseline passes 76.7% (46/60), inside the required
20%-80% band; five failed traces are tagged in `module-M1/NOTES.md` D6.**
Week 1 is M1 only; B1 is deferred.

This is the working plan for M1 from
[`18-week-plan.md`](18-week-plan.md#m1-agent-loop-and-baseline). The lab lives
in [`module-M1/`](module-M1/) so the plan and artifacts stay together.

## Decisions

| Decision | Value | Reason |
| --- | --- | --- |
| Model | `deepseek-flash` (DeepSeek V4.1 Flash) | Cheap, capable, native tool calls; user choice. |
| Mode | Non-thinking, temperature 0 | Thinking mode ignores temperature and adds reasoning tokens; non-thinking keeps the baseline cheap. |
| Seed | Not sent | DeepSeek does not support `seed`. Three runs measure variance instead. |
| Framework | None | Plan requires a from-scratch loop; Anthropic's guidance favors simple composable patterns. |
| Tools | `bash`, `read_file`, `write_file` | Small ACI; bash has timeout and process-group kill; file paths are sandbox-checked. |
| Stop conditions | No tool call, 20 turns, 60k tokens, API error | Explicit, independent limits. |
| Pricing | DeepSeek list prices, 2026-11-02, cache-aware, peak/off-peak | Cached-token pricing is a named pitfall. |
| Sandbox | Temp copy of `starter/`; `check.sh` and `solution/` stay outside | Agent cannot edit the test or see the reference solution. |

## Deliverables

| Artifact | Path |
| --- | --- |
| Loop (<=250 lines, no framework) | [`module-M1/agent/loop.py`](module-M1/agent/loop.py) |
| Tools | [`module-M1/agent/tools.py`](module-M1/agent/tools.py) |
| Logging and cost | [`module-M1/agent/log.py`](module-M1/agent/log.py) |
| 20 tasks | [`module-M1/tasks/`](module-M1/tasks/) |
| Eval runner | [`module-M1/run_eval.py`](module-M1/run_eval.py) |
| Trace inspector | [`module-M1/inspect_run.py`](module-M1/inspect_run.py) |
| Task verifier | [`module-M1/verify_tasks.py`](module-M1/verify_tasks.py) |
| Baseline result | `module-M1/results/baseline.json` |
| Notes | [`module-M1/NOTES.md`](module-M1/NOTES.md) |
| Unit tests | [`module-M1/tests/`](module-M1/tests/) |

## Baseline result (2026-11-02)

`deepseek-flash`, temperature 0, non-thinking, 20 tasks x 3 runs:

| Metric | Value |
| --- | ---: |
| Pass rate | 76.7% (std 7.6) |
| Per-run pass rates | 85.0%, 70.0%, 75.0% |
| Passes | 46 / 60 |
| Cost per task | $0.00150 |
| Total cost | $0.0900 |
| Median turns | 4.0 |
| Median latency | 7.47 s |
| Total tokens | 1,005,684 |
| Prompt tokens | 888,498 |
| Cache-hit tokens | 772,864 (87.0% of prompt tokens) |
| Stop reasons | `no_tool_call` 51, `token_budget` 9 |
| Failed runs | 14 |

The pass rate is inside the required 20%-80% band. Fourteen failed traces are
available; five are tagged in [`module-M1/NOTES.md`](module-M1/NOTES.md) D6.
Most failures concentrate in 037, 038, and 040; 023, 032, and 035 each fail one
or two runs.

### Retune log

| Run | Suite | Pass rate | Failed runs | Outcome |
| --- | --- | ---: | ---: | --- |
| First | 5 anchors + 15 easy tasks | 100.0% | 0 | Too easy; zero traces for D6. |
| Intermediate | 5 anchors + 15 harder tasks | 91.7% | 5 | Still too easy; 5 traces available for D6. |
| Final | 5 anchors + 10 harder + 5 very hard tasks | 76.7% | 14 | In band; D6 tagged. |

## Teaching outline

A 90-120 minute walkthrough. Each step points at an artifact, gives a
discussion prompt, and ends with a checkpoint.

### 1. Frame the experiment (10 min)

- Goal: build the smallest loop that can edit files, then measure it before
  adding frameworks or optimizations.
- Show: the Decisions table and Done criteria above.
- Discuss: which variables are frozen? Why is a 20%-80% pass band more useful
  than 100%?
- Checkpoint: write down the independent variables (model, prompts, tools, stop
  limits, checks) and dependent variables (pass rate, cost/task, turns,
  latency, cache hit rate).

### 2. Trace one run end to end (15 min)

- Show: [`module-M1/agent/loop.py`](module-M1/agent/loop.py). Follow messages ->
  model -> tool calls -> observations -> next turn.
- Discuss: why tool results are observations, not exceptions; why the loop stops
  on no tool call, max turns, token budget, or API error.
- Checkpoint: explain what happens at turn 0, after a successful tool call,
  after a tool error, and at the final no-tool-call turn.

### 3. Design the ACI, not just the tools (15 min)

- Show: [`module-M1/agent/tools.py`](module-M1/agent/tools.py): relative paths,
  sandbox checks, 8k truncation, 30s bash timeout, process-group kill.
- Discuss: tool descriptions are prompts; a small tool surface is easier to
  evaluate; which failures each tool invites.
- Checkpoint: propose one new tool and list the failure modes it would add.

### 4. Make cost and caching visible (15 min)

- Show: [`module-M1/agent/log.py`](module-M1/agent/log.py) and a JSONL trace.
  Separate prompt, cache-hit, cache-miss, and completion tokens.
- Discuss: total tokens are not cost; DeepSeek prices cache hit, cache miss, and
  output separately; peak/off-peak doubles the rates.
- Checkpoint: compute cost and cache hit rate for one trace by hand. Use
  `hit / (hit + miss)`, not `hit / total_tokens`.

### 5. Design tasks that measure the loop (20 min)

- Show: one task's `prompt.md`, `starter/`, `solution/`, and `check.sh`; run
  [`module-M1/verify_tasks.py`](module-M1/verify_tasks.py).
- Discuss: fail-to-pass checks, deterministic checks, sandboxing the check,
  anchors vs. hard tasks, and the 20%-80% band.
- Checkpoint: explain why a check that passes on the starter invalidates the
  task, and why a check that only tests the reference solution is not enough.

### 6. Run and read the baseline (15 min)

- Show: `run_eval.py --runs 3`, `results/baseline.json`,
  `results/baseline.md`, and the JSONL.
- Discuss: mean vs. per-run pass rate, variance without a seed, median turns,
  cost per task, and stop reasons.
- Checkpoint: decide whether the suite is too easy, too hard, or in band;
  identify which metric drove the decision.

### 7. Turn failures into the next hypothesis (15 min)

- Show: `inspect_run.py --list` and `inspect_run.py --id`; read five failures
  in full.
- Discuss: tag root causes (tool misuse, context loss, bad plan, skipped
  verification, environment issue, ambiguous task, check bug); separate model
  failures from task/check failures.
- Checkpoint: write one concrete change and the metric it should move.

### 8. Close the loop (10 min)

- Show: [`module-M1/NOTES.md`](module-M1/NOTES.md) D1/D5/D6 and this page's Done
  criteria.
- Discuss: what would invalidate the baseline (prompt edit, task edit, model
  change, tool change, check change)? Why freeze the commit?
- Checkpoint: record the final artifacts and commit; state the next experiment.

## Caching: how to get a high cache hit

DeepSeek caches repeated prompt prefixes automatically; there is no
`cache_control` flag. The cache hit rate is
`cache_hit_tokens / (cache_hit_tokens + cache_miss_tokens)`. The baseline logs
both token counts and prices them separately.

Rules for a high cache hit rate:

1. Keep the system prompt and tool schema byte-identical across runs.
2. Put static instructions and examples first; put task-specific text after the
   stable prefix.
3. Append messages; never edit, reorder, or delete earlier messages.
4. Avoid timestamps, random IDs, absolute paths, or nondeterministic JSON in the
   prefix.
5. Keep tool output bounded and stable; large unique observations early in the
   conversation reduce reuse.
6. Use the same model and endpoint; the cache is provider/model-specific.
7. Measure `hit / (hit + miss)`; `hit / total_tokens` understates the rate
   because it includes completion tokens.

Cached input is much cheaper and usually faster. In the first baseline,
196,202 / 250,912 prompt tokens were cache hits (78.2%). The intermediate retune
was 411,904 / 487,637 (84.5%); the final baseline was 772,864 / 888,498 (87.0%).
Higher is not automatically better if it comes from repeating a bad prefix;
cache hit rate is an efficiency metric, not a quality metric.

## Runbook

```sh
cd plans/module-M1
uv sync

# No API calls: every check fails on starter, passes on solution.
uv run python verify_tasks.py --verbose

# Unit tests for the loop, tools, and stop conditions.
uv run python -m unittest discover -s tests -v

# Smoke test one task (put DEEPSEEK_API_KEY=... in the repo-root .env first).
uv run python run_eval.py --task 001 --runs 1 --verbose

# Frozen baseline: 20 tasks x 3 runs.
uv run python run_eval.py --runs 3
```

The key can come from the repo-root `.env` (see `.env.example`) or the Atlas
vault:

```sh
uv run at vault set DEEPSEEK_API_KEY
```

## Done criteria

- [x] `agent/loop.py` is 250 lines or fewer and uses no agent framework.
- [x] 20 tasks, each with `prompt.md`, `starter/`, `solution/`, `check.sh`.
- [x] Every check fails on starter files and passes on the reference solution.
- [x] JSONL logs include messages, tokens, cache tokens, cost, latency, and stop
  reason.
- [x] Bash timeout, output truncation, sandbox path checks.
- [x] Unit tests pass without an API key.
- [x] Baseline over 20 tasks x 3 runs, frozen model/prompt/temperature.
- [x] Mean pass rate between 20% and 80% (final: 76.7%, 46/60).
- [x] Cost per task and median turns reported in `results/baseline.json`.
- [x] Five failed traces read in full and tagged with a root cause in
  `NOTES.md`.

## Pitfall checklist

- Unbounded tool output: capped at 8k chars per stream/file.
- No bash timeout: 30s default, process group killed on timeout.
- Check passes on untouched starter: `verify_tasks.py` enforces failure.
- Running outside a sandbox: `run_eval.py` copies starter to a temp dir and
  resolves every tool path inside it.
- Ignoring cached-token pricing: cost uses `prompt_cache_hit_tokens` and
  `prompt_cache_miss_tokens`, with peak/off-peak rates.
- Agent edits the test: `check.sh` and `solution/` are never copied into the
  sandbox; tasks 014 and 028 also hash their test files.
