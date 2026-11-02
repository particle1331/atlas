# \~18-Week Plan: Agents, Retrieval, Post-Training, Codebase Stewardship

Weekly specs for the main track and Track B. Each spec is self-contained enough to hand to an agent cold.

**Main track run order:** M1, M2, M3, M3b, M3c, M4, M5, M6, M7, M8, M9, M10, M11, M12 (14 modules). M3b and M3c are the prompt-optimization and search/retrieval modules; they sit right after the harness work because they reuse eval-v1 and harness v2.

## Constraints baked into every spec

- **Time:** 12 hrs/week = 8 hrs main track + 4 hrs Track B. M5-M7 usually need \~1.5 calendar weeks each, so planned work is \~15.5 weeks (about 190 hrs). Budget \~18 calendar weeks to leave \~2.5 weeks of buffer for failed cloud runs and slips.
- **Default machine: the M5 Air (16GB).** Everything is developed, debugged, and dry-run here. Anything that fits on the Air runs on the Air. Cloud is only for the items in the table below, and only after a clean local dry run: the script runs end to end on a 0.5B model for a few steps, checkpoint save and resume work, the eval script runs on the output, and time per step is measured and extrapolated.
- **Local compute:** Apple M5, 16GB unified memory (MLX-LM or PyTorch MPS). Assume \~10-11GB usable: 1.5B models in bf16 LoRA, 3B only in 4-bit with sequences \~1k tokens, batch size 1, gradient checkpointing. No 7B locally.
- **Air-specific:** The Air is fanless, so sustained runs throttle. Run plugged in with `caffeinate -i`, measure the throttled step time (not the first-minute speed) when extrapolating, checkpoint every N steps, and don't train while harness evals run on the same machine. CUDA-first tools (Unsloth, bitsandbytes, vLLM) may not run on Apple silicon, so they can't be dry-run locally. Treat the first 10 minutes on Colab (or any rented box) as a smoke test for those.
- **Compute tiers:** (1) the Air for everything that fits, (2) Colab for CUDA smoke tests and short runs at no extra cost, (3) Thunder Compute A6000 48GB at $0.35/hr for the real runs (M5 parity, M7 GRPO, M9 serving). The A6000 is Ampere, so bf16 works, and 48GB removes memory juggling. Anything beyond one GPU comes from reserve.
- **Colab rules:** sessions disconnect and storage is ephemeral, so every script is resumable and checkpoints to Drive every N steps. Record the GPU type (T4, L4, A100) in every result, since numbers are not comparable across GPUs. Plan for a 16GB T4 as the floor and treat bigger GPUs as a bonus.
- **Paid cloud (Thunder A6000, $0.35/hr, $40 hard cap = \~114 GPU hrs):** rent for real runs once the local dry run has passed. Auto-shutdown on every session.
- **API spend:** tracked separately, soft cap $5 per week in weeks that use it, except M3b, M4, and M8 ($8 each). Planned total $42 across M1-M4 and M8.
- **Every week ends with** a measured number, a one-page writeup, and artifacts committed to the repo.
- **Rules:** freeze model, prompt, and seed when comparing; debug every cloud script locally on a 0.5B model first; set auto-shutdown on every rented box; checkpoint to persistent storage.

| Module | Cloud item | Cap |
| --- | --- | --- |
| M5 | TRL/Unsloth SFT parity run, plus optional 7B QLoRA or bf16 LoRA run | $5 |
| M7 | GRPO real run (A6000 48GB, 1.5B model; optional 3 seeds) | $12 |
| M9 | vLLM serving and load test | $4 |
| any | Reserve for failed runs (optional 2-GPU FSDP/DeepSpeed lab, price varies by provider, only from reserve) | $19 |

Colab covers smoke tests and short runs; Thunder covers the real runs. At $0.35/hr, planned paid spend is roughly $7 (M5 \~4h, M7 \~12h, M9 \~3h), or \~$12 with 3 M7 seeds. The rest of the $40 is reserve.

## Main track (8 hrs/week)

### M1. Agent loop and baseline

