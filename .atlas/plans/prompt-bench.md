# PromptBench

Status: design proposal; no implementation commitment.

Working name: PromptBench. The product builds and refines prompts and
rubrics, rather than only benchmarking them.

## Goal and starting context

Build a workbench for turning loosely defined tasks into versioned, evaluated
LLM applications. Annotation, rubric discovery, prompt authoring, model execution,
evaluation, and optimization belong to the same workflow.

The motivating use case has approximately 25 top-level questions. **Each question
is a separate project**, not one branch in a single 25-question classifier.
For example, one project asks, "Did the sales agent perform needs discovery?"
Its definition may require several binary subquestions connected by AND/OR.
Another project may need only a system prompt, with no branching.

Processes are poorly documented. SMEs may disagree about the intended meaning,
not merely about how to phrase a prompt. An initial collection of 40 positive
and 40 negative examples is useful for discovering a rubric, but does not
establish that a rubric is correct or that performance estimates are precise.
Do not assume every project already has that many labeled examples.

The product must distinguish:

- **Policy discovery:** deciding what the desired judgment means.
- **Prompt optimization:** improving execution against an agreed target.
- **Evaluation:** measuring a particular candidate against a frozen target.

Automate proposal generation, execution, comparison, and bookkeeping. Do not
silently delegate organizational policy decisions or ground-truth changes to an
LLM.

## Recommended decisions

1. Make evaluation a first-class capability, not a later reporting feature.
2. Start with two project presets: single prompt and Boolean rubric.
3. Share datasets, annotations, artifacts, runs, and evaluators across presets.
4. Store structured records and results in PostgreSQL; store large immutable
   files in an artifact store.
5. Freeze all inputs to an evaluation before dispatching model calls.
6. Keep dataset targets independent of the candidate being optimized.
7. Treat model selection as an experimental variable. A candidate is not
   universally "best" because it won on one model.
8. Begin with manual and LLM-assisted proposals. Add automated search only after
   the execution and evaluation loop is trustworthy.
9. Keep this application independent of Atlas CMS internals. This file is a plan,
   not a proposal to put operational datasets or customer transcripts in Git.

## Product model

### Project presets, not separate products

| Preset         | Authoring experience                                                                                  | Execution                                                              |
| -------------- | ----------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Single prompt  | Edit system/user message templates, variables, optional examples, and an output schema.               | Render messages and call a model; validate and normalize the output.   |
| Boolean rubric | Edit the root question, leaf questions, definitions, evidence requirements, and AND/OR relationships. | Answer leaf questions using a model; evaluate gates deterministically. |

A preset selects an editor and executor, not a different experiment database.
The task's input/output contract and evaluation method are separate from its
execution strategy. A single prompt can classify, extract structured fields, or
produce text. A Boolean rubric returns a binary judgment.

Reference policy and execution topology are also separate: an approved branching
rubric can be implemented by one prompt or by decomposed leaf calls. Compare
both against the same root targets when they claim to implement the same policy.

Do not force a simple system prompt into a dummy decision tree. Conversely, do
not hide a rubric's executable structure inside unvalidated prose. Switching
strategies creates a new candidate; it does not overwrite the previous one.

Arbitrary agent workflows, unrestricted code nodes, and general workflow
orchestration are outside the initial scope.

### Core vocabulary

- **Project:** one task, its owner, output contract, and objective.
- **Case:** a stable identity for an input, plus grouping and provenance.
- **Annotation:** an individual human judgment or model suggestion.
- **Reference policy:** the approved meaning of the task; it may begin as a
  minimal definition and acquire explicit rules later.
- **Dataset version:** immutable input revisions, selected approved targets,
  split assignments, provenance, and reference-policy identity.
- **Candidate:** an immutable executable prompt package with a parent/history.
- **Model configuration:** a provider/model reference and execution settings.
- **Evaluation suite version:** dataset/split selection, evaluator versions,
  metric configuration, and aggregation rules.
- **Run:** execution of one candidate with a frozen execution configuration
  against a frozen evaluation suite.
- **Experiment:** a comparison grouping several such runs.
- **Optimization session:** a bounded sequence of proposed candidates and their
  development evaluations.

An annotation is not automatically ground truth. A proposed rubric is not
automatically reference policy. A run's score is not an attribute of a prompt
alone.

## Main user workflow

1. Create a project and choose a preset.
2. Describe the task, output contract, error costs, and any known policy.
3. Import cases and existing labels, preserving source and grouping information.
4. Annotate examples, adjudicate disagreements, and approve an initial dataset.
5. Author a baseline manually or ask an LLM to propose one from development
   examples and SME explanations.
