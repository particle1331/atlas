# Working in Atlas

Atlas is a notebook-first content CMS with a Quarto website. Use `at notebook`
for notebook cell operations, `at cms` for managed content records, and `at
pdf` to inspect and read local PDF documents. Run commands from the repository
root with `uv run at ...`.

[README.md](README.md#content-cms-and-quarto-frontend) is the reference for setup,
user workflows, examples and site/PDF behavior. Read the relevant section before
an unfamiliar operation; every CLI command accepts `--help`.

Update the relevant documentation when behavior changes: user workflows belong
in README.md, command syntax and matching rules in CLI help, and agent working
rules here. Keep shared explanations in one place and link to them.

## Source ownership

- Edit canonical notebooks under `content/posts/` through the notebook tools.
  Use CMS commands for IDs, managed metadata, publication, membership, ordering,
  notes and to-dos under `backend/`.
- Edit authored post `title`, `short_description` and `tags` in
  `content/posts/<id>.yaml` directly or through the CMS. This file contains only
  those three fields; preserve its filename and the notebook filename on renames.
  See [posts](README.md#posts) for the direct-edit workflow and validation rules.
- Edit authored collection and résumé text under `content/` directly or through
  the CMS. Collection introductions live in `content/collections/<id>.md`;
  keep title, short description and optional cover caption in the matching YAML.
  Preserve both filenames on title changes. Keep résumé section/position fields
  in backend records.
- Import images with the CLI. Keep existing managed copies that may still have
  references, and keep only public supporting assets beside notebooks because
  sync copies notebook-relative sidecars into the frontend.
- Supporting project code lives under `projects/`; see
  [supporting projects](projects/README.md). Treat imported weekly reference
  snapshots as read-only, use each post's CMS `code_path` and the project's
  release manifest to select the matching source, and keep adaptations separate.
- Site templates, configuration, theme/assets and `_metadata.yml` files under
  `frontend/` are editable. Regenerate projected posts, collections, listings
  and résumé pages through CMS sync; direct edits are overwritten.
- Treat `frontend/_site/`, `frontend/_site-preview/` and `.atlas/cms/` as generated
  output or runtime/recovery files. See the [source layout](README.md#source-layout)
  for exact paths.

Preserve immutable IDs and source filenames when changing titles. Obtain exact
IDs from `new`, `ls`, `show` or `cms id`; collisions can produce suffixed IDs.
Prefer exact IDs in scripts; see [workspace and record IDs](README.md#workspace-and-record-ids).
Each post must own a distinct notebook source path. Repair ownership conflicts
before sync or removal. Keep related authored content, imported images, backend
records and deliberate template changes together when committing.

## Read before editing

Use `map`/`find`/`outline`/`cat` before reading raw notebook JSON or writing ad hoc
notebook scripts. A small starting sequence is:

```sh
uv run at notebook map
uv run at notebook find "attention weights"
uv run at notebook outline post/attention
uv run at notebook cat post/attention --index 0 --with-revision --limit 0
```

Substitute the actual post ID. Inspect complete target cells and preserve
Quarto options, labels, attachments and metadata. Cell indices are zero-based;
refresh the outline after inserting or removing cells. Read stored outputs only
when they matter. See [notebook tools](README.md#notebook-tools) for locators,
source paging and command examples.

## Make deliberate edits

Use the smallest applicable notebook operation for every cell change.
`edit-cell` replaces the entire selected source while preserving stored outputs;
keep its existing options and surrounding content. Inspect all matches before
using `remove-cell --tag`, which removes every matching cell.

Provide explicit input in noninteractive work: use `--content`, `--file PATH`
or `--file -` for notebook edits, `--file` for CMS `collection open`, `resume open`
and `notes`, and explicit field flags for metadata edits. These commands can
otherwise open an editor or prompt. Use a quoted heredoc for multiline input to
avoid shell expansion. See [posts](README.md#posts) and
[collections](README.md#collections) for opening source files in VS Code.

Keep source notebooks as ordinary cells. Do not add required front matter,
planning cells or generated navigation/contents lists. The CMS supplies document
metadata, and Quarto supplies global TOC settings.

Preserve publication state unless the task calls for changing it. Publishing
sets build eligibility; deployment is separate, and publishing a collection
does not publish its members. Use CMS commands for destructive record operations
so references are maintained. See [posts](README.md#posts) and
[collections](README.md#collections) for their effects and requirements.

Use [image commands](README.md#images) to import and replace figures, thumbnails
and covers. For figure replacement, retain the existing caption, alt text,
label and sizing; omit `--caption`/`--alt` when using `--replace`.

Preserve existing facts and links when revising résumé prose. Keep résumé sync
enabled in preview and public modes so authored changes reach both the web page
and PDF. See [résumé PDF](README.md#résumé-pdf) for rendering and layout details.
Use CMS notes/to-dos for private planning; see [writing, notes and storage](README.md#writing-notes-and-storage).

## Writing style for posts and collections

Use the [AI-Native Software Development introduction](content/collections/ai-assistant-development.md)
and its [listing description](content/collections/ai-assistant-development.yaml)
as voice references when proposing or revising collection descriptions. Adapt
the emphasis to the collection; keep the tone concrete and understated. Apply
the same voice principles to post introductions.

- Use first person for the author's specific work, choices, observations or
  results, supported by the available material. Attribute general course
  activities and learning objectives to "the course" or "the module" instead
  of turning them into personal plans or experience. For example, write "The
  course compares development tools" for a module overview; use "I chose this
  tool because..." only for an actual choice the author has described.
- Make `short_description` a concise sentence telling readers what to expect.
  Name the subject and the kind of work collected, such as notes or projects.
- Keep `long_description` to one or two focused paragraphs by default: establish
  the context, then explain the work and questions that connect the entries.
  For course-based collections, preserve attribution and links while centering
  the author's learning rather than reproducing the syllabus.
- Prefer plain verbs and specific activities to hype, broad promises, generic
  slogans or lists of tools. Explain what the tools help the author do.
- Keep claims grounded in the source material and actual progress. Distinguish
  planned exploration from completed work; do not invent experience or results.
- Make subtle improvements that preserve the author's intent and scope. Apply
  these principles without forcing every collection into the same template.

### Writing voice

For technical explanations, aim for the voice of a clear 1960s mathematics
textbook: precise, restrained, and pedagogical. The reference is to the care
of the exposition, not dated vocabulary or ornamental formality.

- Develop the explanation from a principle through a concrete example to its
  consequences. Introduce assumptions before relying on them, and explain why
  each step follows. Let this progression guide the prose without making every
  passage follow a fixed template.
- Explain limitations through their causes rather than issuing declarations or
  accumulating warnings. Keep caveats relevant to the concept being taught;
  a short example need not become a checklist of every production concern.
- Condense repetition, not reasoning or evidence. Preserve useful source links
  and the scope of the claims they support when shortening a passage.
- Explain the reasoning in explanatory prose rather than directing the reader.
  Prefer "We keep the message intact because..." to "Keep the message intact."
- Use "we" for shared walkthroughs and "I" for the author's actual choices or
  observations, grounded in the source material. Do not imply shared experience
  or agreement where there is none.
- Reserve imperatives for procedures, checklists, and warnings, where direct
  instructions serve a clear purpose.
- Prefer concrete explanations to generic advice or authoritative-sounding
  claims. State the mechanism, reason, or tradeoff instead of merely telling
  readers what they should do.
- Rewrite naturally rather than mechanically adding "we want to" to every
  instruction. A description of what the code does may be clearer.

Examples for explanatory prose:

| Instead of | Prefer |
|:--|:--|
| "Keep the returned assistant message intact." | "We keep the returned assistant message intact so the next request includes its `reasoning_content`." |
| "Use `asyncio.gather` for independent lookups." | "These lookups are independent, so we use `asyncio.gather` to overlap their I/O waits." |
| "You must validate tool arguments." | "The dispatcher validates tool arguments before execution because a model-generated request can contain unexpected fields or values." |
| "The application controls concurrency—not the model." | "The `tool_calls` array supplies names and arguments, but no dependency information. The harness chooses how to execute the calls using application-defined rules about the tools and the resources they affect." |

### Teaching technical concepts

- Prefer tables to unordered lists for enumerations, such as categories,
  alternatives, or comparisons. Use meaningful column headings to show what
  each entry describes. Retain numbered lists when order matters, as in
  procedures, sequential steps, or a derivation.
- Organize learning posts around the ideas readers need to understand or apply.
  Use the source as a starting point. Spend space on mechanisms, assumptions,
  and failure cases that change how a reader would reason, implement, or
  evaluate something. Cut repetition, dated background, and examples that
  teach the same point.
- Develop important ideas with a worked example, a counterexample, or an
  experiment the reader can inspect. Explain what the example demonstrates
  and what would count as evidence for a stronger claim.
- Bring in current research and engineering conventions when they clarify,
  qualify, or correct the source. Verify and cite the relevant evidence.
  Distinguish the source's example, later findings, and the author's own
  results.

## Revisions and saved execution

When saving changes based on an earlier read, pass `--expected-revision`.
CMS mutations use the record revision from `show`; notebook mutations use the
`notebook:<hash>` token from `cat --with-revision` or `outline`. Refresh the
relevant token after each mutation.

On a stale-write conflict, re-read and reconcile the current record/cells.
Do not bypass conflicts by dropping revision checks or deleting recovery files.
Keep failed edits in `.atlas/cms/edits/` and execution conflicts in
`.atlas/cms/execution-conflicts/` available. Avoid simultaneous CLI and IDE saves
to the same source. See [revisions](README.md#revisions) for the full workflow.

Execute code explicitly only when refreshed results are needed. Edits and site
builds never run code. Clear outputs deliberately, and preserve unrelated saved
results. See [saved execution](README.md#saved-execution) for prefix execution,
output extraction and clearing behavior.

## Commit command handoff

The `/commit` command authorizes its child session to stage clear, in-scope
changes and create new local commits, but never to push or rewrite history.
When it returns, briefly display the actual commit count, hashes, messages,
checks, exclusions and remaining changes in the main conversation. Do not
require the user to open the child session or request a summary. Relay the
result without repeating the review or creating additional commits; report
failures and partial completion explicitly.

## Validate and finish

Run `uv run at cms check` for content changes. It reports draft blockers too;
report relevant diagnostics without filling unrelated drafts just to make it
pass. A running `make preview` automatically syncs source edits; use
`uv run at cms sync --preview` to refresh generated copies without a preview.
Post and collection creation refresh the draft preview automatically. For a
one-time render after later edits, use `uv run at cms build --preview`.
See [preview and build](README.md#preview-and-build) for watching behavior.

Check the relevant preview or build when rendering is affected. Use CMS
preview/build entrypoints so sync runs first and Quarto receives `--no-execute`;
see [preview and build](README.md#preview-and-build). Sync/build can observe
external source edits and update backend public modification dates in UTC;
review those changes alongside the authored content.

Use the [repository secret scan](README.md#secret-scanning) before sharing
changes. It is separate from `cms check`; the Pages build also checks the
rendered artifact before upload. Never print suspected credential values.

Finish by re-reading edited cells/records and inspecting `notebook diff` and
`git diff` as applicable. Report what changed and what was verified. For CLI
implementation changes, run relevant pytest tests. Prose-only edits do not
require the full vault/coverage checks in `make doctor`.