| Field | Spec |
| --- | --- |
| **Goal** | From-scratch agent plus a frozen baseline on 20 tasks. Concepts: tool-call protocol, context growth, stop conditions, cost accounting. |
| **Compute** | None. Python 3.11, cheap capable model via API, temperature 0. API cap \~$5. |
| **Read** | Anthropic's "Building effective agents"; mini-swe-agent's \~100-line loop (note how it stops, handles errors, truncates output). |
| **Plan** | D1 (1h) read, write 5 bullets on choices to copy or reject. D2-3 (3h) build loop with tools bash (timeout, temp dir), read\_file, write\_file; stop on no tool call, 20 turns, or token budget; JSONL log of messages, tokens, cost, latency. D4 (1h) build 20 tasks, each a folder with prompt.md, starter files, check.sh (exit 0/1). D5 (1.5h) run all 20 tasks x 3 runs, everything frozen. D6 (1.5h) read 5 failed traces in full, tag causes. |
| **Repo** | agent/{loop,tools,log}.py, tasks/NNN-name/, run\_eval.py, results/baseline.json, NOTES.md |
| **Done when** | loop.py is 250 lines or fewer, no framework. Baseline reports mean pass rate over 3 runs, cost per task, median turns. Pass rate between 20% and 80% (retune difficulty otherwise). 5 failures annotated with root cause. |
| **Pitfalls** | Unbounded tool output floods context. No bash timeout. A check.sh that passes on untouched starter files (verify each fails first). Running outside a sandbox dir. Ignoring cached-token pricing. |
| **Hands off** | tasks/, run\_eval.py, baseline.json become the eval seed. |

### M2. Evals and verifiers

| Field | Spec |
| --- | --- |
| **Goal** | A trustworthy eval of 100+ tasks. Concepts: programmatic oracles vs LLM judges, judge bias (position, length, self-preference), variance, pass@k, contamination. |
| **Compute** | None. API cap \~$5. |
| **Read** | pass@k definition in the Codex paper ("Evaluating Large Language Models Trained on Code"); "Judging LLM-as-a-Judge with MT-Bench"; Inspect AI docs (use it or hand-roll). |
| **Plan** | D1 (1h) read. D2-3 (3h) grow tasks 20 to 100+ using parametrized templates, with check types: unit tests, exact match, file/state diff. Freeze a 70/30 train/test split by template family. D4 (1.5h) write one rubric judge for a fuzzy task type, hand-label 30 outputs. D5 (1.5h) run 5 seeds, compute pass@1 and pass@k with bootstrap CIs. D6 (1h) writeup. |
| **Done when** | 100+ tasks, 80%+ with deterministic checks. Every check fails on starter files and passes on a reference solution. Judge-vs-human Cohen's kappa reported (target 0.6 or higher, else revise rubric). CI width and run-to-run variance reported. Tagged eval-v1. |
| **Pitfalls** | Agent can edit the test. Judge is the same model as the agent. Small n makes CIs meaningless. Temperature above 0 hides regressions. Template variants leaking across the split. |
| **Hands off** | eval-v1 suite, runner, judge, frozen split. |

### M3. Harness iteration

| Field | Spec |
| --- | --- |
| **Goal** | Measured gains from harness changes, one variable at a time. Concepts: tool descriptions as prompts, output truncation, compaction, scratchpad/todo tool, retry and recovery. |
| **Compute** | None. API cap \~$5 (use prompt caching). |
| **Read** | Anthropic engineering posts on writing tools for agents and on context engineering. |
| **Plan** | D1 (1h) read, list 6 hypotheses. D2-5 (5h) one ablation each on eval-v1 train split, 3 seeds: rewrite tool descriptions, truncation policy, compaction at N tokens, plan/todo tool, error-retry hint, system prompt trim. D6 (2h) combine winners, check the held-out test split for regression, writeup. |
| **Done when** | Ablation table (pass rate with CI, cost, turns) for 6+ changes. At least one change rejected with a reason. Final harness beats baseline by more than the CI, or an honest "no significant gain". |
| **Pitfalls** | Changing two things at once. Overfitting to train tasks. Mistaking noise for gain. |
| **Hands off** | Harness v2. |

