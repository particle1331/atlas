# M1 notes

## D1: choices to copy or reject

Read: Anthropic, "Building effective agents" (Dec 2024); mini-swe-agent's
`DefaultAgent` loop (`agents/default.py`).

1. **Copy: keep the loop small and framework-free.** Anthropic's main finding is
   that the successful systems were simple, composable patterns, not framework
   stacks. mini-swe-agent's core is a `while` loop over `query()` and
   `execute_actions()`. **Reject:** workflow, routing, and multi-agent patterns
   for this baseline; they add variables before there is a measured single-agent
   baseline.

2. **Copy: make stop conditions explicit and independent.** mini-swe-agent has a
   step limit, cost limit, and wall-time limit; Anthropic calls out maximum
   iterations as a control. This loop stops on no tool call, 20 turns, a token
   budget, or an API error. **Reject:** a cost-only limit, because a cheap model
   can still flood the context with tool output.

3. **Copy: environment observations are the ground truth.** Both sources show
   the model acting, receiving the tool result, and continuing. Errors and
   timeouts are observations, not exceptions that kill the run. **Reject:**
   unbounded tool output. `bash`, `read_file`, and `write_file` truncate output
   before it enters the context, and `bash` kills its process group on timeout.

4. **Copy: tool descriptions are prompts and need testing.** Anthropic's
   appendix recommends clear boundaries, example usage, poka-yoke arguments,
   and iterating on the agent-computer interface. **Reject:** a large tool
   surface. Start with three tools (`bash`, `read_file`, `write_file`) and make
   paths relative and sandbox-checked.

5. **Copy: log the trajectory and account for cost.** mini-swe-agent serializes
   the full trajectory and tracks `instance_cost` and `api_calls`; this baseline
   logs messages, per-turn usage, cache-hit/miss tokens, cost, latency, and the
   stop reason. **Reject:** treating token totals as cost. DeepSeek prices
   cache-hit input, cache-miss input, and output separately, and doubles the
   rate during peak hours.

## D2-D3: implementation

- `agent/loop.py`: native OpenAI-style tool calls against DeepSeek
  (`deepseek-flash`, thinking disabled, temperature 0). No seed is sent because
  DeepSeek does not support one.
- `agent/tools.py`: sandboxed `bash`, `read_file`, `write_file`.
- `agent/log.py`: cost accounting and JSONL helpers.
- `run_eval.py`: copies `starter/` to a temp directory, runs the agent, then
  runs `check.sh` outside the agent's reach.
- `verify_tasks.py`: proves every check fails on starter files and passes on the
  reference solution.

## D4: task suite

20 tasks, each with a deterministic check:

| Tier | Tasks |
| --- | --- |
| Anchors | 001 off-by-one, 003 CSV total, 006 rename function, 009 shell script, 014 failing test |
| Hard | 021 JSON parser, 022 expression evaluator, 023 CSV parser, 024 semver sort, 027 apply patch, 028 large-file bug hunt, 029 wildcard match, 031 INI parser, 032 template engine, 035 stack VM |
| Very hard | 036 regex engine, 037 JSON schema, 038 Lisp interpreter, 039 cron scheduler, 040 unified diff |

The five old easy tasks (025, 026, 030, 033, 034) were removed after the
intermediate retune because they did not add discriminating signal.

`uv run python verify_tasks.py --verbose` passes for all 20.

## D5: baseline

Ran 2026-11-02 with `deepseek-flash`, temperature 0, non-thinking, 20 tasks x 3
runs. Full result: `results/baseline.json`; summary: `results/baseline.md`;
traces: `results/logs/eval-20261102T052757Z.jsonl`.

| Metric | Value |
| --- | ---: |
| Mean pass rate | 76.7% (std 7.6 across runs) |
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

The pass rate is inside the required 20%-80% band. The suite has 14 failed
traces, so D6 can be completed. Most remaining failures are concentrated in
037, 038, and 040; 023, 032, and 035 each fail one or two runs.

## D6: failure analysis

Read five failed traces in full from the final baseline. Tags use the candidate
list below; evidence is from the saved JSONL and check output.

| Trace | Evidence | Tag | Next hypothesis |
| --- | --- | --- | --- |
| 032-template-engine#2 | `no_tool_call` at 4 turns; check line 19: `accepted invalid template: '{{ name'`. The agent tested valid rendering but never asserted that an unbalanced opening tag raises. | skipped verification | Add malformed-input self-tests and require the parser to reject leftover/unclosed state at EOF. |
| 036-regex-engine#2 | `token_budget` at 12 turns; check line 42: `accepted invalid pattern: 'a|'`. The agent's own test output listed `a|` as accepted, then kept debugging the matcher until the budget ran out. | bad plan (token budget) | Validate parser edge cases before matcher debugging; add a hard stop when a known failing case is already identified. |
| 037-json-schema#1 | `no_tool_call` at 4 turns; check line 12 (first assertion). The agent emits `$.extra: additionalProperties`; the check expects root `$: additionalProperties`. The prompt does not specify the error path for this keyword. | ambiguous task | State the `additionalProperties` error-path convention in the prompt and pin it with a check case. |
| 038-lisp-interpreter#1 | `token_budget` at 10 turns; check line 21: `(quote (1 2 3)) == [1, 2, 3]`. The agent returns an internal `Pair` chain; the prompt does not say lists must be Python lists. | ambiguous task | State the runtime list representation in the prompt, or normalize `Pair` to a Python list at the API boundary. |
| 040-unified-diff#1 | `token_budget` at 10 turns; check line 5 (basic replacement). The agent appends a trailing newline; the check expects none. It also clamps `context < 0` to 0, while the check expects `ValueError`, which the prompt does not state. | ambiguous task | Specify trailing-newline and negative-context behavior in the prompt and pin both with check cases. |

Candidate tags: tool misuse, context loss, bad plan, skipped verification,
environment issue, ambiguous task, check bug.

Three of the five representative failures are tagged ambiguous-task, not model
capability failures. Before M2 freezes a larger suite, make output conventions
(representation, error paths, trailing newlines, invalid-argument behavior)
explicit in prompts or checks.

## Open questions

- DeepSeek does not support `seed`; three runs measure run-to-run variance
  instead of pretending the run is deterministic.
- The cost model uses DeepSeek's 2026-11-02 list prices and ignores Chinese
  public holidays in the peak/off-peak calendar.
- The task suite is intentionally small and hand-written. M2 grows it to 100+
  tasks with a frozen train/test split.
