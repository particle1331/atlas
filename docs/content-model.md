# Posts, collections and authoring

[Plan index](README.md) · [CMS and CLI](cli-v2-and-flet.md)

**Atlas implementation updated 2026-10-28:** [the CMS CLI](cms-cli.md) implements
this logical model with editable notebooks and prose YAML under `content/`, and
CLI-managed metadata under `backend/`.
Builds inject document metadata into ignored copies under `frontend/posts/`.
The YAML storage and résumé schema below supersede the earlier Markdown choice.

**Decisions recorded 2026-10-21.** Watchtower2 has two reusable content types:
notebook posts and ordered collections of posts. The public site has Home,
Resume, Posts and Collections. Internal authoring data persists alongside the
content records but stays out of the frontend. This replaces the earlier v1
feature-parity target. The [first draft-post slice](first-slice.md) is implemented;
collections, images and publication are still design targets.

## Site pages

| Page | Presentation |
| --- | --- |
| Home | Landing page. Its editable fields remain to be discussed. |
| Resume | Dedicated page generated from `content/resume.yaml` and ordered YAML entries in `content/resume/`; existing facts are preserved. |
| Posts | A listing with image thumbnails beside titles, short descriptions and dates. |
| Collections | Cards in a grid, similar to the v1 course listing, with covers, titles and short descriptions. |

Home and Resume do not introduce additional reusable content types. A project
write-up, tutorial, course chapter or photo essay can be a notebook post.
Collections organize posts without a separate course/chapter/section hierarchy.

## Shared rules

- An `id` is assigned once at creation and never changes. This applies to every
  post and collection, regardless of any edits. Exact ID format and allocation
  remain implementation choices; the examples use readable prefixes.
- `status` is `draft` or `published`. New records are drafts. There is no
  Planned state, separate visibility switch, Start action or prose seeding.
- Drafts can be incomplete. Create a post with a working title; the system
  assigns its ID and intended notebook path. Notebook creation/opening mechanics
  remain to be implemented without a mandatory planning step.
- `created_at` records creation. `updated_at` is the public last-modified date,
  reflecting changes to public content. Both are system-managed.
- `internal_notes` is optional freeform scratch text, with no required outline
  or completeness standard. `internal_todos` is an ordered list of
  `{text, done}` items. Both can be edited at any stage or left empty.
- Editing internal notes or to-dos never changes `updated_at`. Checklist
  completion is not a publication requirement.
- Backend edit revisions still change on authoring saves. A public timestamp
  must not double as the token used to reject stale writes.

## Post

```yaml
id: post/attention
status: draft
title: Understanding Attention
short_description: ""
tags: [python, transformers]
thumbnail_path: null
source_path: content/posts/attention.ipynb
code_path: projects/transformers
related_post_ids: []
created_at: 2026-10-21T02:00:00Z
updated_at: 2026-10-21T02:00:00Z
internal_notes: ""
internal_todos:
  - text: Add a worked example
    done: false
```

| Field | Meaning |
| --- | --- |
| `id` | Immutable post identity. |
| `status` | Draft or Published; publication eligibility is separate from deployment. |
| `title` | Display title. A working title is sufficient for a new draft. |
| `short_description` | Short listing description. |
| `tags` | Optional list of public labels, defaulting to `[]`. |
| `thumbnail_path` | Managed listing image; required to publish. Drafts may omit it. |
| `source_path` | Path to the canonical `.ipynb` file, relative to the configured source workspace. |
| `code_path` | Optional supporting code directory, relative to the configured repository root. Multiple posts can reference the same directory. |
| `related_post_ids` | Ordered stable IDs of related posts. Defaults to `[]`. |
| `created_at`, `updated_at` | Creation and public modification timestamps. |
| `internal_notes`, `internal_todos` | Persistent authoring scratch text and checklist; excluded from the frontend. |