### M3b. Prompt optimization

| Field | Spec |
| --- | --- |
| **Goal** | Automate what M3 did by hand, and find out when it beats you. Concepts: prompt surface as a search space, reflective prompt evolution (GEPA), instruction and few-shot search (MIPRO), optimizer budget, overfitting to the train split. |
| **Compute** | None. API cap \~$8 (optimizer rollouts dominate cost). Cheap student model for rollouts, stronger reflection model, hard rollout budget set before the run, sized from M1's measured cost per task (cap divided by cost per rollout), not a guess. Run rollouts in parallel; wall-clock can far exceed the 3h of hands-on time. |
| **Read** | GEPA paper ("Reflective Prompt Evolution Can Outperform Reinforcement Learning"); MIPROv2 paper ("Optimizing Instructions and Demonstrations for Multi-Stage Language Model Programs"); DSPy optimizer docs. |
| **Plan** | D1 (1h) read, write down what each optimizer mutates and what feedback it uses. D2 (2h) expose the harness's prompt surface (system prompt plus tool descriptions) as text parameters. Split eval-v1 train into optimizer-train and optimizer-val. Metric is pass rate from the existing checks. D3-4 (3h) run two optimizers (GEPA and a MIPRO-style instruction/few-shot search) with the same rollout budget (e.g., 300 rollouts). Log every candidate prompt with its score. D5 (1.5h) eval harness v2 (hand-tuned) vs each optimized prompt on the held-out test split, 3 seeds, bootstrap CIs. Read the diffs. D6 (0.5h) writeup. |
| **Repo** | optimize/{surface,run_gepa,run_mipro}.py, results/optimizer\_candidates.jsonl, results/m3b.json |
| **Done when** | Table: hand-tuned vs each optimizer on the test split with CIs, plus rollouts and $ spent per method. Train-vs-test gap reported. Optimized prompts diffed against hand-tuned and read in full, with at least one overfit or odd artifact noted. Decision recorded: adopt the winner as harness v3 before M4, then freeze through M12. |
| **Pitfalls** | Optimizing against the test split. Picking a candidate that won on noise (small optimizer-val). Prompts that memorize task specifics. Unequal rollout budgets across methods. Reflection model equal to the student, which weakens the feedback. Judge or check bugs that the optimizer exploits. |
| **Hands off** | Optimized prompt (harness v3 candidate), optimizer configs, candidate log. |

### M3c. Search and retrieval

| Field | Spec |
| --- | --- |
| **Goal** | Know how an agent should find things. Concepts: chunking, BM25, dense embeddings, hybrid fusion (RRF), reranking, recall@k, MRR, query rewriting, one-shot RAG vs agentic search (grep and read tools). |
| **Compute** | Local M5 (MPS): small open embedding model (bge-small class) and a small cross-encoder reranker. API cap \~$3 for end-to-end runs. |
| **Read** | BEIR paper; Anthropic's "Contextual Retrieval" post; Reciprocal Rank Fusion paper (skim); Anthropic's context engineering post (revisit the retrieval sections). |
| **Plan** | D1 (1h) read. D2 (1.5h) corpus and gold set: use the B1 repo (code plus docs), pinned commit. 50 questions, each with gold file or function: write 30 by hand, draft 20 with an agent and verify each yourself, tag 10 as multi-hop. Hold out 15. D3 (2h) build BM25, dense, hybrid (RRF), and optional rerank. Two chunking schemes (fixed-size, function/class-aware). D4 (1.5h) retrieval eval: recall@1/5/10 and MRR with bootstrap CIs, broken out by question type. Ablate chunking separately from retriever. D5 (1.5h) end-to-end with harness v2/v3 on all 50 questions at matched token budget: (a) one-shot search tool with top-k context, (b) grep and read\_file only, (c) both. Keep the prompt identical across arms except the search tool's own description. Score answer accuracy with a check or small rubric judge. Compare arms with a paired bootstrap over the same questions, which tightens the CIs. D6 (0.5h) writeup with a verdict on when each approach wins. |
| **Repo** | retrieval/{chunk,bm25,dense,hybrid,rerank}.py, qa/gold.jsonl, results/retrieval.json, results/m3c\_e2e.json |
| **Done when** | Retrieval table (recall@k, MRR, CIs) for BM25, dense, hybrid, hybrid+rerank, with the chunking ablation. End-to-end table for the three arms at equal cost (accuracy, cost, turns). Every gold passage verified at the pinned commit. Wide CIs from n=50 reported honestly (paired where possible), not hidden. Written verdict that covers multi-hop questions separately. |
| **Pitfalls** | Questions that copy identifier names, so BM25 wins trivially (paraphrase some). Changing chunking and retriever in the same run. Tuning on the held-out 15. Index built at a different commit than the gold labels. Comparing arms at unequal token budgets. |
| **Hands off** | Gold set, retrieval package (reusable as an agent search tool in later Track B modules and M12), results tables. |

