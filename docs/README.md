# Watchtower2 plan

[Project home](../README.md) · [Project instructions](../AGENTS.md)

**Atlas implementation, 2026-10-28:** use the [CMS CLI guide](cms-cli.md)
for the current `at cms` commands, YAML sources and generated frontend workflow.
Editable notebooks and YAML live under `content/`; CLI-managed metadata lives
under `backend/`, superseding the Markdown storage
decision below. The remaining plan documents describe the earlier Watchtower2
prototype and proposals; they are not a report of Atlas's current implementation.

**Revised 2026-10-21.** Build a smaller CMS around notebook posts and ordered
collections. The site navigation is Home, Resume, Posts and Collections.
Posts use a thumbnail listing; collections use a cover-card grid similar to
v1 courses. Both content types retain optional internal scratch notes and to-dos.
Kanban is a separate CLI tool, outside Watchtower2.

The [content model](content-model.md) records the agreed fields and rules and
labels open proposals. It supersedes the former full-v1-parity target and the
Kanban-first roadmap. The [first implementation slice](first-slice.md) now has
a Markdown-backed `wt2` draft-post CLI and optional declarative Flet editor.
Notebook/image/publishing/collection workflows remain future work.

## Contents

| Document | Purpose |
| --- | --- |
| [Atlas CMS CLI](cms-cli.md) | Current commands, source layout, generated notebooks, collections and résumé editing. |
| [First implementation slice](first-slice.md) | Working CLI/editor, Markdown format, evidence and limitations. |
| [Content model](content-model.md) | Post and collection schemas, immutable IDs, public dates, authoring fields and separate Kanban. Start here. |
| [CLI and Flet](cli-v2-and-flet.md) | Simple editors and shared application use cases for people and agents. |
| [Development stages](development-plan.md) | Small post/collection slices with early Flet integration. |
| [Architecture](architecture.md) | Source ownership, public projections, persistence boundaries, conflicts and image handling. |
| [Website deployment](website-deployment.md) | Saved authoring state, frozen releases and generated frontend notebooks. |
| [Retention and GC](retention-and-gc.md) | Managed images, recovery and bounded generated storage. |
| [Operations and deferred adoption](migration-and-operations.md) | Backup/restore, diagnostics and the boundary around future migration. |
| [V1 walkthrough](current-system.md) | Historical behavior inventory and source paths; not a v2 feature checklist. |

## Settled product decisions

- Authoring records persist as Markdown; no SQLite or hosted metadata database.
- Two reusable types: notebook posts and ordered collections of post IDs.
- IDs are assigned once and never change, for both types.
- Posts have a title, short description, optional tags, required publication
  thumbnail, source notebook path, optional shared code-directory path and ordered
  related-post IDs.
- Collections have a title, cover, short description, Markdown long description
  and ordered post IDs. A post can appear in multiple collections.
- Both have creation and public modification dates, optional freeform scratch
  notes and an ordered checkbox list. Internal edits do not change public dates.
- Drafts can start with a working title. Use Draft/Published without a separate
  Planned state, visibility control, Start action or automatic prose seeding.
- Notes and to-dos stay available throughout authoring. They are not required
  planning inputs or publication gates, and never enter the frontend.
- Kanban runs separately through its own CLI and storage. Tasks may refer to
  content IDs or paths; there is no required integration or synchronization.

Home and Resume remain dedicated pages. Their editing models need further
conversation. Dedicated course/chapter/section, portfolio/project and photo-gallery
entities are no longer part of the reusable content model. A post may reference
shared project code without introducing a Project record.

## Architecture carried forward

The local declarative Flet CMS and independent `wt2` CLI call the same Python
application services. Keep UI and provider SDKs outside domain code. Notebook
bodies, outputs, inline attachments and authored sidecars remain source files;
builds render generated frontend copies without changing or executing sources.

Metadata and internal-authoring saves intentionally produce readable Git diffs
in a tracked workspace. Keep those records, notebook sources and deliberate
public release records in Git; ignore runtime locks and generated output. The public
site builds from an allowlisted snapshot that excludes internal notes, to-dos,
edit revisions and any separate task system. Save, commit and deploy are distinct.

Backend-managed deletion/cleanup, last-successful output promotion, explicit
conflict handling and recoverable external operations remain design goals.
They should be implemented as the authoring slices require them, not as a
large infrastructure rewrite before a post can be edited.

## Authoring storage decision

During implementation the user selected plain Markdown authoring, replacing the
Turso metadata direction and rejecting SQLite. Records have YAML front matter,
Scratch and checkbox To-dos sections. Exact-file hash revisions and a workspace
advisory lock coordinate supported writes. The CLI and Flet editor share the
same services/store. This is implemented for draft posts.

No database service or object store is required for the first authoring slice.
Managed images, backup/restore and release transport still need their own design;
the presence of image paths does not put binary image bytes into Markdown.

## Open product and delivery choices

| Choice | Next decision/evidence |
| --- | --- |
| Collection publishing | Confirm cover/description requirements, minimum published members and the empty-public-list case. |
| Home and Resume | Agree editable fields and source authority while preserving existing résumé facts. |
| Dates and source changes | Choose how notebook edits are detected and timestamped when the CMS is closed; decide whether shared code edits affect post dates. |
| Editor delivery | Prototype browser Flet first as a recommendation; native packaging and crash recovery for unsaved forms remain open. |
| Files and deletion | Agree image limits, optional context attachments, reference repair, source retention and undo durations. |
| Release/restore promises | Agree retained rebuild window, backup frequency and acceptable data loss; test them. |

## Isolation and implementation

Existing repository-root `.venv/bin/wt` commands inspect the working v1 system.
The future prototype executable is project-local `wt2`; it is not an alias for
`wt`. Root agent instructions, current skills, source stores and production
configuration continue to describe v1.

Use explicit prototype data stores, source copies/workspaces, ports, credentials
and publishing targets. Never infer active v1 stores as defaults. Adoption,
live migration, course rewrites and live Pages changes are separate future work.
The linked AI-assisted course predates this revision and needs its own outline
review before being treated as the new implementation sequence.

The first slice implements a draft post and optional scratch/checklist, immutable
identity, exact-file revisions and a Flet editor. Visual browser verification
remains pending because no browser was connected during implementation. Add managed images and an
ordered collection, then listings, preview and frozen releases. For each slice,
explain stored changes, demonstrate success and a meaningful failure, and record
what was verified and what remains uncertain. A test count alone is not evidence
that the behavior or explanation is understood.
