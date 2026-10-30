# Working in Atlas

Atlas is a notebook-first content CMS with a Quarto website. Use the local
`at notebook` tools to navigate and edit notebook cells, and `at cms` to manage
content records. Run commands from the repository root with `uv run at ...`.
Run `uv sync` if dependencies are missing. Quarto is installed separately.

Read [README.md](README.md#content-cms-and-quarto-frontend) for the current
authoring workflow and setup. Each CLI command accepts `--help`. Remember to update this file (AGENTS.md) and the README.md each time the underlying code changes.

## Source ownership

| Path | What belongs here and how to edit it |
| --- | --- |
| `content/posts/<id>.ipynb` | Canonical post cells, code, outputs, attachments and cell options. Prefer `at notebook` for terminal edits; VS Code/Jupyter saves are supported. |
| `content/collections/<id>.yaml` | Authored `title`, `short_description`, Markdown `long_description` and optional `cover_caption`; edit directly or through the CMS. |
| `content/resume.yaml` | Authored résumé `title` and `summary`. |
| `content/resume/<entry-id>.yaml` | Authored entry `title`, `subtitle` and Markdown `body`. |
| `backend/` | CLI-managed IDs, metadata, source paths/digests, dates, publication, membership, ordering, notes and to-dos. Use CMS commands instead of hand edits. |
| `content/images/` | Canonical imported images; use CLI image commands to copy and link them. |
| `frontend/_cms/`, `frontend/index.qmd`, frontend configuration, theme/assets and `_metadata.yml` files | Editable site templates and presentation. |
| `frontend/posts/*.ipynb`, `frontend/collections/*.qmd`, `frontend/{posts,collections,resume}.qmd`, `frontend/assets/cms/` | Ignored generated copies. Regenerate with CMS sync; direct edits are overwritten. |
| `frontend/_site/`, `frontend/_site-preview/`, `.atlas/cms/` | Ignored render output and CMS runtime/recovery files. |

Preserve immutable IDs and source filenames when changing titles. Obtain IDs
from `new`, `ls` or `show`; collisions can produce suffixed IDs. Commit authored
content, imported images, backend records and deliberate template changes
together. Keep only public supporting assets beside notebooks: sync copies
notebook-relative sidecars into the frontend.

## Find and read content first

```sh
uv run at notebook map
uv run at notebook find "attention weights"
uv run at notebook outline post/attention
uv run at cms post ls
uv run at cms --json collection ls
uv run at cms resume ls --section employment
```

Examples below use `post/attention`, `collection/transformers` and
`resume/engineer-company`; substitute the actual IDs. CMS commands require exact
IDs. Notebook commands also accept a unique source stem or title; prefer the
exact post ID in scripts.

```sh
uv run at cms post show post/attention
uv run at notebook count post/attention
uv run at notebook cat post/attention --index 0 --context 1 --with-revision
uv run at notebook cat post/attention --label fig-attention
uv run at notebook cat post/attention --tag hide-input
```

`notebook outline post/attention` reads Markdown cells inside the source `.ipynb`
and prints JSON with `id`, notebook `revision` and `headings`. Each heading has
`text`, `level` (1–6), zero-based `cell_index` and one-based `line` within its cell.
Use `cell_index` with `cat --index` or `edit-cell --index`; refresh the outline
after inserting or removing cells. It includes headings inside lists and
blockquotes and skips code cells, code blocks, HTML blocks and comments.
Site TOC settings are global: `toc: true` and `toc-depth: 3` under `format.html`
in `frontend/_quarto.yml`.

Use `map`/`find`/`outline`/`cat` before reading raw notebook JSON or writing ad hoc
notebook scripts. `find` searches cell source, excluding outputs. Cell indices
are zero-based; `cat --index` accepts Python slices (such as `0:4` when there
are at least four cells) and negative indices. Source is truncated at
4096 characters per cell by default; use `--offset`/`--limit` to page or
`--limit 0` for the full source. Add `--with-outputs` only when outputs matter.

For an isolated workspace, put `--root /path/to/workspace` immediately after
`cms` or `notebook`. The default root is this checkout regardless of the shell's
current directory. Use `cms init` once for a new workspace (`--empty` skips
sample import).

## Edit notebook cells

Inspect the target cells, then use the smallest applicable operation:

```sh
uv run at notebook edit-cell post/attention --index 0 --file /path/to/cell.md
uv run at notebook append-cell post/attention --type code --file /path/to/example.py
uv run at notebook insert-cell post/attention --before 2 --content "## Results"
uv run at notebook tag post/attention --index 1 --add hide-input --remove old-tag
uv run at notebook remove-cell post/attention --index 3
```

For multiline source, a quoted heredoc avoids shell expansion:

```sh
uv run at notebook edit-cell post/attention --index 0 --file - <<'EOF'
## Attention

Write the replacement cell source here.
EOF
```

Use `--content`, `--file PATH` or `--file -` for agent edits. Without these,
notebook commands read piped stdin or open `$VISUAL`/`$EDITOR` in a terminal.
CMS `open`/`notes` commands open an editor unless given `--file`; metadata
`edit` commands can prompt if no field flags are supplied. Always provide
explicit input in noninteractive work. Cell source is limited to 20,000 characters.

`edit-cell` replaces the whole selected cell source and preserves its metadata,
attachments and stored outputs. Preserve Quarto cell options and labels in the
replacement text. Use a unique `--label` or `--tag` when useful; re-read indices
after inserting or removing cells. `remove-cell --tag` removes every matching
cell, so inspect matches first.

Use the standalone notebook tools for every cell operation; keep source
notebooks as ordinary cells. Quarto supplies the global TOC settings; the CMS
adds post document metadata during sync. Do not add required front matter,
planning cells or generated navigation/contents lists.

## Manage posts, collections and résumé entries

```sh
uv run at cms post new "Attention" --description "How attention works" --tags "python,transformers"
uv run at cms post edit post/attention --title "Understanding Attention" --description "An introduction to attention"
uv run at cms post edit post/attention --related post/another-post
uv run at cms post rm post/attention --yes

uv run at cms collection new "Transformers" --description "A reading sequence"
uv run at cms collection open collection/transformers --file /path/to/introduction.md
uv run at cms collection add collection/transformers post/attention
uv run at cms collection move collection/transformers post/attention --position 0
uv run at cms collection remove collection/transformers post/attention
uv run at cms collection rm collection/transformers --yes

uv run at cms resume add "Engineer · Company" --section employment --subtitle "2026 -- Present"
uv run at cms resume open resume/engineer-company --file /path/to/entry.md
uv run at cms resume edit resume/engineer-company --subtitle "Jan 2026 -- Present"
uv run at cms resume move resume/engineer-company --position 0
uv run at cms resume profile --summary "Updated opening summary."
```

New posts and collections start as drafts. Metadata edits affect listing fields;
notebook edits affect the post body. Repeat `--related` to set ordered related
post IDs; `--clear-related` clears them. Tags are comma-separated; `--tags ""`
clears them. Collection membership stores post IDs and uses zero-based
positions. Adding without a position appends; removing membership preserves the
post. The CMS generates the collection contents table. Removing a post deletes
its record and notebook, detaches it from collection and related-post lists, and
keeps managed images. Removing a collection deletes its record and introduction
and leaves member posts untouched. Both prompt unless `--yes` is supplied.

Each post owns one notebook source path. `check` and both sync modes reject
duplicate ownership across drafts and published posts before sync changes any
records or generated files. `post rm` refuses to delete a source claimed by
another post; repair the ownership conflict first.

Résumé sections are `employment`, `skills`, `education` and `projects`. Keep
section/position fields in backend records and authored text in content YAML.
Résumé content feeds both the web page and `frontend/assets/resume.pdf`.
`make preview` and `make build` regenerate the PDF before rendering the site.
`frontend/_cms/resume-pdf.qmd` controls its layout/contact links. Sync alone does
not render the PDF. Preserve existing facts and links when revising résumé prose.

Use `cms notes ID --file PATH` and `cms todos ID --add "Task"` for private
post/collection planning. To-dos support `--index N --done`, `--text`, `--position`
and `--remove`. Notes/to-dos stay out of the public frontend, do not change
public dates and do not gate publication.

## Import and replace images

```sh
uv run at notebook figure post/attention /path/to/plot.svg --caption "Attention weights" --alt "A heatmap of attention weights."
uv run at notebook figure post/attention /path/to/new-plot.png --replace --label fig-attention
uv run at cms post edit post/attention --thumbnail /path/to/thumbnail.png
uv run at cms collection edit collection/transformers --cover /path/to/cover.png
uv run at cms collection edit collection/transformers --cover-caption '*Cover title* by Artist'
```

These commands copy input bytes into managed storage and leave the originals
in place; no manual relocation is needed. Figure insertion appends by default;
`--index N` inserts at that zero-based position. Use the returned `fig-...` label
for later lookup/replacement. Replacement requires exactly one of `--index` or
`--label` and preserves caption, alt text, sizing, label and surrounding prose.
Omit `--caption`/`--alt` during replacement. Keep existing image copies that may
still have references. Thumbnails/covers accept verified PNG, JPEG, WebP or GIF
up to 20 MiB; notebook figures additionally accept SVG.
Collection cover captions support single-line Markdown and appear beneath the
cover on the collection page. Store them in the authored `cover_caption` field;
use `collection edit --cover-caption ""` to clear a caption. Replacing the cover
preserves its caption.

## Revisions and saved execution

When saving changes based on an earlier read, pass `--expected-revision`:
CMS mutations use the record revision returned by `show`; notebook mutations
use the `notebook:<hash>` token from `cat --with-revision` or `outline`. These
tokens are different. Refresh the relevant token after each mutation.

On a stale-write conflict, re-read the current record/cells and reconcile the
edit. Failed editor input is preserved in `.atlas/cms/edits/`; keep it available.
Do not bypass conflicts by dropping revision checks or deleting recovery files.
Avoid simultaneous CLI and IDE saves to the same source.

```sh
uv run at notebook output post/attention --index 8
uv run at notebook kernels
uv run at notebook run post/attention --index 8 --kernel python3 --timeout 300
uv run at notebook diff post/attention --base HEAD
```

Execute code explicitly when the task requires refreshed results. Editing and
site builds never run code. `run --index N` executes the prefix in a fresh kernel
but saves outputs only for the selected cell; omit `--index` to run the whole
notebook. Code errors are saved and produce exit status 1. Execution conflicts
preserve results in `.atlas/cms/execution-conflicts/`. `output` extracts embedded
images under `.atlas/cms/notebook-output/`. Clear outputs deliberately with
`notebook clear-outputs` and a locator or `--from N`; omitting both clears every
code cell's output.

## Validate, preview and finish

```sh
uv run at cms check
uv run at cms sync --preview
make preview                    # Draft-inclusive preview, port 4200
make preview PORT=4300
make build                      # Published content, frontend/_site/
```

`check` reports references and publication blockers for drafts as well as
published records. Exit 1 can be expected for unfinished drafts; report relevant
diagnostics without filling unrelated content just to make it pass. Preview
includes drafts in `frontend/_site-preview/`. After source edits during a running
preview, run `cms sync --preview` again to refresh generated copies. Public sync
(`cms sync`) and builds include published content only. Use CMS build/preview
entrypoints so sync runs first; they pass `--no-execute` to Quarto.

A publishable post needs a title, description, verified thumbnail and nonempty
notebook content. A collection needs a title, both descriptions, a cover and at
least one published member. Preserve publication state unless the task calls
for changing it; use `cms post publish/draft ID` or
`cms collection publish/draft ID`. Publishing sets build eligibility; deployment
is a separate operation. Publishing a collection does not publish its members.

Sync/build observes external notebook and entry-YAML edits by digest and may
update backend public modification dates in UTC. Review these backend changes
alongside source changes. Finish by re-reading edited cells/records, inspecting
`notebook diff` and `git diff` as applicable, and checking the relevant preview
or build when rendering is affected. Report what changed and what was verified.
For CLI implementation changes, run the relevant pytest tests; prose-only edits
do not require the full vault/coverage checks in `make doctor`.
