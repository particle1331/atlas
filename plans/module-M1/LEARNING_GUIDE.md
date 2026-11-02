# Week 1 learning guide: agent loop and baseline

This week you will learn how a tool-using agent works, how to measure it, and
how to explain its failures. Budget **8 hours across six sessions**. Week 1 is
M1 only; Track B is deferred, as recorded in the [M1 plan](../module-M1.md).

The lab implementation and baseline already exist. Treat them as a worked
example: predict behavior, trace the code, and reconstruct the core ideas
yourself. The plan's completed deliverables describe the artifacts; the
checkpoints below measure your understanding.

By the end, you should be able to:

- Sketch the loop from a task to a model response, tool execution, observation,
  and the next model call.
- Explain who executes tools and how results get back to the model.
- Explain the stop conditions, context growth, and cost accounting.
- Distinguish an agent saying it is finished from an independent check passing.
- Read a failed trace and support a root-cause hypothesis with evidence.

You need basic Python: functions, dictionaries, lists, exceptions, and loops.
Learn unfamiliar SDK details as you encounter them. The week does not require
training a model or using a GPU.

## Start here today

Do Session 1 only. Open a separate page for your own answers and predictions;
keep the existing [NOTES.md](NOTES.md) as the worked answer to consult later.

All commands below run from the lab directory:

```sh
cd /Users/particle1331/code/latest/atlas/plans/module-M1
uv sync
```