6. Select execution models, evaluation suite, and a cost/call budget.
7. Run the baseline and inspect predictions, evidence, failures, and metrics.
8. Review informative disagreements and propose either a candidate improvement
   or a reference-policy correction. These are different operations.
9. Approve revisions explicitly, then reevaluate against the appropriate suite.
10. Promote a candidate only after reviewing quality, cost, coverage, and
    limitations. Export its package and the evaluation manifest.

### Main screens

- **Project overview:** task definition, approved policy, dataset status,
  candidate history, and recent evaluation results.
- **Dataset and annotation:** full source plus relevant excerpts, independent
  labels, evidence selection, reason codes, disagreements, and adjudication.
- **Candidate editor:** message editor or rubric graph/tree editor; definitions
  and validation alongside the editable artifact.
- **Review queue:** model/SME disagreements, policy boundary cases, and a random
  sample to avoid reviewing only model-selected cases.
- **Experiment comparison:** same-case comparisons by candidate and model,
  confusion matrices, error categories, cost, latency, and failed cases.
- **Run inspector:** rendered request, model response, parsed answer, source
  evidence, node path, evaluator output, and invocation attempts.

Independent SME annotation should hide other answers initially. Model answers
should also be hideable to limit anchoring. An SME should be able to label a root
without filling every leaf, or annotate selected leaves without asserting a root.

## Boolean rubric behavior

Represent an executable rubric initially as a validated AND/OR expression tree
with an explicit root. A directed acyclic graph with shared nodes may later avoid
duplicate questions within a project. Each node has a stable identity and
revision history.

- **Leaf:** a binary question with operational Yes/No definitions, instructions,
  and an evidence contract.
- **Gate:** AND or OR over explicit child references.
- **Root:** the project judgment produced by a leaf or gate.

Illustrative proposal, not an endorsed definition of needs discovery:

```text
Needs discovery performed?
  AND
  ├── Customer need established?
  │     OR
  │     ├── Agent elicited the need
  │     └── Customer volunteered it and agent acknowledged it
  └── Agent asked a relevant follow-up
```

Validate missing nodes, cycles, empty gates, duplicate/conflicting identities,
unreachable nodes, and output-schema compatibility before execution. Use a
declarative representation, not arbitrary expressions passed to `eval`.

### Binary decisions without concealing failures

Successful leaf predictions and root outputs are strictly Yes/No. No N/A class
is required. However, execution status is a separate field:

- A timeout, invalid output, refusal, or exhausted budget is not a No.
- Missing evidence needs an explicitly approved policy; absence of a statement
  must not silently imply a negative factual answer.
- An unresolved annotation is not a negative ground-truth label.
- A skipped node is not a negative prediction.

If a valid Boolean answer cannot be computed, record an unsuccessful or
review-required execution, not a fabricated binary result. If the business
requires a binary fallback for every input, version that fallback explicitly and
report its frequency separately.

Evaluate gates in ordinary code. The model interprets document language, not
Boolean semantics. Initially evaluate every required leaf for auditability.
Optional short-circuit execution can later skip unnecessary nodes; persist skips
explicitly. A gate may resolve despite an unavailable child only when its known
children logically determine the result.

Root labels do not generally imply leaf labels: a No at an AND gate does not say
which child failed; a Yes at an OR gate does not identify the successful child.
Never populate leaf ground truth through those invalid inferences.

Evidence should reference the exact source revision and location: page, message,
timestamp, or text offsets. Store concise justifications and citations, not
private chain-of-thought. Source extraction/chunking is versioned because changing
what the model sees can change the answer.

Cross-project question reuse is a later feature. Similar wording does not prove
identical meaning; any reused definition must be pinned to an explicit version.

## Annotation, policy, and dataset versioning

Keep three layers separate:

1. **Raw annotations:** append-only reviewer judgments, evidence, reasons, and
   model suggestions with their provenance.
2. **Adjudicated targets:** approved resolutions referencing the annotations and
   reference-policy version used.
3. **Dataset snapshots:** immutable selections of input revisions and targets.

Corrections create new revisions. Do not mutate labels in a historical dataset.
Candidate prompts must never supply the labels used to score themselves.
LLM-generated labels remain suggestions until approved under a documented process.