### M4. Failure analysis and orchestration

| Field | Spec |
| --- | --- |
| **Goal** | Know why the agent fails, and test whether multi-agent fixes the top class. Also build the trajectory dataset for M5-M8. |
| **Compute** | None. API cap \~$8 (teacher sampling). |
| **Read** | Anthropic's multi-agent research system post; Cognition's "Don't Build Multi-Agents" post. Note where they disagree. |
| **Plan** | D1-2 (3h) cluster 50+ failures (tool misuse, context loss, bad plan, skipped verification, env issue, ambiguous task). D3-4 (3h) implement planner plus workers, or parallel best-of-n with a verifier, aimed at the top class. D5 (1.5h) compare single vs multi at matched token budget. D6 (0.5h) sample a strong teacher 8x per train task, keep verified successes as the dataset. |
| **Done when** | Taxonomy with counts. Single vs multi comparison at equal cost, with CIs, and a recommendation. Dataset of verified success trajectories plus matched failures, split by task. |
| **Pitfalls** | Comparing at unequal cost. Handoffs losing context. Labeling only easy failures. |
| **Hands off** | trajectories.jsonl (successes and failures) for SFT, DPO, distillation. |

### M5. SFT and LoRA

| Field | Spec |
| --- | --- |
| **Goal** | Fine-tune a small model on verified trajectories and prove the gain. Concepts: rejection sampling, chat templates, loss masking (assistant tokens only), LoRA rank and alpha, forgetting. |
| **Compute** | Local: MLX-LM, Qwen \~1.5B Instruct, LoRA rank 16, seq 2048, batch 1. CUDA: smoke-test on Colab, then run on Thunder A6000 48GB ($5 cap). TRL or Unsloth parity run; optional 7B QLoRA or bf16 LoRA (fits in 48GB). |
| **Read** | LoRA and QLoRA papers; TRL SFTTrainer docs; MLX-LM LoRA docs. |
| **Plan** | D1 (1.5h) build dataset: verified successes only, dedupe, render chat template, verify loss mask on 3 samples. D2-3 (3h) local run on train split, lr \~1e-4, 2-3 epochs. D4 (1.5h) eval on held-out tasks via the harness plus a general benchmark subset (e.g., 200 GSM8K or MMLU items via lm-eval-harness). D5 (2h, Thunder) parity run and optional 7B. Dry-run the TRL script on a 0.5B model on the Air first; the CUDA-only pieces get a 10-minute smoke test on Colab or at the start of the rented session. Checkpoint to persistent storage. |
| **Done when** | Before/after on held-out tasks with CI. General benchmark drop reported (about 3 points or less is fine). Parity run reproduces within noise, or differences explained. |
| **Pitfalls** | Wrong chat template (silent failure). Training on prompt tokens. Test-task leakage. Adapter dtype mismatch on merge. MLX adapters do not port to CUDA, so the parity run is a retrain. Match dtype to the Air (bf16) on the parity run: the A6000 supports it, a Colab T4 does not, so don't use a T4 for parity. |
| **Hands off** | SFT adapter, dataset builder, eval script. |