Dependency setup may need internet access. Sessions 1–4 and the saved-trace
exercises need no model API calls. API setup is in the [lab README](README.md#setup).

## Your week

| Session | Time | Focus | What you produce |
| --- | ---: | --- | --- |
| 1 | 60 min | What makes this an agent? | Loop sketch and five design choices |
| 2 | 90 min | Messages and tool-call protocol | Annotated successful trace and pseudocode |
| 3 | 90 min | Tools and execution boundaries | Tool behavior table and limit predictions |
| 4 | 60 min | Tasks and independent checks | One task walkthrough and two proposed edge cases |
| 5 | 90 min | Baseline, context, and cost | Calculations and a short baseline interpretation |
| 6 | 90 min | Failure analysis and teach-back | Five trace annotations and a one-page writeup |

## Session 1 — Understand the system (60 min)

### Crucial concepts

**Feedback makes the loop useful.** A model can suggest a fix from a task
description, but an agent can inspect the actual file, attempt a change, run
a command, and choose its next action from the result. Each observation can
correct an earlier assumption. For example, a failed import may reveal that
the agent misunderstood the project layout. The loop lets it respond to that
evidence instead of continuing with its original plan unchanged.

**Control flow determines how much freedom the model has.** In a fixed
workflow, your code decides the sequence of operations in advance. In this
lab, the model chooses which available tool to request next and whether to
continue, while the harness defines the available actions and enforces limits.
Understanding this division helps you reason about behavior: a poor action
choice and a bug in tool execution are different problems with different fixes.

### Learn

For this lab, an agent is a program that repeatedly asks a model what to do,
executes requested tools, and returns observations to the model. The model
chooses actions; Python runs them. A tool request is structured data containing
a tool name and arguments. It does not execute itself.

The **harness** is the surrounding code that manages messages, executes tools,
enforces limits, and records results. A **trajectory** or **trace** is the
record of what happened during one task attempt.

```text
Task + instructions + tool descriptions
                  |
                  v
          Model receives messages
                  |
          Does it request tools?
             /           \
           yes            no
            |              |
   Python executes tools   Stop
            |
   Append tool observations
            |
   Check limits, then call model again
```

Read these two sources for about 30 minutes total:

1. [Anthropic: Building effective agents](https://www.anthropic.com/research/building-effective-agents).
   Focus on the workflow/agent distinction, framework tradeoffs, the Agents
   section, and Appendix 2 on tools. Write one reason to keep this lab simple.
2. [mini-swe-agent: DefaultAgent](https://mini-swe-agent.com/latest/reference/agents/default/).
   Find `run`, `step`, `query`, and `execute_actions`. Follow the control flow;
   you do not need to understand the entire library or install it.

Then skim [agent/loop.py](agent/loop.py), focusing on `run_agent()`.

### Do

Draw the loop from memory. Mark where the model, Python, and files participate.
Write five choices you would copy or reject for a first agent, with one reason
each. Consider tools, framework use, limits, observations, and logging.

### Checkpoint

Explain aloud: “The model requests `read_file`; what executes next, and how
does the file content reach the next model call?” If you can point to each
step in the code, move on.

## Session 2 — Follow one conversation (90 min)

### Crucial concepts

**Conversation history is the loop's working memory.** In this implementation,
each model request includes the accumulated messages. The model does not
automatically see the Python process's variables or the current filesystem;
file contents enter its context through tool observations. If Python writes a
file but never returns the tool result, the next model call lacks confirmation
that the action succeeded. Trace the messages to understand what evidence the
model actually had when it chose an action.

**Tool calling is a request-and-response protocol.** An assistant message
specifies a tool name and serialized arguments; Python interprets that request,
executes the tool, and adds a tool message linked by its call ID. That link
matters when a response requests several actions: each observation must be
associated with the correct request. Keeping requests, execution, and results
distinct also makes debugging possible—you can locate whether the problem
started in the model's arguments, the executor, or the returned observation.

### Learn

Read `run_agent()` in [agent/loop.py](agent/loop.py) slowly. Identify:

- `messages`: the conversation accumulated so far.
- `llm.chat.completions.create(...)`: the model request.
- `_assistant_message(...)`: conversion of the response into stored history.
- `executor.execute(...)`: actual tool execution.
- The message with `role="tool"`: the observation returned to the model.

The initial system message sets instructions. The user message supplies the
task. Assistant messages hold model replies and tool requests. Tool messages
hold execution results. A `tool_call_id` connects a result to its request.

One turn here means one attempted model request. A response may request more
than one tool, so turns and tool-call counts need not match. This implementation
executes requested tools sequentially.

### Do

Read the first task's [prompt](tasks/001-fix-off-by-one/prompt.md) and
[starter file](tasks/001-fix-off-by-one/starter/range_sum.py). Predict what a
successful agent would read, change, and verify. Then inspect the saved run:

```sh
uv run python inspect_run.py results/logs/eval-20261102T052757Z.jsonl \
  --id '001-fix-off-by-one#1'
```

Make a table with one row per message: role, request or observation, and what
the model can learn from it. Locate the first file inspection, edit,
verification command, and final response. Record if any expected step is absent.

Close `loop.py` and write 10–20 lines of pseudocode for the loop. Include message
updates, tool execution, and stopping. Compare it with the implementation.

### Checkpoint

Explain why a tool result must be added to `messages`. Explain why a final
“done” response does not prove the task passed.

## Session 3 — Understand tools and limits (90 min)

### Crucial concepts

**Tool design determines what the agent can learn and do.** A tool's name,
description, argument schema, and output format form an interface the model
must use correctly. Clear error messages give it a chance to recover; vague
errors make recovery harder. Truncation keeps a large file or command output
from dominating the conversation, but may hide a useful detail. Tool design
therefore involves choices about both execution behavior and the quality of
the evidence returned to the model.

**Limits bound resource use; they do not establish correctness.** A timeout
ends a slow command, a turn limit bounds repeated model calls, and a token
budget limits continued spending once usage reaches its threshold. None proves
the files are correct. Likewise, an instruction to stay inside a directory
expresses intended behavior, while path checks and operating-system permissions
determine what is enforced. Learn to identify the exact guarantee each control
provides rather than assuming one control covers every failure mode.

### Learn

Read [agent/tools.py](agent/tools.py), then
[tests/test_loop.py](tests/test_loop.py) and
[tests/test_tools.py](tests/test_tools.py).

The tool schema tells the model what it can request. The executor implements
the behavior. Path validation, error messages, truncation, and timeouts all
shape the observations available to the model. This interface is sometimes
called the **agent-computer interface**, or ACI.

Notice the execution boundary precisely: `read_file` and `write_file` validate
resolved paths against the workspace. `bash` starts with that workspace as its
current directory, but arbitrary shell commands can access paths outside it.
The temporary directory provides task separation; it is not an OS-enforced
security sandbox. Checks and reference solutions are omitted from the copied
workspace, rather than made inaccessible by filesystem isolation.

### Do

Before running anything, predict these behaviors and locate the relevant code:

| Situation | Your prediction | Code evidence |
| --- | --- | --- |
| `read_file` receives `../outside.txt` | | |
| Tool arguments contain malformed JSON | | |
| A shell command exceeds its timeout | | |
| A file or shell output exceeds the character limit | | |
| Every model response asks for another tool | | |
| A model response has no tool calls | | |
| Usage crosses the token budget during a request | | |
| The API request raises an exception after retries | | |

Run the local tests, which use a fake model client:

```sh
uv run python -m unittest discover -s tests -v
```

Study `test_tool_call_then_final_answer`. Predict the turn count and tool-call
count before reading its assertions. As a paper exercise, replace its final
answer with another tool request: what additional fake response would the test
need, or what limit would stop it?

### Checkpoint

Explain the difference between a tool error returned as an observation and an
API error that ends the run. Explain why the token budget can be exceeded: the
loop checks accumulated usage before the next request, rather than reserving a
hard allowance for the in-flight request.

## Session 4 — Decide what passing means (60 min)

### Crucial concepts

**An evaluation check turns a goal into an observable decision.** A request
such as “fix the function” needs explicit expected behavior before it can be
measured. Here, assertions compare function outputs with expected values and
the runner records the check's exit code. This makes scoring repeatable for a
given program and environment. It still measures only the cases and properties
the check covers: a solution can pass a few examples while failing on valid
inputs that were never tested.

**The prompt and the check must agree on the task.** A check that requires an
unstated output convention may reject a reasonable solution; a check that
ignores a stated requirement may accept an incomplete one. Validating both a
broken starter and a reference solution catches some mistakes in the evaluation
setup. Independent scoring also separates the agent's claim of success from
the observed result. These distinctions matter because an unreliable check
can make changes to the agent appear better or worse than they are.

### Learn

Read all parts of [task 001](tasks/001-fix-off-by-one/): `prompt.md`, the
starter, `check.sh`, and finally the reference solution. Then find
`prepare_sandbox`, `run_one`, and `run_check` in [run_eval.py](run_eval.py).

The prompt describes the requested behavior. The starter is the initial state.
The agent changes a temporary copy. The independent check runs afterward;
exit code 0 is recorded as a pass. The reference solution helps validate the
check, but the agent is not given it as part of its starting files.

### Do

Run the task verifier:

```sh
uv run python verify_tasks.py --verbose
```

For task 001, explain which assertion catches the original bug. Propose two
additional valid inputs and their expected results. Explain whether they add
coverage or just repeat an existing case.

Answer: could an incorrect implementation still pass the existing assertions?
Construct one on paper. This is why “fails on starter, passes on solution” is
a necessary check on the suite, but does not prove every checker is complete.

### Checkpoint

State the distinction between the model's final answer, the observed file
state, and the check's pass/fail result. Explain why a task whose untouched
starter passes would weaken this baseline.

## Session 5 — Read the baseline and account for cost (90 min)

### Crucial concepts

**A baseline is a defined experiment you can compare against.** Its result
depends on the model, instructions, tools, limits, tasks, and scoring rules
together. To investigate a change, hold the other conditions fixed and record
exactly what changed. Repeated attempts reveal some variability, but a small
suite and three repetitions leave substantial uncertainty. A higher average
on a later run is evidence to investigate, especially if the difference is
small compared with the variation already observed.

**Context length and cumulative token usage measure different things.** The
context is the input available to one model call; cumulative usage sums tokens
across calls, including earlier messages supplied again. If each turn adds
roughly the same amount of text and the full history is resent, later calls
get longer and total input usage can grow roughly quadratically with the number
of turns. Cache-hit pricing can reduce the price of repeated input without
removing it from the token count. This is why quality, turns, latency, and cost
need to be read together when interpreting an agent's performance.

### Learn

Read [results/baseline.md](results/baseline.md), the `summary` and `config`
fields of [results/baseline.json](results/baseline.json), and
`aggregate()` in [run_eval.py](run_eval.py).

The saved baseline has 20 tasks with three attempts each: 60 attempts total.
Its per-repetition pass rates are 85%, 70%, and 75%, averaging 76.7%. That is
inside M1's requested 20%–80% band. The band leaves room to observe both
successes and failures; it is not a general quality standard for agents.

The reported 7.6 standard deviation is about **7.6 percentage points across
three repetitions**, not a confidence interval. Three repetitions give a
limited view of variability. Temperature 0 should not be interpreted as a
guarantee of identical runs.

Read `compute_cost()` in [agent/log.py](agent/log.py). It prices cache-hit
input, cache-miss input, and output separately. Its rates are a dated snapshot
used by this lab; do not treat them as a live provider quote.

### Do

Compute these yourself, then compare with the saved summary:

```text
Pass rate       = passed attempts / total attempts
Cost per attempt = total cost / all attempts, including failures
Cache hit rate  = cache-hit input / (cache-hit input + cache-miss input)

Request cost = (hit tokens × hit rate
                + miss tokens × miss rate
                + output tokens × output rate) / 1,000,000
```

The field `mean_cost_per_task_usd` means cost per task attempt in this runner,
not the cost of all three attempts on one task. For a hand calculation, use
1,000 hit tokens, 2,000 miss tokens, 500 output tokens, and the stored
`deepseek-flash` off-peak rates in `log.py`.

Write three sentences interpreting pass rate, cost, and median turns. Then
explain context growth: earlier messages are supplied again on later calls.
A repeated prefix may receive cache-hit pricing, but still contributes input
tokens. Inspect a longer saved trace's `agent.turn_log` usage to see this.

### Optional live practice, within this session

You can complete the week from saved traces. If you want a fresh attempt,
follow the [API-key setup](README.md#setup), then run one task with a separate
output name so the saved baseline summary is preserved:

```sh
uv run python run_eval.py --task 001 --runs 1 --verbose \
  --out results/practice-001.json --log-dir results/practice-logs
```

This makes paid API calls. Inspect the log path printed by the runner using
`inspect_run.py`. For an optional full reproduction, use the same configuration
and separate output paths:

```sh
uv run python run_eval.py --runs 3 \
  --out results/practice-baseline.json --log-dir results/practice-logs
```

### Checkpoint

Explain why token totals alone do not determine cost, why failed attempts
belong in the cost denominator, and why changing the prompt or task suite would
change the experiment being compared.

## Session 6 — Explain failures and teach it back (90 min)

### Crucial concepts

**A failure label is a hypothesis that needs evidence.** “The test failed” is
an outcome, and “the token budget was reached” is a stopping condition. A useful
explanation follows the sequence that produced them: what the agent saw, what
it inferred, what it did, and which observation it missed or misunderstood.
Look for the earliest consequential mistake, while recognizing that a trace
records visible behavior rather than giving direct access to the model's
internal reasoning. Several causes may contribute to the same failure.

**A diagnosis becomes useful when it predicts an experiment.** If the agent
missed malformed inputs, a verification instruction might improve those cases;
if the prompt omitted an output convention, clarifying the task addresses a
different problem. State the proposed change, which failures it should affect,
and what result would weaken your explanation. Keep the saved baseline intact
so a later experiment has a clear comparison. Your writeup should distinguish
observed evidence, your interpretation, and what remains untested.

### Learn and do

List the saved attempts:

```sh
uv run python inspect_run.py results/logs/eval-20261102T052757Z.jsonl --list
```

Read these five failed traces in full, using the same command with `--id`:

- `032-template-engine#2`
- `036-regex-engine#2`
- `037-json-schema#1`
- `038-lisp-interpreter#1`
- `040-unified-diff#1`

For example:

```sh
uv run python inspect_run.py results/logs/eval-20261102T052757Z.jsonl \
  --id '032-template-engine#2'
```

Budget about 10 minutes per trace. Check the corresponding prompt and failing
assertion, then record:

| Trace | What was requested? | What happened? | Evidence | Likely cause | Next experiment |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

Possible causes include tool misuse, context loss, a poor plan, skipped
verification, environment trouble, an ambiguous task, or a check bug. Treat
the stop reason as evidence, then investigate the cause: `token_budget` tells
you why execution ended, but does not explain why the agent spent its budget.

Write your own interpretation before reading [NOTES.md, D6](NOTES.md#d6-failure-analysis).
Compare disagreements against the actual prompt and trace. In particular,
ask whether an expected output convention was ever stated to the agent.
Propose fixes in your notes; leave the baseline task files unchanged while
studying the saved experiment.

Use the remaining time for a five-minute explanation of the entire system,
without looking at the code, and a one-page writeup covering:

1. The goal and loop design.
2. The fixed configuration and what was measured.
3. Baseline results with units and denominators.
4. Two failures supported by specific observations.
5. One proposed change, the metric it should affect, and a limitation.

### Checkpoint

You can explain a successful run, a failed run, and a task-definition problem
without treating all three as evidence about model capability.

## Quick self-check

Try these before opening the answers:

1. Who executes a requested `write_file` call?
2. Can an attempt pass after a `token_budget` stop?
3. Does a 100% pass rate prove a useful evaluation suite?
4. Does a temporary working directory confine arbitrary shell commands?
5. What is the difference between the model and the harness?

<details>
<summary>Answers and calculation check</summary>

1. The Python tool executor writes the file; the model supplies the request.
2. Yes. The runner checks the resulting files regardless of how the loop ended.
3. No. The suite could be too easy or have weak checks. For M1, difficulty is
   deliberately tuned to leave failures available to study.
4. No. Changing a process's current directory does not restrict its filesystem
   permissions.
5. The model generates responses and action requests. The harness manages
   the surrounding control flow, execution, limits, and records.

Using the lab's stored off-peak rates, the hand-calculated request cost is
`(1000 × 0.003 + 2000 × 0.15 + 500 × 0.60) / 1,000,000 = $0.000603`.
Its input cache hit rate is `1000 / 3000 = 33.3%`.

</details>

## Finished for the week

- [ ] I can reconstruct the loop in pseudocode and trace each message role.
- [ ] I can explain all four stop conditions and the token-budget overshoot.
- [ ] I can describe tool validation, timeout, truncation, and shell boundaries.
- [ ] I can explain how the independent check determines passing.
- [ ] I have calculated pass rate, cost per attempt, and input cache hit rate.
- [ ] I have annotated five failures before consulting the existing notes.
- [ ] I have a one-page writeup and one testable next hypothesis.

These are your learning checkpoints. The lab's artifact acceptance criteria
remain in the [M1 plan](../module-M1.md#done-criteria). M2 builds on this by
asking how to make the evaluation larger and more trustworthy.