A dataset manifest records case IDs, source/artifact hashes, target revisions,
annotation scope (root or named node), policy version, split/group assignments,
provenance, and exclusions. Node annotations also identify the rubric revision
whose definitions they describe; changed definitions may invalidate those labels.

Keep input selections and approved target releases independently identifiable,
even if one dataset manifest bundles both. A label correction can then create a
new target release and rescore identical stored predictions without rerunning
inference. Compatibility checks require the same case/input revisions.

Support sparse labels: most examples may have root labels but no leaf labels.
Report node-level accuracy only where compatible ground truth exists. New
subquestions do not magically inherit labels from previous rubric versions.

If SMEs change the intended category, create a new reference-policy/dataset
version. That is a target change, not evidence that a prompt improved. Scores
against different targets must not be ranked as directly comparable.

## Native evaluations

### Freeze a run manifest

Every run pins:

- Candidate artifact hash and the materialized executable package.
- Dataset and evaluation-suite versions, including exact case selection.
- Provider, requested model identifier, and resolved model/version metadata
  where the provider exposes it.
- Sampling/reasoning settings, token limits, seed where supported, response
  schema, tool configuration, and adapter version.
- Preprocessing, rendering, graph-execution, parsing, and evaluator versions.
- Per-node model routing if supported; initially one model configuration per run.
- Application/code version, execution mode, repeat count, and budget policy.

Aliases can change and deterministic settings do not guarantee identical future
outputs. Preserve actual requests and responses so historical runs remain
inspectable even when exact reproduction is impossible.

Validate provider capabilities before running. Unsupported settings must fail
validation or require an explicit revised configuration, not be silently dropped.

Distinguish the candidate's execution model, an optional proposal/optimizer
model, and an optional judge model. They have different roles and separate
configuration, provenance, and costs.

### Metrics and comparisons

For binary classification, start with counts, confusion matrix, precision,
recall, F1, and accuracy. Show false positives and false negatives explicitly.
Choose the promotion objective according to actual error costs, not just F1.

Also report:

- Total selected cases, completed cases, valid answers, failures, and fallbacks.
- Answer coverage and quality on valid answers.
- For binary tasks, correct predictions divided by all selected labeled cases as
  an additional end-to-end measure; do not inflate results by dropping failures.
- Per-node metrics where labels exist, gate traces, and evidence-validation
  results separate from classification correctness.
- Token usage, provider-reported cost where available, estimated cost otherwise,
  latency, and retries. Keep estimates distinguishable from billed totals.
- Repeated-run variation when measuring nondeterminism.

For structured extraction, begin with schema validity and task-appropriate exact
or field-level matches. Text-generation projects require an explicitly selected
evaluation contract; there is no universal automatic correctness score.

Prefer deterministic graders when targets permit. An LLM judge is optional,
versioned, and calibrated against human judgments; its output is not ground
truth merely because it is automated.

Compare candidates on the same dataset, case subset, evaluator, and execution
conditions. A matrix can vary candidates and models, but the UI must expose
those dimensions rather than presenting one context-free leaderboard. Show
paired disagreements and sample counts. Small differences on 80 cases may be
noise; uncertainty calculations should respect related-case grouping.

Distinguish a prompt comparison on a fixed model from a system comparison between
independently optimized model/prompt combinations. Neither establishes universal
prompt superiority.

Changing a grader can rescore stored predictions without new model calls.
Rescoring creates new score records referencing the original predictions and the
new evaluation suite; it must not overwrite old results.

### Prevent evaluation leakage

- Separate development cases from protected final-test cases.
- Examples already inspected to discover the rubric are development-exposed.
  Splitting those examples afterward does not create a genuinely blind test.
- Keep related documents, calls from the same source, and duplicate/near-duplicate
  variants in the same partition.
- Track cross-project exposure when cases, shared examples, or optimizer context
  overlap; a holdout in one project may already have influenced another.
- Only development cases, labels, errors, and retrieved few-shot examples may
  enter candidate generation or optimization.
- Holdout targets and feedback must not be available to the optimizer.
- Use stratified/group-aware development splits where feasible. Repeatedly
  optimizing against validation cases makes them development data too.
- With limited data, use restrained comparisons and report uncertainty rather
  than searching thousands of candidates and declaring the best score reliable.
- Record access to protected cases. Once used to make development decisions,
  they are no longer an untouched final test.
- A balanced sample does not establish deployment prevalence; precision and
  operational cost may differ in real traffic.

## Prompt optimization

Support three progressively automated modes:

1. **Manual:** edit a candidate, run it, compare.
2. **Assisted:** an LLM proposes changes based on development errors; a person
   approves the candidate and any execution.