### M6. Preference optimization (DPO)

| Field | Spec |
| --- | --- |
| **Goal** | Improve on SFT using pass/fail pairs. Concepts: DPO loss, beta, reference model, length bias, over-optimization, pair quality. |
| **Compute** | Local only. 1.5B LoRA (reference is the model with adapter disabled), seq 1024. |
| **Read** | DPO paper; TRL DPOTrainer docs. |
| **Plan** | D1 (1.5h) build 500+ pairs (pass vs fail on the same task, ideally sampled from your SFT model); drop pairs where chosen is far longer. D2-3 (3h) train from SFT model, beta 0.1, lr 5e-6 to 2e-5. D4 (1.5h) beta sweep {0.05, 0.1, 0.3}, short runs. D5 (2h) eval: held-out pass rate, general benchmark, output length stats. |
| **Done when** | Pass rate vs SFT with CIs. Length stats pre and post. Regression check. Sweep table. |
| **Pitfalls** | Chosen differs from rejected mainly by length. Off-policy pairs (teacher-written) give weak signal. Learning rate too high collapses outputs. |
| **Hands off** | DPO adapter; verifier as reward function. |

### M7. RL with verifiable rewards (GRPO)

| Field | Spec |
| --- | --- |
| **Goal** | Turn a verifier into a training signal. Concepts: group-relative advantage, KL penalty, reward design, reward hacking, entropy collapse. |
| **Compute** | Local dry run: 0.5B, group size 4, completions 256 tokens or less, \~20 steps. Real run on Thunder A6000 48GB ($12 cap, \~34 GPU hrs at $0.35/hr): 1.5B, TRL GRPOTrainer, 6-8 GPU hrs per run, resumable. Optional: 3 seeds (about $8 total) so the held-out comparison reflects run-to-run variance, not one lucky run. |
| **Read** | DeepSeekMath (GRPO) and DeepSeek-R1 papers; TRL GRPOTrainer docs. |
| **Plan** | D1 (1h) read. D2 (1.5h) wrap one verifier as a reward function on a single-turn task (e.g., code fix with unit tests): 0/1 reward plus small format reward. D3-4 (2.5h) local dry run; log sampled completions every N steps. D5 (2h) real run on Thunder, checkpoint every 50 steps to persistent storage, auto-shutdown. Rent only after the local dry run shows nonzero reward variance, stable KL, and a working resume. D6 (1h) eval plus reward-hacking audit. |
| **Done when** | Reward curve, KL and completion-length curves, held-out pass rate vs SFT with CIs, 3+ reward-hacking examples inspected with a fix. |
| **Pitfalls** | Initial pass rate outside \~10-60% gives no gradient. Groups with identical rewards give zero signal. Completion length drifts unnoticed. No checkpoints. Verifier executing model code outside a sandbox. |
| **Hands off** | RL'd model; environment wrapper. |

### M8. Distillation

| Field | Spec |
| --- | --- |
| **Goal** | A cost vs quality frontier. Concepts: trajectory vs response distillation, teacher selection, verifier filtering, data scaling. |
| **Compute** | Local student training (1.5B LoRA). API cap \~$8 for teacher sampling. |
| **Read** | "Distilling Step-by-Step"; TRL docs. |
| **Plan** | D1 (1h) pick a strong and a mid-price teacher. D2 (2h) sample 4x per train task from each. D3 (1h) filter by verifier into datasets A (strong), B (strong+mid), C (size-matched random subset). D4-5 (3h) train students. D6 (1h) eval and cost model. |
| **Done when** | Frontier chart: x = inference `$`/task, y = held-out pass rate, for API strong, API mid, base small, SFT small, distilled small. Data-scaling points at 50%, 100%. Training cost amortized into `$`/task. |
| **Pitfalls** | Template leakage across the split. Comparing on different cost bases. Counting only successes in cost. |
| **Hands off** | Best student model for serving. |

### M9. Inference and serving

