# Retention and garbage collection

[Plan index](README.md) · [Architecture](architecture.md) · [Operations](migration-and-operations.md)

**Revised 2026-10-21.** This policy concerns Watchtower's post thumbnails,
collection covers, recoverable operations, releases/backups and disposable build
storage. Kanban, cards and task attachments belong to a separate tool and storage.
No general context-attachment workflow has been selected for Watchtower2.

Authoring records are Markdown files; no database stores posts or authoring
notes. Image layout/hosting remains a later choice. These rules protect managed
binary files, whether local or eventually remote. All durations below are proposals;
review them before enabling destructive cleanup. Prototype policies never sweep
active v1 stores, deleted archives, source trees or the live website.

## Ownership and deletion

The backend handles managed image deletion and GC through one supported path.
CLI, Flet and active-session cleanup share its ownership checks, claims, retries
and reporting. UI handlers do not delete image keys/files independently.

A managed image is removable only when no active post/collection, retained undo
record, retained release, supported backup or pending operation protects its
exact bytes. Reference counts can help reporting but cannot replace the complete
root check. Missing bytes are an integrity fault to report/recover, not permission
to silently erase metadata.

Draft records, internal notes and checklists are active data. An old draft or a
completed checkbox is not garbage. Only explicit supported actions retire records.
Independent task completion has no storage or publication effects in Watchtower.

Proposed content-deletion behavior, still to confirm:

- Removing a collection member removes only that membership.
- Deleting a collection retains its posts, notebooks and shared code.
- Deleting a post reviews incoming related links and collection memberships, then
  repairs those references in one coordinated change, preserving survivor order.
- Retain authored notebooks on record deletion by default. Physical source deletion
  is a separate explicit action, with its own recovery contract.
- A `code_path` reference never authorizes deleting or moving that directory.
- Keep removed identities reserved rather than assigning them to new records.

Public collection validation must define what happens if removal/drafting leaves
no published members before these cascades are implemented. Removing an image
required by a published entity needs a replacement or an explicit valid lifecycle
change. None of these actions withdraws an already deployed static page; deploy
a new release to do that.

## Managed image lifecycle

1. Validate and stage/upload an immutable image attempt under a unique identity.
2. Verify bytes before finalizing a post thumbnail or collection cover reference.
3. Finalize the reference together with the entity save under its loaded revision.
4. If finalization fails, retain the saved old image and mark the attempt for
   recovery or later collection. Do not claim the replacement was saved.
5. Once every protecting reference is absent and grace has elapsed, claim deletion
   before removing exact bytes. New owners cannot attach to a claimed version.
6. Verify deletion and record its outcome; external failure remains retryable.

Multiple owners may share bytes if the chosen implementation supports it. Removing
one owner must leave others working. A paused collector must not delete a later
replacement that happens to have the same digest. Physical immutable identities
and guarded claims prevent that race. Remote adapters must account for exact
versions and any delete markers; a key-level response alone does not prove the
referenced version was removed.

Ordinary filesystem/editor access remains appropriate for authored notebook/code
changes. Out-of-band removal of managed bytes is an explicit repair path, not the
normal image workflow. Detect affected owners/releases without blocking unrelated
scratch edits or silently discarding references.

## Proposed retention defaults

Ages use recorded UTC transitions and apply within an explicit environment.

| Data | Proposed retention | Removal condition |
| --- | --- | --- |
| Active records, scratch/to-dos and their images | Indefinite while active | Explicit supported retirement; no age-based purge. |
| Abandoned upload or verified image never finalized | 24 hours after inactivity/completion and lease expiry | No pending finalization, active owner or other protecting root. |
| Image losing its last live owner | At least 7 days of quarantine | Undo/release/backup/operation protection also absent. |
| Deleted-record undo payload | 30 days | Undo promise expired, references reconciled and remaining pins respected. Source handling must match the agreed deletion contract. |
| Retired ID reservations | Indefinite | Never reuse an identity. |
| Unexported release staging | 24 hours after abandoned lease | No possibly committed/deployed export. |
| Exported release with unresolved publication status | Until reconciled | Never infer retirement from age alone; report and bound outstanding exports. |
| Confirmed releases | Current deployment, previous 3 successes, all under 90 days old and named pins | Record retirement only after release/rollback/backup roots permit it. |
| Application backups | Initial proposal: 30 days | Retained replacement exists and the declared restore window has expired. |
| Completed source-operation staging | 7 days | Final state verified; no recovery/undo dependency. |
| Pending/conflicted operations or execution results | Until explicitly resolved | Preserve divergent authored bytes; never purge them by age. |
| Completed operation details/audit events | 90 days | No unresolved operation depends on them; avoid whole-workspace copies per save. |
| Idempotency receipts, if remote retries are used | Proposed 7-day accepted request window | Expired requests remain rejected after receipts expire. |
| Successful local build projects | Current and one successful fallback per mode | No active renderer/export lease or protected output. |
| Failed local build projects | Latest failure per mode, up to 7 days | Not active or required for unresolved recovery. |
| Build records/logs | Latest 20 completed per mode plus retained-output records | Bound log size; expire full debug logs after 7 days. |
| Download/render cache | Proposed 1 GiB LRU cap | No active lease; bytes are fetchable from a verified retained origin. |
| App-owned upload/package staging | Upload grace or build-job retention | No active operation; never sweep shared toolchain caches. |
| CI artifacts and diagnostics | Configured bounded retention | Keep deployment lifetime and promised release rebuildability separate from transient artifacts. |

A historical manifest remaining in Git does not imply indefinite rebuildability.
The release-retention policy must state which exact image/source/toolchain inputs
remain available. Agree that promise before automated release retirement.
Backups need their exact image versions protected for the entire restore window;
a normal seven-day image grace is not enough if an older backup still needs it.

## Local build storage

A build stage owns generated frontend notebook copies, generated pages/navigation,
hydrated images and rendered output. Cleanup removes these together under the
stage's lease. Canonical notebooks and shared code stay outside that scope.

Use an exclusive render/cleanup gate, validated immediate-child stage names and
no symlink traversal. Clean before allocation and after jobs finish. Preserve
current/fallback output and active render/export stages. A cleanup error is visible
and retryable without invalidating an otherwise successful render.

Lease renewal and a reconciler distinguish abandoned work from a slow renderer.
A stale status string or timer alone is insufficient authority to remove a stage.
Keep unresolved filesystem recovery data outside ordinary build retention.

## Scheduling, diagnostics and restore

Run bounded cleanup at startup/resume, after relevant operations, periodically
while the backend is active or explicitly through CLI. No always-on host is
required while the laptop is closed. Expiry makes data eligible; it does not
promise deletion at an exact time while the application is inactive.

Provide dry-run and apply using the same candidate rules. Apply rechecks roots
and claims at execution time. Report protected, eligible, deleted and failed bytes
with reasons. Unavailable/inconsistent ownership inventory stops destructive cleanup rather
than guessing from a directory or bucket listing.

Backup manifests protect exact referenced image versions independently of the
authoring record set being restored. Stop GC during restore, verify all required bytes, replace worker
generations and reconcile before resuming writes. Back up uncommitted source if
the recovery promise includes it; Git only protects committed source. See the
[backup and restore procedure](migration-and-operations.md#backup-and-restore).

Before destructive apply, demonstrate shared ownership, attach/delete races,
failed finalization, interrupted deletion, a paused collector versus replacement,
release/backup protection, missing-image reporting, oldest-supported-point restore
and repeated lifecycle/build runs settling to the declared retained set. Use
isolated resources and simulated time; never test against live v1 storage.