3. **Bounded search:** generate and evaluate candidates within explicit call,
   cost, time, and iteration limits.

An optimization session pins its starting candidate, development dataset,
proposal model, target execution model(s), objective, constraints, search
configuration, and budget. Persist the full candidate lineage and evaluations,
not just the winner.

Initially optimize wording, examples, and output instructions. Rubric topology
changes require review because they may alter policy rather than improve
implementation. Promotion must distinguish "better implements the same target"
from "proposes a different target."

Do not automatically optimize labels, inspect protected test feedback, promote
an unreviewed policy change, or claim cross-model generalization without testing.

## Artifacts and persistence

### Storage boundaries

Use PostgreSQL for identities, relationships, version manifests, annotations,
run state, predictions, scores, review decisions, and searchable metadata.

Use an artifact-store interface for source files, extracted text snapshots,
large requests/responses, exported reports, and prompt packages. Begin with a
local filesystem backend; add object storage without changing artifact identity.
Small structured records may stay in PostgreSQL.

Artifacts have stable IDs, content digests, media types, sizes, ownership,
provenance, and retention metadata. A local path or expiring signed URL is not a
durable artifact identity. Keep artifacts private by default.

### Suggested logical records

| Record                                                        | Responsibility                                                                                  |
| ------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `projects`, `policy_versions`                             | Task contracts, ownership, preset, approved meaning, and policy history.                        |
| `cases`, `case_revisions`                                 | Stable input identities, immutable source revisions, grouping, and provenance.                  |
| `annotations`, `adjudications`                            | Independent judgments, suggestions, evidence, approved resolutions, and reviewer identity.      |
| `dataset_versions`, `dataset_items`                       | Frozen membership, targets, split assignments, hashes, and label-policy references.             |
| `candidate_versions`                                        | Prompt/rubric package, parent lineage, execution strategy, approval state, and artifact digest. |
| `model_configs`, `evaluator_versions`, `suite_versions` | Frozen execution settings and scoring/selection contracts.                                      |
| `experiments`, `runs`, `run_cases`                      | Comparison groups, manifests, lifecycle, case-level status, and normalized predictions.         |
| `invocations`, `invocation_attempts`, `node_results`    | Provider requests/responses, retries, usage, timing, leaf predictions, gate results, and skips. |
| `score_sets`, `case_scores`                               | Versioned aggregate and per-case scoring, including rescoring lineage.                          |
| `optimization_sessions`, `proposals`                      | Search settings, budgets, proposed edits, approvals, lineage, and stopping reason.              |
| `artifacts`, `audit_events`                               | Durable file references, integrity metadata, access/review history, and change provenance.      |

These are domain responsibilities, not a requirement to create every table in
the first migration. Use relational constraints plus schema-validated JSON for
versioned graph/config payloads; avoid an opaque unvalidated JSON database.

### Prompt package

An exportable candidate package contains its strategy, message templates or
rubric graph, variable contract, output schemas, example references, evidence
requirements, parser/renderer versions, and preprocessing dependencies. Few-shot
examples included in an export must be materialized or durably referenced with
access and integrity guarantees.

Store source authoring artifacts and the resolved executable snapshot. Include
a manifest and digest so execution does not depend on a mutable editor state.
Keep provider credentials out of packages and run manifests.

## Execution architecture

```text
Web UI / SDK
     |
     v
Application API ----------> PostgreSQL
     |                      projects, versions, reviews, runs, scores
     |
     +--------------------> Artifact store
     |
     v
Persisted run work -------> Worker
                              |
                              +--> renderer / rubric executor
                              +--> model-provider adapter
                              +--> parser / schema validator
                              +--> deterministic or configured evaluator
                              |
                              v
                         persisted case/node results
```

Provisional stack: Python, FastAPI, Pydantic, and PostgreSQL. Choose the web UI
framework at implementation time. Start with one provider adapter and a
deterministic fake provider for tests.

Persist a run and its work before returning acceptance. Do not rely on a
request-scoped background coroutine for a long evaluation. Runs need resume,
case-level progress, cancellation, retry history, and cost accounting.

The [Durable Task Platform](durable-distributed-task-platform.md) is a possible
execution substrate, not a prerequisite or a second implementation to build here.
PromptBench owns candidates, datasets, predictions, scores, and policy; a task
platform would own dispatch, leases, and execution attempts. Link IDs across the
boundary without treating the task result backend as the experiment database.