| Field | Spec |
| --- | --- |
| **Goal** | Serve your model and measure real throughput and cost. Concepts: prefill vs decode, KV cache memory, continuous batching, PagedAttention, quantization, speculative decoding. |
| **Compute** | CUDA (GPU is the lesson): Thunder A6000 48GB, 3 hrs max (\~$1), $4 cap. Run the vLLM server and the load-test client on the same box. Local comparison via MLX-LM server. |
| **Read** | vLLM / PagedAttention paper; vLLM docs on quantization and benchmarking. |
| **Plan** | D1 (1.5h) read. D2 (1h) prep before renting: merged model on storage, setup script, load-test script. Dry-run the load-test script against the local MLX-LM server on the Air. D3 (2.5h Thunder) serve with vLLM, load test at concurrency 1, 8, 32. D4 (1.5h) AWQ 4-bit variant, same load test. D5 (1h) rerun held-out eval on quantized model. D6 (0.5h) local MLX comparison and writeup. |
| **Done when** | Tokens/sec and p50/p95 latency at 3 concurrency levels. Quantization quality drop with CI. $/1k tasks vs API baseline, including GPU hourly cost. Report the GPU type and price GPU time at the rate you actually pay ($0.35/hr for the A6000), stating the rate and date. |
| **Pitfalls** | Unrealistic prompt lengths. Idle GPU while writing scripts. Forgetting shutdown. Single-stream-only benchmarks. Comparing tokens/sec across different GPU types. |

### M10. Pretraining fundamentals

| Field | Spec |
| --- | --- |
| **Goal** | Intuition for what breaks in pretraining. Concepts: scaling laws, data mixing, LR warmup and cosine decay, loss spikes, batch size and accumulation. |
| **Compute** | Local M5 (MPS), \~10-30M param GPT, TinyStories subset, 1-2 hrs per run. $0. |
| **Read** | Karpathy's "Let's build GPT" and nanoGPT; Chinchilla paper. |
| **Plan** | D1 (1.5h) read and watch. D2 (1.5h) get a nanoGPT-style baseline running on MPS. D3-4 (3h) ablate LR (3 values) and data mix (2 sources at 0/30/70%), same token budget. D5 (1h) deliberately break training (LR too high, no warmup), diagnose. D6 (1h) writeup. |
| **Done when** | Loss curves per ablation at equal tokens. Rough scaling plot from 3 model sizes. One documented instability with cause. |
| **Pitfalls** | Comparing runs of different token budgets. Unseeded runs. Evaluating on contaminated data. MPS numerics differ from CUDA. Fanless thermal throttling skews wall-clock comparisons, so compare at equal tokens, not equal time. |

### M11. Agentic RL (optional)

| Field | Spec |
| --- | --- |
| **Goal** | RL in a multi-turn tool-use environment. Concepts: multi-turn rollouts, credit assignment, masking tool outputs in the loss, sparse long-horizon rewards. |
| **Compute** | Local toy environment, 0.5B. Colab for small runs; Thunder from reserve if needed (max \~$8). |
| **Read** | RAGEN paper; TRL or verifiers-style environment docs. |
| **Plan** | D1 (1.5h) read. D2 (2h) build a 3-5 step tool-use environment with programmatic reward. D3-4 (3h) multi-turn rollout loop with tool-output loss masking, local training. D5 (1h) eval on held-out environment instances. D6 (0.5h) writeup. |
| **Done when** | Success rate vs training steps on held-out instances. Ablation: turn-level shaping vs final-only reward. |
| **Pitfalls** | Training on tool-output tokens. Rewards too sparse. Environment leaking the answer in the prompt. Small-scale noise read as signal. |

### M12. Capstone

