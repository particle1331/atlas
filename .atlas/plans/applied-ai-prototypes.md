# Applied AI Prototypes — course and post plan

## Decisions and status

This is the authoring plan, not completed course content. It supersedes the temporary 22-post outline and the schedule-shaped 28-post draft.

| Item | Decision |
|---|---|
| Course title | Applied AI Prototypes |
| Signature | `AAP-{n}`, starting at `AAP-1`; no zero padding |
| Current allocation | 44 draft post scopes created, including seven explicit system-design studies |
| Scope | Maximize useful, forward-looking coverage; no fixed duration, post-count target or live-course schedule |
| Organization | Conceptual dependencies, not six weekends or six equally sized units |
| Outline location | Detailed authoring outlines and gap bookkeeping stay here; each draft gets one ordinary scope/code/limitations cell |
| Companion projects | Root-relative paths such as `projects/applied-ai-prototypes/aap1`, containing pinned references or an explicit missing-implementation guide; authored adaptations remain separate |
| Gap handling | Repair, qualify or replace an example as its post is authored; do not repair the entire upstream repository first |
| Publication | Planning does not authorize publication, deployment or paid API runs |

**Coverage takes precedence over compression.** The 44-post allocation is a working decomposition, not a cap. A useful prototype should not disappear because it does not fit a live session or an earlier estimate. Split an investigation when it needs more explanation or experiments. Combine variants only when a comparison teaches the mechanism better than separate treatments; do not combine merely to reduce length. Do not pad the course with repeated examples that establish nothing new.

Every audited folder has an explicit disposition below. Substantial examples previously grouped together—prompt regression, sycophancy, critique/refinement, chunking, fusion, filtering, query rewriting, reranking, repair approaches, memory variants and orchestration patterns—now have dedicated investigations. Generated tools are included, not relegated to an optional appendix. A pointer-only folder is a research task rather than a falsely advertised runnable prototype.

`AAP-n` labels are course signatures, not CMS IDs. All 44 companion directories now exist with imported reference examples where available, or guidance recording an unavailable implementation. Their existence is not a claim that the lessons' proposed implementations or experiments are complete. The approved scaffold step created exactly 44 draft records, each with a title, short description and one ordinary Markdown cell describing lesson scope, companion-code responsibilities and known limitations. Detailed authoring outlines and private gap bookkeeping remain here and in CMS notes, not additional planning cells. Before creating any later draft, check for work created by another session and reconcile it; obtain immutable IDs from the CMS rather than manufacturing them. Preserve the created IDs and source filenames when changing titles.

## Sources and evidence