At first, a PostgreSQL-backed work loop with one worker can suffice. Use explicit
claims and immutable run manifests. Expect at-least-once work delivery: retries
must not overwrite terminal case results, and a provider call may have incurred
cost before a worker failure. Record ambiguous attempts rather than promising
exactly-once billing.

Separate intentional experimental repetitions from infrastructure retries.
Declare which attempt supplies the scored prediction before execution; never
choose the most favorable retry after comparing it with ground truth.

Rate limits, concurrency, and budgets apply to all nested leaf calls, judges,
proposal calls, and retries. Check budgets before dispatch; exact hard monetary
caps may be impossible with concurrent or ambiguously completed provider calls.
Record budget exhaustion separately from a classification outcome.

Optional response caching keys include the complete effective request, model
settings, input/artifact hashes, adapter behavior, and execution versions.
Scoring caches additionally depend on targets and evaluator versions. Disable
response reuse for stochastic-repeat experiments and label reused calls clearly.

## Security and data handling

- Treat documents as untrusted data, not model instructions. Delimit content and
  give classifiers no privileged tools by default.
- Sales transcripts may contain sensitive customer information. Provider use,
  retention, region, and access requirements must be approved before upload.
- Keep secrets in a credential store; redact them from logs and exports.
- Apply project access controls to source documents, annotations, requests,
  responses, artifacts, and exports, not just the project listing.
- Version redaction and preprocessing; they can change task evidence.
- Immutable scientific history does not override retention/deletion obligations.
  Record deletion/tombstone events and make affected historical runs explicitly
  non-reproducible instead of retaining prohibited data indefinitely.
- A local single-owner MVP need not implement enterprise tenancy, but must not
  be represented as ready for shared sensitive production use.

## Staged implementation and acceptance criteria

### Stage 1: A trustworthy single-prompt evaluation loop

- Create one project; import cases and approved root labels.
- Create immutable dataset, prompt, model-config, and evaluator versions.
- Execute through a fake provider, then one real provider.
- Persist case predictions, raw responses, failures, metrics, and usage.
- Compare two prompt candidates and export their manifests.

Acceptance: changing an editor draft or source label cannot alter a past run;
failures remain visible in metrics; rescoring needs no new provider calls;
a completed case survives worker restart.

### Stage 2: Annotation and Boolean rubrics

- Independent annotation, evidence capture, disagreement review, and adjudication.
- Leaf/gate editor, validation, deterministic execution, and node inspection.
- Sparse root/leaf labels and explicit reference-policy versioning.

Acceptance: AND/OR gates pass truth-table tests; invalid graphs cannot run; root
labels never fabricate leaf labels; a timeout is never silently scored as No.

### Stage 3: Assisted rubric discovery and model comparisons

- Generate proposed definitions, boundary questions, and candidates from
  development examples.
- Review targeted disagreements plus random cases.
- Compare approved candidates across model configurations.
- Display the impact of proposed rubric changes before approval.

Acceptance: proposals cannot change approved policy or targets automatically;
changing policy creates a new evaluation target; comparisons disclose changed
datasets, evaluators, and model settings.

### Stage 4: Bounded prompt optimization

- Persist search sessions, candidate lineage, budgets, and stopping reasons.
- Support approval gates and protected final-test evaluation.
- Promote/export a selected candidate with its evidence and limitations.

Acceptance: the optimizer cannot access protected targets; all billed invocation
types count toward usage; rejected candidates and failed search steps remain
inspectable; a winning prompt retains its exact evaluation context.

## Deliberately deferred

- General-purpose agents and arbitrary workflow/code execution.
- Fine-tuning, large-scale automatic labeling, and unreviewed self-improvement.
- Enterprise multi-tenancy and complex access-policy administration.
- Automatic cross-project rubric merging.
- Broad provider coverage, cloud deployment, and advanced distributed scheduling.
- Automatic production deployment of a candidate.

## Decisions to confirm before implementation

1. First pilot: document classification or call-transcript review; one project.
2. Initial input formats and evidence locations to support.
3. Who approves policy and adjudicates SME disagreements.
4. Whether the first real tasks are all binary or require extraction/text outputs.
5. Initial provider/model and data-handling constraints.
6. Promotion objective: false-negative cost, false-positive cost, and budget.
7. Whether the Durable Task Platform is available or a minimal worker is needed.
8. Local-only pilot versus shared team deployment.

The first deliverable should be an end-to-end evaluation on one real project,
not a universal optimizer or a polished graph editor without trustworthy runs.