| Field | Spec |
| --- | --- |
| **Goal** | One reproducible end-to-end story: harness and evals, prompt optimization and retrieval, then training, then serving, with costs. |
| **Compute** | Reuse artifacts. No new spend. |
| **Plan** | D1-2 (3h) rerun the pipeline from scratch scripts. Do not rerun the M3b optimizer or the M4/M8 teacher sampling; reproduce from the logged final prompt and saved datasets. D3-4 (3h) final comparison table. D5-6 (2h) README, 2-page writeup, cleanup. |
| **Done when** | Public repo with one-command eval reproduction. Final table: API baseline, harness v2, optimized prompt (M3b), SFT, DPO, GRPO, distilled and quantized, each with pass rate and CI, $/task, latency. Plus the M3c retrieval table in the README. A limitations section with negative results. |
| **Pitfalls** | Unpinned versions and seeds. Claiming gains inside the noise. Hiding negative results. |

## Track B: codebase stewardship (4 hrs/week, Media App w/ B2 storage)

### B1. Reading unfamiliar code

| Field | Spec |
| --- | --- |
| **Goal** | Verified architecture doc for a \~50k LOC OSS Python repo, plus one small fix. |
| **Setup** | Repo with a runnable test suite and open good-first-issue labels. |
| **Plan** | 1h skim manually: entry points, run tests, hand-draw module graph. 1h agent writes ARCHITECTURE.md (modules, data flow, extension points, 20 specific claims). 1.5h verify each claim against code. 0.5h start the smallest issue. |
| **Done when** | 85%+ of claims correct, wrong ones fixed in the doc. One PR opened. |
| **Pitfalls** | Trusting summaries of code the agent never opened. A repo whose tests will not run locally. |

### B2. Agent-readable context

| Field | Spec |
| --- | --- |
| **Goal** | Measure what AGENTS.md and ADRs actually change. |
| **Read** | agents.md convention; Anthropic's Claude Code best-practices guide. |
| **Plan** | 1h write AGENTS.md (commands, structure, conventions) and 3 ADRs. 0.5h write 10 small tasks. 2h run an agent on all 10 with and without context, fresh branch each. 0.5h tally. |
| **Done when** | First-try acceptance (tests pass plus checklist) with vs without. AGENTS.md under \~150 lines. Every rule either tool-checkable or marked as judgment. |
| **Pitfalls** | Bloated context file. Rules a linter should enforce. Session contamination between runs. |

### B3. Quality gates

| Field | Spec |
| --- | --- |
| **Goal** | Gates that catch agent mistakes before review. |
| **Plan** | 1h ruff, strict type checking (mypy or pyright), pre-commit. 1h CI running tests, lint, types. 1.5h mutation testing with mutmut on one core module. 0.5h record results. |
| **Done when** | Mutation score before and after writing tests for surviving mutants. 5 injected bugs: how many escaped the gates. CI under 5 minutes. |
| **Pitfalls** | Mutation testing the whole repo (slow). Counting equivalent mutants as failures. Gate config the agent can edit. |

### B4. Reviewing agent code

| Field | Spec |
| --- | --- |
| **Goal** | A failure taxonomy and review checklist from real agent PRs. |
| **Plan** | 1h have an agent produce 10 PRs on varied issues. 2.5h review each, tag every issue. 0.5h distill a checklist. |
| **Done when** | Taxonomy with counts across 10+ PRs (duplication, over-abstraction, plausible-but-wrong, dead code, swallowed errors). Checklist of 15 items or fewer. Review time per PR. |
| **Pitfalls** | Reading the diff without running it. Rubber-stamping green CI. Skipping test quality. |

### B5. Architecture for agents

| Field | Spec |
| --- | --- |
| **Goal** | Make features local. Concepts: small interfaces, clear boundaries, low coupling. |
| **Plan** | 0.5h pick the messiest module; write minimal characterization tests; measure files touched and context tokens for 3 representative feature requests (before). 2.5h refactor. 1h re-measure. |
| **Done when** | Before/after files touched and tokens per feature. Tests green throughout. No behavior change. |
| **Pitfalls** | Refactoring without tests. Abstraction layers that add files. |

### B6. Tests as spec

| Field | Spec |
| --- | --- |
| **Goal** | Let tests, not prose, define the behavior an agent must preserve. |
| **Plan** | 1.5h characterization (golden) tests on a legacy module. 1h property-based tests with Hypothesis. 1.5h agent refactors using the tests as the only spec. |
| **Done when** | All pass after refactor. Mutation score before vs after. Any behavior change was caught by a test. |
| **Pitfalls** | Snapshots that pin incidental output (timestamps, ordering). Property tests with weak generators. |

