# wt2 and the smaller Flet CMS

[Plan index](README.md) · [Content model](content-model.md) · [Development stages](development-plan.md)

**Revised 2026-10-21.** Build authoring around Posts and Collections. The public
site has Home, Resume, Posts and Collections; public navigation is separate from
CMS navigation. Dedicated Home/Resume editing remains to be designed.

The proposed local declarative Flet application and independent headless `wt2`
CLI share Python application services. The [first slice](first-slice.md) now
implements draft-post CLI and editor behavior over Markdown records. Later
image/publication/collection flows below remain design targets. No SQLite,
hosted metadata database or embedded Kanban.

## Start writing without a planning gate

1. New post asks for a working title and creates a Draft record with an immutable
   ID and intended notebook path.
2. Open/create the notebook and write directly. It may start empty. There is no
   Planned state, Start action, structured brief or generated starter prose.
3. Save scratch notes or to-dos when useful. They may stay empty indefinitely.
4. Prepare the title, short description and thumbnail, then publish once the
   notebook has meaningful content. Publication checks readiness, not plan quality
   or checklist completion.

A draft can name a source that does not exist yet. Show that readiness state and
provide an actionable Create/Open notebook control once implemented. Never
silently overwrite an existing notebook. The source editor remains VS Code/Jupyter.

## Post editor

Use one editor page with these content controls:

- Title and short description.
- Optional tags in a comma-separated field; Save trims labels and removes exact
  duplicates. Leave blank to clear. Tags are public metadata.
- Thumbnail upload/replace and image preview. A missing draft thumbnail displays
  "Thumbnail required"; a published post must have a valid one.
- Notebook source path, Copy path, and Create/Open notebook as appropriate.
- Optional supporting code directory and Open code when it exists.
- Related-post search/select, saving ordered exact IDs.

Show the immutable ID and creation/public modification dates as read-only details.
Keep optional Internal notes and To-dos together in a clearly internal authoring
area. Notes are freeform scratch text. Checklist items have text and a checkbox,
can be reordered/edited/removed, and never gate publication.

Actions: Save, Publish/Return to draft, Preview and Delete. Publication may save
pending form fields and its verified image atomically. Exact deletion/undo review
is still open. Do not add portfolio fields, course controls or a separate Plan tab.

## Collection editor

Use one page containing Title, Cover upload/preview, Short description, Markdown
Long description and an ordered post list. Provide a simple introduction preview.

Search/select existing posts by title or ID; show identity and Draft/Published
status. Add, remove and reorder members by dragging or explicit Up/Down controls.
Prevent duplicates. A membership removal changes the collection only. Save the
whole form and member order under the loaded collection revision.

Show ID/dates read-only and the same optional Internal notes/To-dos authoring
area. Display the published/total member count so filtering on the public page
is predictable. Publishing a collection never changes member post status.
Exact collection publication validation remains a proposal in the content model.

## Lists and application frame

The CMS needs Posts and Collections destinations with search and status filters.
Post rows show thumbnail, title, description, dates and source readiness.
Collection cards can show cover, title, short description and member counts.
Provide clear empty states and preserve filters/return position after saving.

Home/Resume settings can be added after their fields are discussed. Preview/build
status and a small Settings entry belong in the frame. Storage keys, provider
versions, request IDs and recovery internals appear in diagnostics when needed;
they are not mandatory content fields. Preserve the white/charcoal/orange palette.

## Shared use cases and future CLI

The executable name remains `wt2`, separate from v1's repository-root
`.venv/bin/wt`. Run implemented project-local commands with `.venv/bin/wt2` from
`projects/watchtower2/`. Only command help and the first-slice walkthrough
establish what exists; later proposed flows are not installed commands.
The implemented draft-post commands and JSON shapes are documented in the
[first slice](first-slice.md) and nested command help.

Headless use cases should cover creating/reading/editing drafts, scratch/checklist
updates, post tags, thumbnail/cover changes, related IDs, membership/reordering,
publication, source inspection, preview and release preparation. Provide environment selection,
expected revisions, useful errors and structured context for agents. Add operational
diagnostics as real recovery/cleanup mechanisms arrive. Do not port v1's entire
command surface for compatibility that no prototype caller needs.

An agent can read public metadata, notebook content and internal scratch/checklist
through content context without loading every sibling notebook. Keep authoritative
content in the notebook and unfinished context in the entity's internal fields.
Internal-only writes advance the edit revision, never the public modified date.

Flet calls the same typed services directly; it does not shell out to `wt2`.
The CLI runs without a GUI/browser runtime or Flet installed. A future API adapter
may reuse those services if needed; it is not a prerequisite for local use.

## Separate Kanban CLI

Authors and agents may invoke an independent Kanban tool's CLI for tasks.
Watchtower2 neither implements nor chooses that tool, its database or its file
store. There is no Kanban tab, board schema, card attachment workflow, required
connector or automatic synchronization.

Task text can reference immutable post/collection IDs or source paths. Looking up
those IDs through `wt2` is enough to recover current content context. Entity notes
and to-dos remain separate from task-specific progress. Moving/completing a card
has no effect on publication, content dates or entity checkboxes.

## Saved state and editor state

| State | Example | Authority |
| --- | --- | --- |
| Saved content/authoring data | Post title, scratch text, member order, image reference | Application core and its configured stores. |
| Unsaved editor data | Changed description, selected upload, loaded revision | Flet form/session until successful save. |
| Presentation state | Selected tab, open preview, loading indicator | Component state. |

Keep explicit saves and stable editor identity. Re-rendering, changing a checklist
item or opening a preview must not erase other entered fields. Preserve submitted
values and selected uploads after validation failure or conflict. Dirty navigation
requires an explicit discard decision. Do not silently retry a stale edit.

Rendering controls has no storage effects. Event handlers delegate writes to
use cases. Run slow work outside the UI event loop and show discoverable outcomes;
a closed view does not prove a backend operation was cancelled. Ignore delayed
results belonging to a previously selected record.

Session-local unsaved drafts that survive re-renders are the initial recommendation.
Crash recovery for unsaved text is still open; do not promise it or write a
tracked history entry on every keystroke by accident.

## Early Flet evidence

Use disposable fixtures to demonstrate the real post editor and a small ordered
collection: controlled inputs, scratch/checklist changes, dirty navigation,
conflicting CLI/UI saves, thumbnail selection/cancellation/failure, keyboard
ordering controls, Markdown introduction preview, source links and a long preview
job. Record the chosen runtime, OS/browser and limitations. Browser file selection
must not assume a server filesystem path.

Choose and verify the pinned Flet/runtime version during implementation. The
previous broad Kanban/math/attachment feasibility project is no longer a required
starting stage; investigate those capabilities only if a current flow needs them.

## Interface changes from v1

The old HTML/no-JavaScript forms are not carried over into Flet. Preserve their
useful intent through labelled controls, keyboard access, focus restoration,
explicit reordering, preserved editor values and clear conflict messages.
A headless CLI supports agents; the Flet interface still needs its own usability
and accessibility evidence.

Build a use case and CLI action, then connect a thin Flet screen early. Continue
in small post/collection slices rather than finishing all storage administration
before the first usable authoring flow. The current CMS/site remain independent.
