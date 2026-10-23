# Prototype operations and deferred adoption

[Plan index](README.md) · [Architecture](architecture.md) · [Retention](retention-and-gc.md)

**Revised 2026-10-21.** Active scope is operating, backing up and evaluating an
isolated posts/collections prototype. Kanban is operated independently through
its own CLI. This plan does not select a Kanban provider, copy its data into
Watchtower2 or require that tool to be online for authoring.

The previous full-v1 migration/parity contract is superseded. Adoption remains
future work; this document does not authorize moving live data, redirecting root
agent instructions, replacing `wt` or changing live publishing configuration.
The future `wt2` operations described below still need implementation and help.

## Environment and source binding

Require explicit prototype environment, metadata/image stores, source workspace,
repository root and output directories. Never infer active v1 stores. Use separate
credentials and namespaces if remote storage is chosen. Keep secrets in the OS
keyring and redact them from diagnostics.

Select each authoring workspace explicitly. Git can carry records and notebooks
together, but branches/merges and divergent external editor saves still need
explicit conflict handling. Never default a new worktree to active v1 files.
The first store supports explicitly opening a copied complete prototype workspace;
full multi-machine authoring and publication still need operational evidence.

Authoring uses Markdown records and source notebooks. No SQLite or hosted
metadata database. Commit/merge authored files deliberately; metadata and scratch
saves now produce readable Git diffs. The prototype marker has no absolute
machine path and a local ignored writer lock can be recreated after a copy/clone.
Image layout, binary-file backups and release transport remain later choices.

## Backup and restore

Back up public metadata, internal scratch/checklists, managed images and the
source versions promised by the recovery policy. Excluding internal fields from
the frontend does not exclude them from backups. Scratch-only saves change edit
revisions, but public dates must remain unchanged after save or restore.

Agree backup frequency, retention, acceptable data loss and target recovery time.
The retained initial proposal is a 30-day application-backup window; no recovery
promise is established by a hosted provider or by keeping source in Git. Git
protects committed source only, not live metadata or uncommitted notebook edits.

1. Capture a coherent set of Markdown authoring records and source files under
   supported coordination. Coordinate it with image GC before the backup is usable.
2. Record schema/workspace identity and an immutable manifest of exact required
   image identities/digests and source compatibility. Protect image roots
   independently of the authoring record snapshot being restored.
3. Back up uncommitted source separately if recovering that work is part of the
   promise. A code directory shared by posts needs its own explicit source backup
   policy; duplicating it into each post backup is not necessary.
4. Verify required bytes and mark the backup complete only when snapshot and
   protection inventory are durable.
5. Expire snapshots and pins under the agreed policy. If a remote provider adds
   a recovery window, image-version retention must cover it as well.

Restore first into isolated resources with writers, workers and GC stopped.
Verify schema, immutable IDs, link/member order, notes/checklists, public dates,
images and source hashes. Build the selected site snapshot. Replace worker
generations and reconcile before resuming writes or deletion. Never remove a
missing image's metadata merely to make the drill pass.

Per-edit undo, deleted-record undo and disaster recovery are different promises.
Git records committed versions; it does not automatically recover every uncommitted edit. Agree the required
history before adding a versioned copy of every record on every scratch edit.

## Day-to-day behavior

| Situation | Expected behavior |
| --- | --- |
| Competing CLI/UI save | Reject the stale revision without changing data; retain submitted input. |
| File save outcome uncertain after interruption | Read the exact record and inspect its revision before another write; preserve staging for any later multi-file operation. |
| Image replacement fails | Keep the previous saved image; expose pending/retryable staging. |
| Referenced notebook/image is missing | Report readiness/integrity on the affected entity; preserve its record and allow unrelated authoring. |
| Source operation meets a divergent IDE save | Preserve original/proposed/current bytes and require explicit resolution. |
| Preview/render fails | Keep the last successful output and expose the build log. |
| Storage pressure | Report active/protected/collectible bytes; remove only eligible garbage, preserving sources and shared code. |
| Old worker or schema upgrade | Check compatibility/generation, back up and coordinate before further writes. |
| Kanban CLI is unavailable | Content editing, scratch/to-dos, preview and publication remain usable. |

Provide headless diagnostics for environment binding, entity context, integrity,
operation recovery, image ownership, GC dry-run/apply, backup verification and
release inspection as their mechanisms are implemented. The GUI may surface
relevant failures without growing a required storage-administration workflow.

Cleanup runs during active use/startup/resume or explicit CLI calls. No always-on
service is required while the laptop is closed. Backups have a separately agreed
schedule; active-session GC alone does not establish that recovery schedule.

## Deferred: mapping v1 content

A future migration must inventory the real workspace read-only, including
untracked managed bytes, unresolved journals and historical source dependencies.
A clean clone alone may not contain every referenced payload. Preserve exact
original records/files and unknown fields with provenance before transforming.
Malformed YAML or duplicate keys require explicit repair.

The following is a discussion mapping, not an import instruction:

| Existing material | Candidate treatment |
| --- | --- |
| Posts and course chapter notebooks | Ordinary posts; preserve identities, source bytes and public route compatibility explicitly. |
| Courses and ordered outlines | Collections, with a reviewed mapping of sections, home fields and ordering. No automatic hierarchy or prose flattening. |
| Portfolio/project write-ups | Posts with optional shared `code_path`; preserve referenced code. |
| Profile/résumé and home content | Dedicated Home/Resume inputs after their schema is agreed; preserve facts and ordering. |
| Photo gallery | Review whether notebook posts/collections represent it adequately; no invented photos/captions or automatic conversion. |
| Existing internal notes/to-dos | Preserve as authoring context where the mapping is agreed; never publish them. |
| Structured plans and seed history | Preserve provenance separately and decide what remains useful; no automatic reseeding into new notebooks. |
| Existing Kanban/cards/task files | A separate tool migration decision; no Watchtower2 board tables or mandatory sync. |

IDs already assigned never change. Prefixes in examples are not permission to
rename imported identities to match a new kind. Review legacy routes/aliases and
path reservations explicitly; do not derive replacements from current titles.

Do not sweep v1 `archive/deleted/` or historical project dependencies. A supported
cleanup policy for the isolated prototype does not authorize permanent removal
of those originals.

## Deferred: adoption and rollback

If adoption is later selected, produce a concrete mapping/preservation report,
verified backups, import checksums, route/public-content comparisons, conflict
and restore evidence, exact environment/credential requirements and a rollback
procedure. Compare the intentionally smaller contract, not full v1 feature parity.
Only one backend may accept authoritative writes to a given workspace at a time.

No live switch happens automatically after prototype completion. Before a switch,
freeze affected writes/IDE saves, reconcile recovery and revalidate the final
snapshot. After new writes, restoring old v1 YAML alone loses work; a rollback
needs a tested current-state export/mapping or a reviewed forward repair.
Separate-Kanban data may have its own lifecycle and must not be silently rolled
back with Watchtower metadata.

A future publishing switch also needs reviewed settings and workflow changes.
Until then the current site, root instructions, skills and `wt` remain independent.
The linked AI-assisted course's broader plans require a separate revision; this
documentation change does not edit course metadata or notebooks.

## Handover evidence

Be able to trace a draft save, scratch/checklist edit, image replacement, notebook
change, collection reorder, stale write, release and restore. Identify the exact
rows/files each action changes, explain public versus internal dates/revisions,
and show why referenced images and shared code survive cleanup.

Record real command/source links and measured recovery limits as implementation
proceeds. Never describe a proposed command, provider feature or restore promise
as verified behavior before the corresponding slice demonstrates it.