### B7. Extensibility

| Field | Spec |
| --- | --- |
| **Goal** | Flat cost per feature. Concepts: plugin points, config vs code, rule of three. |
| **Plan** | 1h design a registry or config-driven extension point. 2.5h add 3 features in sequence via agent. 0.5h compare diffs. |
| **Done when** | LOC and files per feature do not grow across features 1-3. Features 2 and 3 need no core changes. |
| **Pitfalls** | Abstracting before the second use. Config sprawl. |

### B8. Entropy and maintenance

| Field | Spec |
| --- | --- |
| **Goal** | Agent-run maintenance that does not break things. |
| **Plan** | 0.5h baseline metrics: LOC, complexity (radon), dead code (vulture), dependency age, doc drift. 2.5h three agent sweeps (dead code, dependency bumps, docs sync), each behind gates. 1h compare. |
| **Done when** | Metrics delta. Tests green. Every agent change reviewed. Zero unrelated behavior changes. Start logging data for the B12 dashboard. |
| **Pitfalls** | Deleting code used via reflection or dynamic dispatch. Bulk dependency bumps in one PR. |

### B9. Full-stack slice (plan 2 calendar weeks)

| Field | Spec |
| --- | --- |
| **Goal** | Ship a small full-stack app where you own design and review, and the agent implements. |
| **Plan** | 1h write the OpenAPI spec, DB schema, and auth approach yourself. 2.5h agent implements backend and frontend against the spec. 0.5h deploy to a free tier. Overflow into the next slot. |
| **Done when** | Contract tests (e.g., Schemathesis) pass against the spec. One migration applied and rolled back. Deployed URL. You can explain every module without reading it. |
| **Pitfalls** | Spec drift. Agent-rolled auth (use a vetted library). Secrets in the repo. |

### B10. Observability and ops

| Field | Spec |
| --- | --- |
| **Goal** | Diagnose agent-written code from telemetry. |
| **Plan** | 1h structured logs, request IDs, OpenTelemetry traces to local Jaeger or console. 1h feature flag and tested rollback. 1.5h have an agent inject 3 bugs; diagnose from telemetry only. 0.5h write a runbook. |
| **Done when** | Time-to-diagnose per bug. Runbook. Rollback tested. |
| **Pitfalls** | Logging secrets or PII. Diagnosing by reading code instead of telemetry. Noisy logs. |

### B11. Parallel agents, one repo

| Field | Spec |
| --- | --- |
| **Goal** | Know when parallelism pays. Concepts: git worktrees, ownership boundaries, merge conflicts. |
| **Plan** | 0.5h define ownership and 3 features on distinct modules. 1.5h run 3 agents in separate worktrees. 1h merge and resolve. 1h rerun the same features sequentially. |
| **Done when** | Conflict count, wall-clock, review time, and cost for parallel vs sequential. |
| **Pitfalls** | Shared files (lockfiles, registries) as conflict magnets. Nobody owning integration tests. |

### B12. Capstone

| Field | Spec |
| --- | --- |
| **Goal** | Evidence of a healthy long-lived agent-built repo. |
| **Plan** | Land 10+ small agent-driven changes (start in B8 slots). Collect metrics each week. 1h build the dashboard. 1h writeup. |
| **Done when** | Dashboard over time: complexity, test time, mutation score, files per change. One page on what you would do differently. |
| **Pitfalls** | Cherry-picking changes. No baseline. |

## If time gets tight

1. **Protect:** M5-M7, M3c, then B2, B3, B5, B7.
2. **Cut first:** M11, M9, then the optional 7B and multi-GPU runs.
3. **Cut next:** B10, B11, then M10.
4. **Spare capacity:** Track B needs 13 slots (B9 takes two), so about 5 of the 18 weeks have a free 4h B slot. Reassign those to main-track overflow, especially M5-M7.