| Source | Role |
|---|---|
| [Arpit Bhayani's Applied AI course page](https://arpitbhayani.me/applied-ai/) | Subject coverage, including seven design exercises; the author supplied the six-session outline in this conversation |
| [Public prototypes](https://github.com/arpitbbhayani/prototypes-ai) | Inspectable starting examples, not a fixed syllabus or a guarantee that every advertised system is implemented |
| Upstream revision `678d9d0b579a72113c94a2d2f57671fd9f7f2a56` | Revision used by the earlier folder-by-folder audit |
| Enrolled course materials | Additional source available to the author; request relevant details where public material is incomplete |

The earlier audit recorded source/documentation/output findings across all 39 top-level folders. It was static: it did not reproduce model results or run prototype test suites. This planning step carries those findings forward, not a claim to have repeated that audit. The gap register preserves the substantive findings without depending on ignored temporary audit files.

The public repository, enrolled course and current APIs may diverge. Keep upstream provenance pinned and separate from our adaptations. Use current primary documentation for version-dependent claims. Upstream links are attribution, not the reader's companion-code location.

## Audience and teaching approach

The primary reader has an undergraduate mathematics background, applied-AI experience and strong coding fundamentals. Assume programming fluency and mathematical maturity, not familiarity with every AI pattern, SDK or systems term. Introduce unfamiliar background briefly at its first use; proceed quickly, but do not omit the reasoning that makes the next step intelligible.

This is an inference-time applied-systems course, not a preliminary Python, machine-learning or deep-learning curriculum. Explain similarity, ranking, sampling uncertainty, evaluation metrics, state transitions, concurrency and cost where the investigation needs them.

Use precise, restrained prose. Develop assumptions through an inspectable example to consequences. Distinguish syntax, types, domain constraints, factual support and task success. A model that finishes, code that exits zero and a system that satisfies its specification have established different properties.

Evaluate from the opening experiments. The dedicated evaluation post later develops dataset construction, scoring validity and integration; it is not the first time earlier examples are tested. Introduce authority boundaries when tool execution appears, not only during the security studies.

### Keeping the material useful going forward

| Keep | Revise or replace while authoring |
|---|---|
| Mechanisms with durable learning value: state, dispatch, evidence, ranking, recovery, memory and measurement | Obsolete SDK mechanics that distract from the mechanism |
| Small transparent implementations and comparisons between materially different approaches | A claim that an old model's captured response predicts current model behaviour |
| Failed experiments that explain a boundary or refute an assumption | Static success explanations that disagree with actual results |
| A historical design where its limitations are explicit and instructive | Universal recommendations based on tiny hand-selected examples |
| New implementation where a useful syllabus topic has no adequate public prototype | Renaming a different mechanism to pretend the topic was covered |

The goal is broad understanding, not blindly preserving every line of old code. Replace an unsuitable implementation with a better experiment that retains its useful question. Record why an example is narrowed, replaced or omitted instead of silently losing it.

## Planned post format and system-design scope

Each entry below has a title, short description, root-relative code location, coverage bullets, starting material and assigned gaps. Bullets are the outline; the final lesson should develop the reasoning, not merely expand a checklist.

The seven system designs are substantive posts, not closing paragraphs. Each identifies requirements and assumptions, compares alternatives, and develops a bounded executable slice or simulation with tests.

| Kind of evidence | What it establishes |
|---|---|
| Requirements and design | Explicit workload, data/trust boundaries, state, failures and operating assumptions |
| Bounded implementation/simulation | Behaviour under the implemented conditions |
| Measured experiment | Results for the specified fixtures, models, configurations and workload |
| Capacity estimate or larger architecture | An estimate or hypothesis until separately measured; not a claim that the complete system or advertised scale works |

## Part I — LLM components, prompting and behavioural experiments

### AAP-1: LLM Calls as Software Components

**Short description:** Treat LLM requests as fallible software operations and distinguish response validity, task correctness and repeatability.

**Project code:** `projects/applied-ai-prototypes/aap1`

- Request/response boundaries and the division of responsibility between model and application.
- Sampling variation, refusal, truncation, malformed output, missing information and service errors.
- Repeated extraction with separate formatting, parsing and correctness checks.
- Task baselines, configuration and error accounting; what repeated output does not prove.

**Starting material:** `non-deterministic`; selected classification examples from `evals`.

**Open gaps:** G01.

### AAP-2: Comparing Prompting Strategies

**Short description:** Compare direct, step-by-step and few-shot prompts on held-out tasks while measuring accuracy, latency and token cost.

**Project code:** `projects/applied-ai-prototypes/aap2`

- Direct instructions, requested intermediate explanations and worked examples as different experimental conditions.
- Parameterized tasks and reliable final-answer checks beyond familiar puzzles.
- Repeated matched comparisons, per-case outcomes and sample uncertainty.
- Example selection/count and input/output overhead; generated explanations are not proof of internal reasoning fidelity.

**Starting material:** `cot-vs-direct`, `cot-vs-few-vs-direct`, treated as a paired comparison rather than duplicate lessons.

**Open gaps:** G01, G03.

### AAP-3: Structured Outputs and Domain Validation

**Short description:** Compare JSON instructions, response schemas and domain checks to establish what each output constraint actually guarantees.

**Project code:** `projects/applied-ai-prototypes/aap3`

- JSON requested in prose versus provider-supported response schemas.
- Parsing, types, enums, cross-field constraints and semantic correctness.
- Canonicalized object comparison versus exact-string equality.
- Malformed/refused/truncated outputs and schema-valid wrong answers as independent test cases.

**Starting material:** `non-deterministic`, structured examples in `evals`.

**Open gaps:** G01, G02.

### AAP-4: Typed Model Judgements: Jev and Clairic

**Short description:** Examine typed model judgements and the deterministic policies that consume them, using available Jev and Clairic source material.

**Project code:** `projects/applied-ai-prototypes/aap4`

- Verify the source course's “System One” framing, product interfaces and actual evidence for their claims.
- Typed classifications/scores versus downstream action policy.
- Thresholds, abstention and labelled decision cases; distinguish type safety from calibrated judgement.
- Inspect the SDK boundary or build a transparent equivalent; test machine-readable output separately from terminal presentation.

**Starting material:** `jev`; relevant primary documentation and enrolled material for Clairic.

**Open gaps:** G08, G32. Do not invent Clairic behaviour from the name or equate a typed output with verified reasoning.

### AAP-5: Prompt Design, Versioning and Regression Tests

**Short description:** Treat prompts as versioned behaviour and use labelled cases to inspect improvements, regressions and ambiguous requirements.

**Project code:** `projects/applied-ai-prototypes/aap5`

- Drafting prompts from task definitions, evidence requirements, examples and consumer contracts.
- Prompt/configuration versions, dataset versions, recorded responses and a regression harness.
- A concrete change that fixes one case and breaks another; inspect the actual prompt diff.
- Held-out/per-class cases, repeated calls, compatibility and rollback.

**Starting material:** `prompt-regression`.

**Open gaps:** G01, G04.

### AAP-6: Sycophancy and Justified Belief Updates

**Short description:** Distinguish agreement under unsupported pressure from a warranted revision after new evidence.

**Project code:** `projects/applied-ai-prototypes/aap6`

- Baseline answers, persuasive pushback and multi-turn state.
- Matched pressure conditions: confidence, authority, emotional appeal and genuine correction.
- Ambiguous questions, restrictive output formats and the limits of exact answer persistence as a metric.
- Repeated trials scoring factual accuracy and warranted updates, not stubbornness as a proxy for quality.

**Starting material:** `sycophancy`.

**Open gaps:** G05.

### AAP-7: Critique, Refinement and Evaluator Validity

**Short description:** Test whether rubric-guided revision improves concrete work rather than merely raising a model-generated score.

**Project code:** `projects/applied-ai-prototypes/aap7`

- Rubric and free-form feedback on a shared initial design.
- Iterative edits, stopping criteria and cost of additional critique rounds.
- Independent concrete defect checks or blinded assessment; ceiling effects and judge agreement.
- Cases where scores rise without better work, or useful feedback does not raise the score.

**Starting material:** `critic-refiner`.

**Open gaps:** G06.

### AAP-8: Designing a Fact-Checking System

**Short description:** Design a fact-checking workflow that separates claims, evidence, support judgements and uncertainty.

**Project code:** `projects/applied-ai-prototypes/aap8`

- Claim types, evidence sources, freshness, conflicting evidence and abstention requirements.
- Claim decomposition, evidence interfaces, provenance and supported/contradicted/insufficient-evidence decisions.
- A fixture-based implementation that can acquire richer retrieval after Part III.
- Tests for coverage and citation support; compare a bounded workflow with open-ended agent control.

**Starting material:** Source design exercise 1/7; original bounded implementation informed by AAP-1–7.

**Open gaps:** G34.

## Part II — Tools, execution and trust boundaries

### AAP-9: Tool Schema Design and Selection

**Short description:** Measure how names, descriptions and argument contracts affect tool selection and request correctness.

**Project code:** `projects/applied-ai-prototypes/aap9`

- Distinguish names/descriptions from parameter structures; vary one contribution at a time.
- Selection, argument validity, domain validity and no-tool decisions as separate outcomes.
- Ambiguous queries, overlapping tools and underspecified requests.
- Repeated comparisons with per-case records instead of an arbitrary “significant improvement” threshold.

**Starting material:** `tool-schema-calibration`.

**Open gaps:** G07.

### AAP-10: Tool Dispatch and Application Control

**Short description:** Build a dispatcher that validates model requests and executes them under explicit application rules.

**Project code:** `projects/applied-ai-prototypes/aap10`

- Parsing, validation, tool registries and operation/result correlation.
- Trusted permissions, resource scopes, timeouts and structured results.
- Multiple requested calls and application-chosen sequential/concurrent execution.
- Offline tests for unknown tools, extra fields, invalid values and protocol preservation.

**Starting material:** Dispatcher excerpts from `loop`; tool interfaces developed in AAP-9.

**Open gaps:** G07, G11. This is one request/dispatch cycle; AAP-25 develops iterative agent execution.

### AAP-11: Tool Failures, Retries and Partial Results

**Short description:** Inject tool failures and examine disclosure, partial success, recovery and duplicated side effects.

**Project code:** `projects/applied-ai-prototypes/aap11`

- Deterministic success, timeout and unavailable-service injection.
- API failure versus tool failure; error disclosure versus recovery.
- Retry budgets, backoff assumptions and idempotency through a simulated effect ledger.
- Partial results, exhausted retries and fresh output from the adapted code.

**Starting material:** `tool-call-error-injection`.

**Open gaps:** G09.

### AAP-12: Human Review and Execution Authority

**Short description:** Bind human approval to specific operations and distinguish confirmation, authorization and process isolation.

**Project code:** `projects/applied-ai-prototypes/aap12`

- Proposed action, operator-visible evidence and review decisions.
- Operation identity, arguments, environment, expiry and one-shot approval.
- Mocked denial, approval replay, changed context and failure after approval.
- Host-shell/Python permissions; a timeout or a prompt is not a sandbox.

**Starting material:** `hitl`.

**Open gaps:** G10.

### AAP-13: Prompt Injection and Untrusted Context

**Short description:** Test document-borne instructions against behavioural defences and independently enforced action boundaries.

**Project code:** `projects/applied-ai-prototypes/aap13`

- Trusted instructions versus retrieved/supplied content; intended task and attacker goal.
- No defence, literal filtering, model classification and prompt separation.
- Paraphrases, delimiter imitation and benign quoted instructions.
- Attack success and false rejection; structured verdict handling and external permissions.

**Starting material:** `prompt-injection`.

**Open gaps:** G11.

### AAP-14: Encoded Instructions and Filter Bypasses

**Short description:** Examine why text denylists fail under transformations and how input policy differs from action authorization.

**Project code:** `projects/applied-ai-prototypes/aap14`

- Literal SQL keyword blocking versus character substitution and other controlled transformations.
- Normalization, decoded/semantic checks and benign false positives.
- Generated prohibited text versus actual database execution as different outcomes.
- Use a mock action/parser boundary to compare filtering with constrained permissions.

**Starting material:** `token-smuggling`.

**Open gaps:** G11. Do not describe this substitution example as a tokenizer result without evidence.

### AAP-15: System-Instruction Disclosure and Confidentiality

**Short description:** Probe instruction disclosure while separating observed model behaviour from unsupported explanations about its cause.

**Project code:** `projects/applied-ai-prototypes/aap15`

- Dummy markers, direct extraction and code-framed extraction.
- Controlled distractor length and repeated trials, without assuming that a short prompt fills the context window.
- Exact disclosure, partial disclosure and refusal as measured outcomes.
- Why system-instruction secrecy is not an authorization boundary and real credentials do not belong in such prompts.

**Starting material:** `system-prompt-leak`.

**Open gaps:** G11.

## Part III — Retrieval, evidence and caching

### AAP-16: Chunking and Retrieval Evaluation

**Short description:** Compare chunking strategies using representative evidence labels and a stated retrieval/context budget.

**Project code:** `projects/applied-ai-prototypes/aap16`

- Brief embedding/similarity and retrieval baseline sufficient for the experiment.
- Fixed windows, adjacent-sentence grouping and parent/child expansion.
- Representative questions and evidence spans rather than publication-notice metadata alone.
- Explicit retrieval metrics, normalization/stride checks, indexing cost and context-budget comparisons.

**Starting material:** `rag-chunking-strategy`.

**Open gaps:** G12.

### AAP-17: Hybrid Search and Reciprocal-Rank Fusion

**Short description:** Derive rank fusion and test when combining lexical and embedding retrieval helps or hurts.

**Project code:** `projects/applied-ai-prototypes/aap17`

- Actual lexical and learned-embedding baselines beside a labelled toy concept-space example.
- Rank rather than raw-score combination; derive smoothing effects and missing-list contributions.
- Candidate depth, absent documents, correlated errors and complementary retrieval.
- Labelled evaluation across smoothing values; interactive curves support reasoning rather than prove a universal default.

**Starting material:** `rrf`, `rrf-viz`, paired because the visualization illuminates the same mechanism.

**Open gaps:** G13.

### AAP-18: Metadata Filtering and Access Constraints

**Short description:** Compare pre- and post-filtering while separating query interpretation from trusted access restrictions.

**Project code:** `projects/applied-ai-prototypes/aap18`

- Real retrieval under a candidate limit instead of a hand-selected naive result.
- Extracted year/quarter constraints, ambiguous queries and partial/missing filters.
- Pre-filter versus post-filter effects on recall and candidate exhaustion.
- Authorization from trusted identity/policy, independently of model-extracted preferences.

**Starting material:** `metadata-filtering`.

**Open gaps:** G14.

### AAP-19: Query Rewriting and Hypothetical Documents

**Short description:** Compare original and generated retrieval queries, including cases where expansion improves ranking or changes the intended question.

**Project code:** `projects/applied-ai-prototypes/aap19`

- Vocabulary mismatch, ambiguity and hypothesized evidence text.
- Original-query embedding, query-to-query rewriting, and generation then embedding of a hypothetical document to retrieve real documents.
- A clearly labelled handwritten diagnostic condition; synthetic text is a retrieval aid, not factual evidence.
- Repeated transformations and harmful expansions, not only a selected rank flip.
- Candidate recall, ranking, latency and generation cost before any reranker is introduced.

**Starting material:** `query-rewrite-hyde`.

**Open gaps:** G15.

### AAP-20: Bi-Encoders, Cross-Encoders and Reranking

**Short description:** Examine candidate generation and joint query–document scoring while measuring ranking quality and computational cost separately.

**Project code:** `projects/applied-ai-prototypes/aap20`

- Independent embeddings versus joint query/document scoring.
- A genuine candidate-generation→reranking boundary with fixed candidate sets.
- Ambiguity, negation and directional relevance cases with explicit judgements.
- Candidate-depth recall, final ranking and latency; scores are not calibrated probabilities without evidence.

**Starting material:** `cross-encoders`.

**Open gaps:** G16.

### AAP-21: Diagnosing RAG Failures

**Short description:** Distinguish retrieval misses, misuse of evidence, unsupported answers and misleading evaluation metrics.

**Project code:** `projects/applied-ai-prototypes/aap21`

- A minimal retrieve → budgeted evidence assembly → grounded answer baseline, with actual-retrieval and oracle-evidence controls.
- Known evidence availability and separate retrieval/generation checks.
- Move identical evidence among beginning/middle/end at fixed context length.
- Support, correctness, abstention and ranking metrics measure different properties.
- Validate judge outputs and empty-claim behaviour; correct answers are not generation failures merely because evidence is ranked late.

**Starting material:** `rag-failure-modes`.

**Open gaps:** G17.

### AAP-22: Semantic Caching and Answer Reuse

**Short description:** Test when similar questions can reuse answers without violating correctness, freshness or access constraints.

**Project code:** `projects/applied-ai-prototypes/aap22`

- Exact response caching, semantic answer reuse and provider prompt/context caching as different mechanisms.
- Context-sensitive cache keys: tenant, authorization, source version, time, task and configuration.
- Similarity proposes a candidate; it does not establish answer equivalence.
- Negation/date/unit counterexamples; false reuse, missed reuse, verification cost, freshness and latency.

**Starting material:** Source semantic-caching coverage; new bounded implementation, not renamed `prompt-caching`.

**Open gaps:** G31.

### AAP-23: Designing RAG over Ten Million Documents

**Short description:** Develop a large-corpus RAG design with explicit ingestion, indexing, access, freshness and capacity assumptions.

**Project code:** `projects/applied-ai-prototypes/aap23`

- Corpus/chunk sizes, change rate, query load, authorization and latency requirements.
- Ingestion, index build/update, partitioning, retrieval, reranking and grounded answer interfaces.
- Storage/embedding/index/update capacity estimates and identified bottlenecks.
- Bounded integration/workload simulation, failure cases and cache invalidation; separate estimates from measured scale.

**Starting material:** Source design exercise 2/7; AAP-16–22.

**Open gaps:** G14, G17, G31, G34.

## Part IV — Agent control and code-execution studies

### AAP-24: Observe–Think–Act and Whole-File Repair

**Short description:** Implement a bounded repair loop and test why a runnable replacement is weaker evidence than preserved program behaviour.

**Project code:** `projects/applied-ai-prototypes/aap24`

- Observe source/execution, propose a change and decide whether to accept it.
- Whole-file model output, fence parsing and validation failures.
- Disposable fixture, tests for intended/unrelated behaviour and rollback.
- Bounded iterations, invalid fixes and host-execution risks; no claim about internal cognition from the loop's name.

**Starting material:** `observe-think-act-loop`.

**Open gaps:** G27.

### AAP-25: ReAct, Streaming and Agent Execution State

**Short description:** Build an explicit streaming agent loop with correct tool state, scheduling and termination.

**Project code:** `projects/applied-ai-prototypes/aap25`

- Agent anatomy: model, harness, state, tools, observations and stopping policy.
- Observe–act/ReAct representations and preservation of required provider message state.
- Fragmented/interleaved tool-call argument assembly, completion and validation before dispatch, and interrupted streams tested with deterministic synthetic inputs.
- Multiple calls, result correlation and application-selected scheduling.
- No-tool completion, unknown calls, repeated errors, turn exhaustion and honest final-answer validation.

**Starting material:** `loop`, `react`, compared as iterative harness implementations rather than repeating AAP-10's single dispatch.

**Open gaps:** G18.

### AAP-26: Checkpointing, Replay and Recovery

**Short description:** Compare saved conversations with workflow recovery and examine when replay repeats an external effect.

**Project code:** `projects/applied-ai-prototypes/aap26`

- Message history, execution state and operation/result records as different recovery inputs.
- Crash-atomic writes, version checks and incomplete turns.
- Interrupted execution around effect/write boundaries.
- Idempotency, deduplication and demonstrated recovery properties under an explicit side-effect model.

**Starting material:** `checkpoint-replay`.

**Open gaps:** G19.

### AAP-27: Patch-Based Repair and Change Acceptance

**Short description:** Compare unified-diff edits with whole-file repair using validation, behavioural tests and recoverable worktree changes.

**Project code:** `projects/applied-ai-prototypes/aap27`

- Patch proposals, application context and actual changed lines.
- Malformed/stale patches, partial application and failed fallback.
- Disposable worktrees, unrelated staged/unstaged work and acceptance before staging.
- Tests and rollback; compare edit surface/reviewability with semantic correctness.

**Starting material:** `code-patcher`, compared with the AAP-24 whole-file approach.

**Open gaps:** G27.

### AAP-28: Coding-Agent Architecture: Claude Code as a Case Study

**Short description:** Use documented Claude Code behaviour to examine repository context, search, edits, permissions and delegation.

**Project code:** `projects/applied-ai-prototypes/aap28`

- Version/date-stamped primary sources; documented behaviour versus inferred implementation.
- Repository instructions, file reads, search and scoped context acquisition.
- Editing, validation, permission boundaries, subprocess tools and task delegation where documented.
- Independent bounded harness reconstruction; locate referenced search code or explicitly leave it unresolved.

**Starting material:** Source Claude Code coverage; current primary documentation; `code-patcher`; `grep_search` as a pointer only.

**Open gaps:** G27, G30, G33.

### AAP-29: Designing a Paper-to-Code Agent

**Short description:** Turn a paper's definitions into implementation checks and separate execution feedback from algorithmic verification.

**Project code:** `projects/applied-ai-prototypes/aap29`

- Paper ingestion, extraction, context limits and unresolved specification questions.
- Isolation Forest tree/path-score definitions introduced briefly, not as a general ML detour.
- Scratch code, tests, execution observations and acceptance/completion criteria.
- Compare v2/v3 authority, actual sample-size normalization, small/empty/constant cases and reference behaviour in isolated execution.

**Starting material:** Source design exercise 3/7; `agent-paper-to-code-2`, `agent-paper-to-code-3` as a deliberate version-diff study; AAP-24–28.

**Open gaps:** G27, G28, G34.

## Part V — Memory and coordination

### AAP-30: Persistent Memory and Retrieval

**Short description:** Store facts across conversations and evaluate useful recall, missed recall and stale information.

**Project code:** `projects/applied-ai-prototypes/aap30`

- Conversation state versus external persistence and scope.
- Extraction, stored representation, provenance and runtime/sample fixtures.
- Keyword matching, paraphrases and selection into later context.
- Controlled persistence/read tests and the limits of append-only memory.

**Starting material:** `memory-persistent`.

**Open gaps:** G20.

### AAP-31: Memory Writes, Corrections and Deletion

**Short description:** Separate model-proposed fact actions from deterministic mutation and durable update semantics.

**Project code:** `projects/applied-ai-prototypes/aap31`

- Fact identity, ADD/UPSERT/DELETE actions and schema/domain validation.
- Duplicates, contradictions, provenance, deletion and missing/unknown actions.
- Deterministic update tests separate from extraction/action-selection quality.
- Persistence added to the volatile example where needed; evaluate stale and incorrect updates.

**Starting material:** `evolving-memory`, extending AAP-30 rather than treating mutation as persistence.

**Open gaps:** G20.

### AAP-32: Working Memory and Context Budgets

**Short description:** Compare eviction, summary compression and retrieval under an explicit total-input budget.

**Project code:** `projects/applied-ai-prototypes/aap32`

- Instructions, messages, tool schemas/results and retained state in actual token accounting.
- Derive cumulative history-resend cost under stated payload assumptions.
- Compare eviction, summaries and retrieval on one fact/evidence set.
- Rare but important detail loss, retrieval/embedding failures, task success, latency and cost; this is not provider caching.

**Starting material:** `working-memory`; accounting in `react`.

**Open gaps:** G18, G21.

### AAP-33: Orchestrators and Specialist Contracts

**Short description:** Define typed specialist interfaces and test what they enforce beyond a model's formatted output.

**Project code:** `projects/applied-ai-prototypes/aap33`

- Single-worker baseline and reasons to separate tools, context or responsibilities.
- Planner/researcher/writer contracts, validation and task ownership.
- Nested type errors versus schema-valid false claims and incorrect domain bounds.
- Provenance and cross-step consistency beyond syntactic conformance.

**Starting material:** `orchestrator-vs-specialist`.

**Open gaps:** G22.

### AAP-34: Skills and Structured Workflows

**Short description:** Build a staged skill executor and separate validated workflow structure from evidence-backed work.

**Project code:** `projects/applied-ai-prototypes/aap34`

- Declarative steps, selected context, JSON schemas and retry handling.
- Fixed workflow versus an agent choosing its next operation.
- Replace model-only repository “analysis” with a pinned fixture and actual evidence-producing tools.
- Compare staged and monolithic work on factual validity, schema validity, actual call counts and cost.

**Starting material:** `skill-executor`.

**Open gaps:** G22.

### AAP-35: Parallel Research and Subagent Execution

**Short description:** Compare bounded parallel research with serial and single-worker baselines on quality, evidence and execution cost.

**Project code:** `projects/applied-ai-prototypes/aap35`

- Task decomposition, task-type/count validation and genuine independence.
- Fork–join execution, concurrency bounds, cancellation and partial results.
- Search-grounded versus conceptual tasks; claim/citation checks beyond requested citation text.
- Actual serial/parallel measurements, dates, evidence coverage, latency and cost.

**Starting material:** `deep-research`.

**Open gaps:** G24.

### AAP-36: Coordination, Progress and Deadlocks

**Short description:** Diagnose cyclic handoffs and stalled workflows with explicit state, progress checks and bounded execution.

**Project code:** `projects/applied-ai-prototypes/aap36`

- Distinguish long work, repeated routing, livelock and blocked wait-for deadlock.
- Reproduce circular refund/shipping prerequisites and the missing transition.
- State/visit records, progress measures, repeated-state checks and limits.
- Revised prerequisites, routing, cancellation and escalation; inject slow/failed workers.

**Starting material:** `deadlock`; coordination paths in AAP-35.

**Open gaps:** G23, G24.

### AAP-37: Designing an Incident Remediation System

**Short description:** Design an incident workflow with evidence collection, scoped actions, human review and recoverable remediation.

**Project code:** `projects/applied-ai-prototypes/aap37`

- Trusted telemetry, service ownership, incident/task model and permitted actions.
- Diagnosis/proposal specialists separated from an authorized executor.
- Review thresholds, operation identity, duplicate events, rollback/compensation and escalation.
- Bounded simulation of false diagnosis, stalled specialists and interrupted remediation; no real infrastructure changes.

**Starting material:** Source design exercise 4/7; AAP-11–12, AAP-26 and AAP-30–36.

**Open gaps:** G34.

## Part VI — Evaluation, operation and integrated systems

### AAP-38: Evaluation Datasets, Scoring and Integration

**Short description:** Build a versioned evaluation set and choose checks that measure required application behaviour.

**Project code:** `projects/applied-ai-prototypes/aap38`

- Task specification, representative sampling, stratification, provenance and held-out cases.
- Exact/domain checks, retrieval metrics, task success, rubric/semantic judges and abstention.
- Judge disagreement, invalid outputs, uncertainty and evaluation cost.
- Development, regression, release and sampled online integration; exploratory failures become reproducible cases.

**Starting material:** `evals`, `prompt-regression`, metric cases from AAP-21 and adversarial experiments from AAP-6–7/AAP-13–15.

**Open gaps:** G01, G17. Earlier posts already evaluate their experiments; this develops the common methodology.

### AAP-39: Designing an AI Code Reviewer

**Short description:** Tie code-review findings to inspected changes and evaluate them against independently checked defects and benign cases.

**Project code:** `projects/applied-ai-prototypes/aap39`

- Diff/repository scope, invariants and evidence required for a finding.
- Actual static tools/tests plus targeted model analysis, not reports from repository names.
- Structured findings, line evidence, severity, uncertainty and duplicate handling.
- Seeded-defect evaluation, false positives, missed defects, hostile source comments and isolated patch validation.

**Starting material:** Source design exercise 5/7; `skill-executor`, `code-patcher` as contrasts, not complete reviewer implementations.

**Open gaps:** G22, G27, G34.

### AAP-40: Designing Self-Updating Documentation

**Short description:** Design a documentation-update workflow with source provenance, reviewable changes and independently checked updates.

**Project code:** `projects/applied-ai-prototypes/aap40`

- Clarify “Self-Updating AI Doc + Externalized Platform” from enrolled material before inventing a platform boundary.
- Versioned truth, externalized documents/state and change detection.
- Evidence linking implementation/decision changes to affected documentation.
- Review, validation, rollback and feedback/poisoning controls in a bounded change→proposal→update demonstration.

**Starting material:** Source design exercise 6/7; original bounded implementation using earlier state/workflow/evaluation mechanisms.

**Open gaps:** G34, G35.

### AAP-41: Generated Tools and Controlled Capability Changes

**Short description:** Compare one-off generated scripts with reusable tools while testing contracts, containment and actual task benefit.

**Project code:** `projects/applied-ai-prototypes/aap41`

- What the source calls self-evolving: code generation and runtime registry changes.
- One-shot execution versus registration/reuse; provenance and versions.
- Contracts, approvals, isolated execution, safe storage/cleanup and resource/turn limits.
- External task checks, rejection/rollback and measured reuse benefit rather than assumed self-improvement.

**Starting material:** `self-evolving-agent`; included as substantive coverage, not an optional afterthought.

**Open gaps:** G29.

### AAP-42: Prompt Caching and Workload Economics

**Short description:** Measure provider prompt/context cache behaviour and derive costs for a specified workload.

**Project code:** `projects/applied-ai-prototypes/aap42`

- Explicit/implicit provider caching under verified current rules, distinct from AAP-22 answer reuse.
- Stable prefixes, changed content, TTL, observed hits and cleanup.
- Verified usage/prices and applicable creation/storage costs.
- Actual cached/uncached comparisons and break-even conditions, including workloads where caching does not help.

**Starting material:** `prompt-caching`.

**Open gaps:** G26.

### AAP-43: Observability, Cost and Operational Failure

**Short description:** Trace model, retrieval and tool work and compare observed usage with estimates and operational decisions.

**Project code:** `projects/applied-ai-prototypes/aap43`

- Request/operation correlation across models, retrievers, workers, tools and retries.
- Local simulation versus emitted spans versus confirmed backend delivery.
- Usage/pricing estimates, provider records, cumulative budgets and latency distributions.
- Selected failure cases: runaway work, retry storms, contention, orphaned tasks and recovery ownership; redaction/retention for safe debugging.

**Starting material:** `observability`; execution/accounting from earlier posts.

**Open gaps:** G25.

### AAP-44: Designing a Natural-Language Workflow Engine

**Short description:** Translate requests into validated workflows with explicit execution, review, recovery and resource limits.

**Project code:** `projects/applied-ai-prototypes/aap44`

- Constrained workflow representation, ambiguity resolution and proposal versus authorization.
- Tool registry, typed dependencies, scheduling and durable state.
- Approval, retries, cancellation, compensation and observable execution.
- End-to-end malformed-plan, denied-action, partial-failure and resource-limit tests; when a conventional workflow is enough.

**Starting material:** Source design exercise 7/7; integration of dispatch, state, coordination, evaluation and operation.

**Open gaps:** G34.

## Mapping to the supplied live-course coverage

The six source areas and their design exercises are a completeness check, **not a schedule, length limit or requirement for equally sized parts**. Prototype counts advertised on the source page are not targets for our course.

| Source coverage | Planned posts |
|---|---|
| Prompt LLMs Reliably: mental model, CoT/few-shot, structured outputs, prompt failures/design/infrastructure, Jev/Clairic | AAP-1–7; Jev/Clairic explicitly AAP-4 |
| Design: Fact Checking Agentic System | AAP-8 |
| Tool Use and RAG: schema/infrastructure/failures, hybrid search, metadata filtering, reranking, query rewriting, semantic caching | AAP-9–11 and AAP-16–22; authority/adversarial context AAP-12–15 |
| Design: RAG over 10M documents | AAP-23 |
| Single Agent Loops and Systems: anatomy, observe–think–act, ReAct, checkpoint/resume, human review, Claude Code | AAP-24–28; human review explicitly AAP-12 |
| Design: Paper to Code Agent | AAP-29 |
| Multi-Agent Systems and Memory: memory architecture/write/read, working budgets, when/why/how multiple agents, parallel/subagents, orchestrator/specialist, decomposition, deadlocks | AAP-30–36 |
| Design: Incident Auto-remediation System | AAP-37 |
| Evaluation, Safety, and Systems: why/good evals, scoring, integration, dataset construction, exploratory/adversarial testing | AAP-38 plus dedicated experiments AAP-5–7, AAP-13–15 and AAP-21; evaluation begins at AAP-1 |
| Design: AI Code Reviewer System | AAP-39 |
| Design: Self-Updating AI Doc + Externalized Platform | AAP-40 |
| Production Gotchas and Systems: self-evolving agents, prompt caching, observability, cost-efficient systems, multi-agent/use-case operating problems | AAP-41–43, integrated failure cases throughout and in AAP-44 |
| Design: Natural Language Workflow Engine | AAP-44 |

## Gap register — fix during authoring

All entries are **OPEN**. Close a gap with the adaptation/claim correction, verification and remaining limitation. A narrowed claim or explicit replacement can close a gap; not every gap requires more infrastructure.

The first 30 entries preserve the earlier audit's substantive findings under the expanded numbering. G31–G35 make source-page topics/design dependencies explicit.

| Gap | Assigned posts | Finding or dependency | Work at authoring time |
|---|---|---|---|
| G01 | AAP-1–3, 5, 38 | Tiny/familiar sets, substring answers and exact strings can misstate correctness or improvement. | Separate validity/correctness/errors; add reliable held-out and repeated matched cases with warranted uncertainty. |
| G02 | AAP-3 | JSON text instructions in `non-deterministic` are not response-schema enforcement. | Add a real schema condition and domain checks; do not equate repeated strings with determinism. |
| G03 | AAP-2 | Prompt comparison code uses eight trials rather than README's ten; familiar puzzles do not establish general gains. | Reconcile counts, generation, answer checks and costs/configuration; qualify reasoning claims. |
| G04 | AAP-5 | Prompt-regression README describes absent examples and several rules change together. | Inspect actual diffs and causes; distinguish observed regressions from general reliability. |
| G05 | AAP-6 | One-word sycophancy scoring conflates warranted revision with agreement; saved runs vary. | Match evidence/no-evidence pushback and score justified updates over repeated trials. |
| G06 | AAP-7 | Critic arms start from different drafts and share near-ceiling model scoring. | Share initial work; check concrete defects independently or use blind assessment and inspect rating/quality agreement. |
| G07 | AAP-9–10 | Tool “schema” comparison changes descriptions only, checks first selected name and uses a count-based significance verdict. | Separate selection, arguments and execution; add ambiguous/no-tool cases and defensible statistics. |
| G08 | AAP-4 | `jev` SDK setup is undocumented; tests cover UI more than policy validity. | Verify interface/dependencies or implement a transparent equivalent; test judgements and policy separately. |
| G09 | AAP-11 | Current weather tool always succeeds although README/output show a 503 (`main.py:25–32`). | Restore deterministic faults; test disclosure, partial results and effect-safe retries; capture fresh outputs. |
| G10 | AAP-12 | Human approval reuses command strings and permits host-shell execution. | Bind one-shot approval to operation/context and test denial/replay; contain executable demos genuinely. |
| G11 | AAP-10, 13–15 | Fixed attacks/delimiters/classifier strings do not establish security; SQL is generated, not executed; extraction does not prove attention dilution. | Vary benign/hostile cases, validate verdicts, enforce authority externally and narrow unsupported causal claims. |
| G12 | AAP-16 | Chunking tests only five notice/metadata questions; pooled-context success is called precision; normalization/stride assumptions unchecked. | Use representative evidence, explicit metrics/budgets and validated parameters; account for actual embedding work. |
| G13 | AAP-17 | Handcrafted concept vectors/manual ranks are not learned retrieval evidence; `k=60` claims overgeneralize. | Label derivations; test real retrieval, smoothing/depth, absent candidates and correlated errors. |
| G14 | AAP-18, 23 | Metadata retrieval is hand-selected, security corpus unused; extracted filters are not authorization or a zero-hallucination guarantee. | Implement real retrieval/filtering, trusted access and partial-filter semantics; narrow guarantees. |
| G15 | AAP-19 | HyDE rewrite is handwritten but labelled LLM-decoded (`main.py:104–108`); baseline is dense retrieval. | Add generated rewrites with a labelled handwritten diagnostic condition and harmful-expansion cases. |
| G16 | AAP-20 | Static reranker explanation conflicts with saved reverse-flight rank 3/score 0.9116; probabilities are unestablished. | Evaluate actual candidates/ranks, use result-derived explanations and report score/cost limits. |
| G17 | AAP-21, 23, 38 | Correct middle-context answer is labelled failure via ranking precision; empty `supported` list yields faithfulness 1.0. | Separate retrieval/generation metrics, control position/length, and validate judge outputs/abstention. |
| G18 | AAP-25, 32 | One ReAct run, weak answer check and static success text conflict with failed verdict; growth claim uncontrolled. | Correct acceptance/commentary, derive/test history costs and preserve actual provider protocol state. |
| G19 | AAP-26 | Direct text-history JSON overwrite is not atomic recovery of completed workflow effects. | Test atomic state writes and effect/result records at interruption boundaries under stated idempotency assumptions. |
| G20 | AAP-30–31 | Append-only facts lack reconciliation; evolving memory is volatile and actions/deletion reporting are partly checked. | Specify identity/provenance/update/delete semantics; test mutation separately from extraction/read quality and durability. |
| G21 | AAP-32 | Saved working-memory budget/strategies are stale, instructions omitted from counts and failed embeddings become zero vectors. | Reconcile new results, count relevant total input, surface errors and compare on a common evidence set. |
| G22 | AAP-33–34, 39 | Skill “clone/analysis/coverage” is model knowledge, not inspected source; typed output may be false. | Use pinned source/tool evidence or label simulation; test valid-shaped false reports and cross-step/domain consistency. |
| G23 | AAP-36 | Max-step handoff cycle is labelled detected deadlock without state/progress checks. | Distinguish liveness failures and test repeated-state/progress analysis plus prerequisite changes. |
| G24 | AAP-35–36 | Research bounds/types/date handling are incomplete; saved-time estimate is not a serial baseline; citations are not verified. | Bound work, handle dates, compare actual conditions and validate evidence, failures, latency and costs. |
| G25 | AAP-43 | Mock spans do not reach a backend; local IDs do not prove delivery; per-run estimates are not daily budgets; tests may run live. | Separate offline/live checks, verify delivery/usage/budgets/setup and redact data; do not reproduce upstream `.env` values. |
| G26 | AAP-42 | Cache code uses 5+5+2 calls and a hardcoded hit comparison; new cache creation does not prove invalidation; pricing can be stale. | Use observed metadata, current rules/prices and changed-prefix/TTL/cost/cleanup experiments. |
| G27 | AAP-24, 27–29, 39 | Whole-file/patch loops can overwrite or stage host changes without behavioural acceptance; patch artifacts are not success evidence. | Use disposable fixtures/worktrees, inspect changes, preserve unrelated work and test edits/behaviour/rollback. |
| G28 | AAP-29 | Paper agents run host Python; v3 adds shell but no stronger acceptance/isolation; tests omit algorithm fidelity and setup/defaults differ. | Isolate execution; inspect actual delta/setup; derive invariants, edge/reference tests and actual sample-size normalization. |
| G29 | AAP-41 | Generated code imports/runs with host authority, weak contracts, unsafe cleanup and no turn bound or benefit benchmark. | Scope execution/storage, validate registry, bound resources and require external tasks before capability approval. |
| G30 | AAP-28 | `grep_search` only points to absent upstream symbols. | Locate/pin code or teach search with an independently documented fixture; do not pretend the folder is runnable. Record any deferral. |
| G31 | AAP-22–23 | Semantic caching has no adequate audited implementation; prompt caching is a different mechanism. | Build semantic reuse with equivalence/freshness/access checks and wrong-reuse/verification-cost measures. |
| G32 | AAP-4 | Clairic and source “System One” framing are not established by the `jev` examples. | Consult primary/enrolled material and distinguish actual interfaces, claims and evidence; record unavailable details honestly. |
| G33 | AAP-28 | A generic loop does not establish current Claude Code architecture. | Date/version primary sources and distinguish documented behaviour, inference and our reconstruction. |
| G34 | AAP-8, 23, 29, 37, 39–40, 44 | Seven design labels are not seven demonstrated full implementations; toy runs do not establish scale/reliability. | State workload/trust/failure assumptions, implement a bounded slice/simulation and separate results from estimates/unbuilt architecture. |
| G35 | AAP-40 | “Self-Updating AI Doc + Externalized Platform” is a label, not full requirements. | Clarify enrolled source meaning and retain provenance, review, rollback and update-validation boundaries. |

## Public prototype coverage ledger

All 39 audited folders have an explicit use or a recorded pointer-resolution task. Paired variants retain their substantive differences; grouping does not mean silently skipping their code or results.

| Folder | Planned use |
|---|---|
| `agent-paper-to-code-2` | AAP-29; compare with v3 |
| `agent-paper-to-code-3` | AAP-29; capability/prompt/default/candidate differences |
| `checkpoint-replay` | AAP-26 |
| `code-patcher` | AAP-27; architecture/design reuse AAP-28–29, 39 |
| `cot-vs-direct` | AAP-2; repeated two-condition baseline |
| `cot-vs-few-vs-direct` | AAP-2; few-shot comparison and token accounting |
| `critic-refiner` | AAP-7 |
| `cross-encoders` | AAP-20 |
| `deadlock` | AAP-36 |
| `deep-research` | AAP-35; coordination cases AAP-36 |
| `evals` | AAP-3, 38; simple checks begin AAP-1 |
| `evolving-memory` | AAP-31 |
| `grep_search` | AAP-28 via G30; unresolved pointer until actual source is located |
| `hitl` | AAP-12 |
| `jev` | AAP-4 |
| `loop` | AAP-10 dispatch; AAP-25 iterative/streaming state |
| `memory-persistent` | AAP-30 |
| `metadata-filtering` | AAP-18 |
| `non-deterministic` | AAP-1; actual schema comparison AAP-3 |
| `observability` | AAP-43 |
| `observe-think-act-loop` | AAP-24; design reuse AAP-29 |
| `orchestrator-vs-specialist` | AAP-33 |
| `prompt-caching` | AAP-42, not substituted for semantic caching |
| `prompt-injection` | AAP-13 |
| `prompt-regression` | AAP-5; methodology AAP-38 |
| `query-rewrite-hyde` | AAP-19 |
| `rag-chunking-strategy` | AAP-16 |
| `rag-failure-modes` | AAP-21; design/methodology AAP-23, 38 |
| `react` | AAP-25; context/accounting AAP-32 |
| `rrf` | AAP-17 |
| `rrf-viz` | AAP-17; supporting mathematical visualization |
| `self-evolving-agent` | AAP-41; substantive included investigation |
| `skill-executor` | AAP-34; evidence contrast AAP-39 |
| `sycophancy` | AAP-6 |
| `system-prompt-leak` | AAP-15 |
| `token-smuggling` | AAP-14 |
| `tool-call-error-injection` | AAP-11 |
| `tool-schema-calibration` | AAP-9 |
| `working-memory` | AAP-32 |

## Second review and creation decision

The second independent curriculum review retained the 44-post allocation and dependency order. It identified the following corrections, incorporated before draft creation:

| Post or boundary | Correction |
|---|---|
| AAP-4 | Removed the unsupported “verified case studies” wording while Jev/Clairic evidence remains unresolved. |
| AAP-19 | Distinguished original-query embedding, query-to-query rewriting and hypothetical-document generation followed by embedding; synthetic text is a retrieval aid, not factual evidence. |
| AAP-20 | Used joint query–document scoring rather than the potentially misleading term “pairwise reranking.” |
| AAP-21 | Made the retrieve → budgeted evidence assembly → grounded answer baseline explicit, including actual-retrieval and oracle-evidence controls. |
| AAP-25 | Added fragmented/interleaved argument assembly, completion/validation before dispatch and interrupted-stream tests. |
| Companion-code boundary | At initial scaffold creation, destinations were marked planned and managed `code_path` remained unset. The later reference import creates actual companion directories, whose guides distinguish references from pending implementation. |

The author approved creation of the collection and exactly 44 draft posts. Each post has a title, short description and one ordinary Markdown cell containing topics, a specific companion-code discussion, and known limitations/evidence gaps. These cells do not claim to contain completed implementations or results. The full authoring plan and private bookkeeping remain outside notebook planning cells.

### Created draft collection

| Item | Saved state |
|---|---|
| Collection ID | `collection/applied-ai-prototypes` |
| Introduction | `content/collections/applied-ai-prototypes.md` |
| Authored metadata | `content/collections/applied-ai-prototypes.yaml` |
| Membership | 44 draft posts ordered `AAP-1` through `AAP-44`; actual immutable IDs are stored in the CMS collection record |
| Each post | Title, short description and exactly one Markdown cell with `Topics`, `Project code`, and `Known gaps and limitations` sections |
| Companion projects | Root-relative directory appears as **Companion project** in the cell; managed `code_path` identifies its actual reference/guide directory, not a claim of completed implementation |
| Verification | All 44 records/cells re-read through CMS/notebook tools; rendered titles, descriptions, sections, paths, gaps and collection order checked after a successful preview build |
| Publication blockers | Only missing thumbnails/cover added by these drafts; unrelated pre-existing draft blockers were not changed |
| Execution/publication | No companion-code/model execution, publication or deployment |

Creation and verification were performed in the isolated `plan/applied-ai-prototypes` worktree. Pre-existing tracked authored/managed content was verified unchanged. All 35 authoring gaps remain open; creating a draft scope does not close a gap.

### Pinned reference import

The course plan and draft records were merged into `master` before the reference import. The user then requested local code under the per-post companion directories.

| Item | Import scope |
|---|---|
| Reference revision | `678d9d0b579a72113c94a2d2f57671fd9f7f2a56` |
| Directory layout | `projects/applied-ai-prototypes/aapN/reference/<upstream-folder>/`, with an authored guide outside `reference/` |
| Provenance | `projects/applied-ai-prototypes/provenance.json`: actual post IDs, source folders, Git blob IDs, SHA-256 checksums, modes and explicit omissions |
| Available source | 284 file copies across 39 reference-bearing companion projects; repeated source examples are independent pinned copies |
| Missing implementations | AAP-8, AAP-22, AAP-37, AAP-40 and AAP-44 contain guides only, with no invented placeholder code |
| Partial coverage | Jev does not establish Clairic; patch/search references do not implement Claude Code; diagnostics/workflow examples do not implement the full large-scale RAG or code-review designs |
| Security omission | Tracked `observability/.env` is excluded before reading/copying its contents; other selected tracked files retain their source bytes and modes |
| Adaptations | Not implemented by copying; use a separately named `implementation/` directory during authoring |
| Execution | No prototype imports/tests, model requests, dependency installation or generated-code execution as part of import |
| Verification | All imported blobs/checksums/modes verified, 79 Python file copies syntax-parsed, 44 project links and single-cell notebooks checked, and CMS diagnostics unchanged |
| Preview and discovery | An isolated CMS preview build rendered and verified all 44 updated posts; root pytest collected 231 root tests and no imported project tests |

The project guide documents the distinction between imported reference code, captured output artifacts and missing/adapted implementations. Copying source closes none of the 35 authoring gaps.

## Authoring handoff

1. Re-read the relevant outline, source mapping and gaps. Inspect pinned source and current primary documentation before fixing the post's claim.
2. Create or reconcile exactly 44 draft posts through the CMS, with the planned title and short description, and add them to the draft collection in numeric order. Obtain actual immutable IDs and preserve their filenames thereafter. Each notebook gets exactly one ordinary, learner-facing Markdown cell for topics, planned companion-code responsibilities, and known limitations. Do not present this scope as a completed lesson or add code/output cells at this stage.
3. Keep detailed authoring outlines and private gap bookkeeping here and in CMS notes. The single draft cell states substantive scope and unresolved limitations; it is not a private task list, generated navigation or front matter. Keep managed `code_path` pointed at the actual companion directory and accurately distinguish imported references, missing implementations and later authored code in its guide and the post.
4. Read `projects/README.md` before imports/adaptations. Keep pinned reference material unchanged and separate from maintained implementations; document provenance and deliberate deviations.
5. Develop a small implementation/experiment that answers the actual question. Use deterministic offline tests for dispatch/state/control mechanics and deliberate model calls only for model-dependent evidence. Do not execute upstream/generated shell or Python on the host merely to collect output.
6. Record fixtures/datasets, models/configuration, repetitions, errors and relevant usage. Distinguish source illustrations, our adaptations, measured results and unresolved questions.
7. Close each assigned gap with evidence, a narrowed claim or an explicit replacement/deferral. Do not repair unrelated prototypes or silently drop useful coverage.
8. Validate notebook/project/CMS changes when authoring begins and inspect diffs. Preserve draft state unless publication is explicitly requested.

**Next action:** author the lessons in dependency order, replacing each draft scope with substantive exposition and experiments while keeping the recorded gaps visible. If an investigation later needs two posts, add the space; a live-course schedule and the current count are not constraints.