The notebook owns the complete body: prose, code cells, stored outputs, inline
attachments and cell options. The CMS owns listing metadata. It supplies
document metadata to generated copies without changing the authored source.

Tags are plain labels, with no separate taxonomy records. Trim surrounding
whitespace and remove exact duplicates, preserving spelling, capitalization and
first-seen order. Each label is nonempty and contains no commas or line breaks;
the editor uses comma-separated input. Save `[]` to clear tags. Changes to tags
advance the public `updated_at`; normalized no-op edits leave it unchanged.
Collections do not have their own tags.

`code_path` references shared code; it does not establish ownership. Deleting a
post leaves that directory intact. A shared repository setting can turn the
path into a Source code link. There is no separate Project content type just
to support that link. Code-directory edits triggering a post's public date are
an open policy question; changing the post's `code_path` is a public metadata edit.

A published post requires a title, short description, valid thumbnail and an
existing notebook with meaningful content. The CMS offers Upload/Replace
thumbnail and shows "Thumbnail required" for an unfinished draft. Publishing
or rendering does not implicitly execute notebook cells.

Collection membership is stored on collections, not duplicated on posts.

## Collection

```yaml
id: collection/transformers
status: draft
title: Transformers from Scratch
cover_path: null
short_description: ""
long_description: ""
post_ids:
  - post/attention
  - post/training
created_at: 2026-10-21T02:00:00Z
updated_at: 2026-10-21T02:00:00Z
internal_notes: ""
internal_todos:
  - text: Write the introduction
    done: false
```

| Field | Meaning |
| --- | --- |
| `id` | Immutable collection identity. |
| `status` | Draft or Published. Publishing a collection does not publish its posts. |
| `title` | Display title. |
| `cover_path` | Managed image for the collection card and page. |
| `short_description` | Description shown on its card. |
| `long_description` | Markdown introduction on its page. |
| `post_ids` | Ordered member post IDs, with no duplicates. Defaults to `[]`. |
| `created_at`, `updated_at` | Creation and public modification timestamps. |
| `internal_notes`, `internal_todos` | The same internal authoring fields as posts. |

A collection has no source notebook. Generate its page from its own metadata
and the referenced posts. Do not duplicate post titles, descriptions or paths
on the collection. One post can belong to several collections or none.
Collections contain posts, without nesting or per-membership overrides.

Public collection pages show published members in their stored order. Post
publication is independent of collection publication. Editing a member post
does not change the collection's `updated_at`; editing membership or order does.

**Proposed publication validation, still open:** require a title, valid cover,
both descriptions and at least one published member. The draft/published
relationship is established; these exact collection requirements and the
empty-published-collection case still need agreement.

## Dates and internal edits

The settled rule is that scratch text and checklist edits do not alter public
modification dates, on either content type. Notebook edits count as post content
changes. Collection dates reflect edits to the collection itself.

Proposed implementation conventions: store UTC timestamps, display in the site
timezone (initially Asia/Manila), keep creation dates fixed, and leave dates
unchanged after no-op, failed or stale saves. Use a separate edit revision for
every accepted record mutation, including internal-only saves.

Notebook changes made in VS Code/Jupyter need source-change detection. The
mechanism and timestamp meaning when the CMS was closed remain to be decided;
do not silently treat file modification time as an authoritative edit history.
Rendering captured source bytes must not mark a post as newly modified.

Public projections must omit authoring-only revision values and history. A
scratch edit must not alter public release metadata or hashes indirectly just
because it changed the record revision.

## Lightweight authoring

Open a draft and write directly in the notebook. Notes hold rough ideas,
unresolved questions, references or agent instructions. To-dos hold small next
actions. Neither needs to be written before starting, perfected, consumed or
copied automatically into the body.

Agents read current notebook content and these authoring fields through the
future `wt2` CLI. They write accepted prose/code into the notebook and keep
unfinished context in the scratch field or checklist. Public metadata is
explicitly authored; it is not inferred from internal notes.

