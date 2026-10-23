# Development stages

[Plan index](README.md) · [Content model](content-model.md)

**Revised 2026-10-21.** Build the actual post/collection authoring flow in small
CLI-led slices, with an early Flet editor. The former Kanban-first and full-v1-parity
roadmap is superseded. Kanban belongs to a separate tool and is not an implementation
stage or prerequisite. The linked course still needs its own outline revision.

The [first slice](first-slice.md) now implements draft-post CLI/editor behavior.
Stage 1 still awaits real browser evidence and acceptance; later stages remain proposals. V1 remains the
working system. Use isolated stores, source copies/worktrees, credentials, ports
and output targets throughout. Live migration and deployment changes are separate.

## Working approach

For each slice, explain its inputs, authoritative records/files, stored changes
and important failure case. Inspect the relevant v1 workflow read-only where it
helps; do not study or reproduce every v1 entity first. Implement one coherent
action, demonstrate it, inspect its effects and record evidence/questions.

Use brief implementation notes with Context, Decision, Consequences, Evidence
and Open questions when a durable choice needs recording. Review the behavior
and explanation together; a passing test count alone does not complete a stage.
Keep agents' unfinished content questions in the entity's scratch/to-dos once
those fields are implemented. Independent task tracking can use a separate CLI.

## Stage 0 — Set boundaries and authoring format

The user selected Markdown authoring during implementation: public metadata in
YAML front matter, internal scratch and Markdown checkbox lists in the body.
No SQLite or hosted metadata database. The immutable-ID, lightweight draft and
public/internal-date rules remain settled. See the first-slice decision/evidence.

Use explicit isolated workspaces and schema markers. Define exact-byte revisions,
supported file coordination and the boundary around external IDE/Git changes.
Image limits, managed binary files and backup/release transport belong to their
actual later slices; no remote-provider spike gates the first post editor.

## Stage 1 — Draft post through CLI and one Flet editor

Deliver a project-local headless `wt2` entry point, application use cases and the
Markdown record adapter. Define command help, structured context, errors and
expected-revision behavior with the implemented slice. Keep Flet out of the
headless import/dependency boundary.

Create a draft from a working title, assigning an immutable ID and intended
notebook path. Save metadata, freeform scratch notes and an ordered checklist.
There is no plan schema, Start action or body seeding. Define the initial date
convention and separate enforced revision from public `updated_at`.

Connect one real Flet post editor immediately. Verify that CLI and UI observe
the same data, a stale save preserves input, a re-render keeps unsaved fields,
and scratch/checklist changes leave the public modification date unchanged.

Evidence: inspect saved fields and revisions after each action; verify identity
never changes; show no-op/stale-save cases and readable Git diffs confined to
the intended Markdown record. Scratch edits must leave the public date unchanged. Publish can remain unavailable until source/image
readiness is implemented in the next slice.

## Stage 2 — Notebook/source links and required thumbnail

Add existing-notebook registration and Create/Open behavior for a draft's
intended source. Empty creation must preserve existing files and never generate
a writing brief. Preserve authored body, outputs and options. Supporting
`code_path` is a reference to an existing directory, not project scaffolding.

Add validated managed image upload/replace through CLI and Flet. Finalize bytes
and metadata coherently; retain the old image after failure. Agree how source
changes are detected and how dates behave after edits made while the CMS was
closed. Supporting-code edits affecting post dates remain a separate choice.

Implement post publishing requirements and Return to draft. Evidence: two posts
share one code directory, notebook changes affect the right public date, scratch
edits do not, missing thumbnails block publication, a rejected image replacement
preserves the old reference, and a divergent source save is not overwritten.

## Stage 3 — Collections and the public listing layouts

Create/edit a collection with cover, short description, Markdown long description,
ordered post IDs and the same internal scratch/checklist. Save the form and order
under one enforced collection revision. Decide exact collection publication and
empty-eligible-list validation before implementing those transitions.

Build Posts as a thumbnail listing and Collections as a cover-card grid. Generate
a collection detail page from its metadata and member posts. Home and Resume stay
in navigation; agree their editing model separately before implementing their
new authoring controls or converting existing data.

Evidence: the same post appears in two collections without copying its notebook;
reordering changes only the selected collection; removing a member preserves the
post and code; internal edits do not change public dates; a member's content edit
does not change collection dates; public rows filter drafts and preserve order.
Demonstrate stale reorders and keyboard-accessible membership controls.

## Stage 4 — Preview and frozen public releases

Capture saved notebook/sidecar bytes, eligible public metadata, exact images and
configuration into an isolated build stage. Generate frontend notebook copies
and collection/listing pages. Render stored outputs without executing kernels,
leaving canonical source bytes unchanged. Promote only successful output.

Retain the frozen-release design from the earlier plan. Export allowlisted public
inputs with matching source/image/configuration hashes for deliberate review
and commit. Exclude internal fields and edit revisions. CI builds that snapshot
without querying mutable live authoring state. If images are local, define how
exact bytes reach CI; if remote, verify exact retained versions with scoped reads.

Evidence: a scratch/checklist-only edit leaves the public projection/digest
unchanged; subsequent CMS edits cannot mutate an existing release; required
image/source failures preserve the last successful output. Demonstrate release
binding, source immutability and a clean-checkout build in an isolated target.
Home/Resume inputs must have an explicit public snapshot boundary by this stage.

## Stage 5 — Deletion, bounded storage and recovery

Implement the agreed deletion/undo policy, incoming-reference review and managed
image ownership. Entity deletion must account for shared post memberships and
code references; default source retention is still a proposal to confirm.
There are no Kanban/card deletion or card-file workflows in this stage.

Expose backend cleanup diagnostics/dry-run before destructive apply. Protect live
images, retained releases/backups, pending operations and active render/export
leases. Run cleanup during active use/startup or explicit CLI calls. Bound build
stages, caches, operation history and abandoned upload staging.

Evidence: failed/repeated uploads settle to declared storage, shared images
survive removal of one owner, an interrupted deletion is recoverable, and a
backup restores metadata plus every required image/source version. A missing
unrelated image remains a reported fault without blocking unrelated authoring.
Use disposable resources only. See [retention](retention-and-gc.md) and
[operations](migration-and-operations.md) for the safety contract.

## Stage 6 — Evaluate and decide future work

Demonstrate the complete two-type workflow through CLI and Flet, including
creation, direct notebook writing, internal notes/to-dos, images, shared code,
ordered collections, public preview/release, conflicts and recovery.

Record usability, limitations, measured provider behavior and storage growth.
You should be able to trace which records/files change and diagnose the demonstrated
failure cases. Review whether extra authoring features are actually needed.
Separate Kanban may be used by CLI throughout without becoming a Watchtower module.

Future adoption, data mapping, course changes and live hosting changes need
separate scope. Full v1 parity and a live cutover are not completion requirements.

## Verification discipline

Implementation uses isolated worktrees and data environments. Run required code
checks for behavior changes, meaningful provider contracts when relevant, and
UI evidence for the actual supported runtime. Update command documentation when
commands exist, not when this roadmap proposes them.

For the first implementation slice, run file/CLI/editor checks and required
repository lint/type/tests. Record unrelated baseline failures separately. Review
Markdown links/examples and the diff; there is no notebook/rendering change that
requires kernel execution or a production build.