The frontend receives only the selected public metadata, eligible links and
notebook projections. "Internal" means excluded from the site; its confidentiality
also depends on the eventual storage and backup configuration.

## Separate Kanban

Kanban is a separate tool with its own CLI and storage. Watchtower2 has no Kanban
tab, card records, board counters, card attachments or task-driven publication.
You and agents can invoke the separate CLI directly. Its choice of tool and
storage is outside this project's implementation scope.

Tasks may reference immutable post/collection IDs or source paths. There is no
required synchronization, mirrored checklist, automatic task creation or task
completion requirement for publication. Entity notes and to-dos remain useful
without a running Kanban application.

## Authoring storage

Authoring records in Atlas are YAML files, selected by the user on 2026-10-28.
This replaces the earlier Markdown/front-matter storage choice for this CLI.
Editable files live under `content/`, and CLI-managed fields live under `backend/`.
Posts have `backend/posts/<stable-id>.yaml` and a canonical
`content/posts/<stable-id>.ipynb`. Collections have editable `title`,
`short_description` and Markdown `long_description` in
`content/collections/<id>.yaml`; IDs, cover, membership, status, dates and internal
fields are in `backend/collections/<id>.yaml`. Their contents list is generated
from backend `post_ids`. There is no database.

Résumé profile fields (`title`, `summary`) live in editable `content/resume.yaml`.
Each `content/resume/<entry-id>.yaml` contains editable `title`, `subtitle` and
Markdown `body`. Its immutable ID, section, zero-based position and dates are in
`backend/resume/<entry-id>.yaml`. Sections are employment, skills, education and
projects. The CLI handles section headings, entry ordering and public layout.
The storage schema version is recorded in `backend/cms.yaml`.

Every backend record stores a `source_path` and authoring-only `source_digest`.
Sync/build observes hand edits to notebooks, collections and résumé entries,
updates public dates once, and preserves the authored source bytes. Combined CLI
read/write revisions include editable collection/résumé source bytes to reject
stale saves. Post records additionally store `toc` and `toc_depth`. Image
imports are verified PNG/JPEG/WebP/GIF files up to 20 MiB, stored by digest under
`content/images/`. Collection publication in this implementation requires both
descriptions, a cover and at least one published member.

Image inputs can be anywhere on the local filesystem; importing copies their
original bytes into managed storage. `at notebook figure <post> <image-path>`
also accepts SVG and stores each figure as
`content/images/post/<post-id>-<uuid>.<ext>`. It appends or inserts a Quarto
Markdown figure cell at a zero-based index. Generated notebooks reference
copies of the used figure files under `frontend/assets/cms/post/`.

`make docs` and `make build` sync source and allowlisted metadata into generated
notebooks/pages under `frontend/`. Generated content, locks and recovery files
are ignored; canonical content, backend records and public templates are tracked. No build edits
or executes the source notebook. See the [CLI guide](cms-cli.md) for exact paths,
publication requirements and source-observation timestamp semantics.

Real authoring records may be tracked in Git. Metadata and internal edits
intentionally produce readable diffs, while public projections continue to omit
internal data and keep public dates unchanged. Runtime locks and generated
output are ignored. This is a change from the earlier no-Git-diff goal.

## Remaining choices

- Managed image layout, backup/restore and publication retention. Image bytes are
  ordinary files, not embedded database payloads; future hosting is separate.
- Home editing fields and storage; résumé PDF generation.
- Frozen release transport and retained-image cleanup beyond local builds.
- Whether supporting code edits should eventually affect post modification dates.
- Source-code link versioning, deletion/undo policy
  and whether context attachments are useful. Do not import the entire v1 feature
  set to answer these questions.

The v1 system and linked AI-assisted development course remain untouched. Their
broader planning and Kanban workflows are historical context until separately
reviewed for migration or course revision.
