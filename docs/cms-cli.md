# Atlas content CLI

The current implementation is `uv run at cms`. It follows the post/collection
[content model](content-model.md), with the user's 2026-10-28 changes: YAML
editable sources under `content/`, CLI-managed records under `backend/`, and ignored frontend copies
generated before every preview/build. Earlier `wt2`/Flet documents describe a
separate historical prototype; Atlas does not depend on it.

## Source and generated files

| Path | Role |
| --- | --- |
| `content/posts/<id>.ipynb` | Canonical body, code, outputs, attachments and cell options. |
| `content/collections/<id>.yaml` | Editable `title`, `short_description`, Markdown `long_description` and optional `cover_caption`. |
| `content/resume.yaml` | Editable résumé `title` and `summary`. |
| `content/resume/<entry-id>.yaml` | Editable entry `title`, `subtitle`, and Markdown `body`. |
| `backend/posts/<id>.yaml` | CLI-managed post metadata, notes/to-dos, source path and digest. |
| `backend/collections/<id>.yaml` | CLI-managed ID, cover, status, dates, ordered post IDs and internal fields. |
| `backend/resume/<entry-id>.yaml` | CLI-managed ID, section, position, dates, source path and digest. |
| `backend/cms.yaml` | CLI-managed storage schema version. |
| `content/images/<sha256>.<ext>` | Imported, verified image bytes. |
| `content/images/post/<post-id>-<uuid>.<ext>` | Copied notebook figure images. |
| `frontend/_cms/resume.qmd` | Public résumé layout; entry content is supplied by YAML. |
| `frontend/_cms/resume-pdf.qmd` | PDF résumé layout/contact links; uses the same YAML content. |
| `frontend/assets/resume.pdf` | Download regenerated before each preview/build. |
| `frontend/_cms/posts.qmd`, `frontend/_cms/collections.qmd` | Public listing templates. |
| `frontend/posts/*.ipynb` | Generated notebook copies; ignored. |
| `frontend/collections/*.qmd`, `frontend/resume.qmd` | Generated pages; ignored. |
| `frontend/posts.qmd`, `frontend/collections.qmd` | Generated listings; ignored. |
| `frontend/assets/cms/` | Generated image copies; ignored. |
| `.atlas/cms/` | Ignored locks, interrupted-save journal and preserved failed edits. |

Edit files under `content/` by hand or through the CLI. Use the CLI to change
records under `backend/`, including membership, order and publication. Keep
existing source filenames stable; IDs and source paths are assigned by the CLI.
The editable YAML files contain only authored fields, with no IDs, dates, source
digests or ordering fields. `show` combines source text and backend metadata into
one logical record for inspection.

Commit `content/`, `backend/` and frontend templates/configuration. Backend records
are persistent data required to rebuild the site. Generated frontend paths are
disposable; direct edits there are replaced on the next sync. IDs are assigned
once from the initial title, with a random suffix on collision. Title edits do
not rename any file. `post/attention` has the permanent source
`content/posts/attention.ipynb`. Collections store IDs instead of copied post
titles, so title edits appear on the next build.

## Initialization

```sh
uv run at cms init
```

This imports existing frontend QMD posts into plain notebooks and separate YAML,
collection descriptions/membership into YAML, and résumé facts into individual
entries. The original résumé styling/contact block becomes a public template.
Imported post/collection QMD files are removed only after their source records
are staged successfully; the corresponding frontend paths are now generated.
Incomplete imported examples become drafts. `init` also migrates the previous
layout: post metadata moves from `content/posts/` to `backend/posts/`, collection
and résumé files are split into editable text and backend records, and the schema
marker moves to `backend/cms.yaml`. IDs, dates, membership and notebook bytes are
preserved. Migration uses the recovery journal and refuses conflicting backend
records. Repeated initialization after migration is a no-op.
`init --empty` skips importing sample content. Initialization rejects unknown
résumé sections or conflicting source paths before saving any imported files.

For an isolated workspace, put the frontend templates there and use
`at cms --root /path/to/workspace ...`. The default root is the Atlas checkout,
independent of the shell's current directory.

## Posts

```sh
uv run at cms post new "Attention" --description "How attention works" --tags "python,transformers"
uv run at cms post ls
uv run at cms post show post/attention
uv run at cms post edit post/attention
uv run at cms post edit post/attention --title "Understanding Attention" --tags "python,math"
uv run at cms post edit post/attention --thumbnail /path/to/image.png
uv run at cms post edit post/attention --code-path projects/transformers
uv run at cms post edit post/attention --related post/another-post
uv run at cms post edit post/attention --clear-related
uv run at cms post toc post/attention --depth 3
uv run at cms post toc post/attention --disabled
```

`new` creates a draft record and a notebook with one empty Markdown cell. Open
the `.ipynb` directly in VS Code/Jupyter and add/edit cells normally. There are no
required front-matter, navigation or planning cells. Normal Markdown headings
populate the generated TOC. `--tags ""` clears tags; labels are trimmed and exact
duplicates removed. Repeat `--related` to set ordered related IDs.

For terminal editing without notebook JSON:

```sh
uv run at cms post cells post/attention
uv run at cms post open post/attention              # Single-cell body only
uv run at cms post open post/attention --cell 0     # Zero-based index
uv run at cms post open post/attention --append
uv run at cms post open post/attention --append --code
uv run at cms post open post/attention --cell 0 --file body.md
cat body.md | uv run at cms post open post/attention --cell 0 --file -
```

`open` uses `$VISUAL`, then `$EDITOR`, then `vi`. Editor arguments are supported
(for example `EDITOR='code --wait'`). It edits only the selected cell source.
Unchanged cells retain metadata, attachments and outputs. A changed code cell
has its execution count and outputs cleared, and is never executed by the CMS.
Use Jupyter/VS Code to run code and save its outputs explicitly.

## Collections

```sh
uv run at cms collection new "Transformers" --description "A reading sequence"
uv run at cms collection edit collection/transformers --cover /path/to/cover.png
uv run at cms collection edit collection/transformers --cover-caption '*Cover title* by Artist'
uv run at cms collection open collection/transformers
uv run at cms collection add collection/transformers post/attention
uv run at cms collection add collection/transformers post/another-post --position 0
uv run at cms collection move collection/transformers post/attention --position 0
uv run at cms collection remove collection/transformers post/another-post
uv run at cms collection show collection/transformers
```

`open` edits just the Markdown introduction; `--file` works here too. Membership
positions start at zero. Adding without a position appends. Duplicate, self and
unknown references are rejected.
Removing membership leaves the post and its notebook intact. The ordered Contents
table is generated automatically with linked titles, short descriptions, estimated
reading times, and creation dates. Reading time uses notebook Markdown
at 200 words per minute, rounded up to at least one minute. You can also edit
`title`, `short_description` and `long_description` directly in
`content/collections/<id>.yaml`. Membership, cover, publication and dates are
managed through the CLI in `backend/collections/<id>.yaml`.

`--cover-caption` sets a single-line Markdown caption beneath the cover on the
collection page; emphasis and links are supported. It can be supplied with
`--cover` or used separately. The caption is editable as `cover_caption` in the
collection's content YAML and defaults to empty for existing collections.
Replacing the cover preserves its caption; pass `--cover-caption ""` to clear it.

## Notebook navigation and cell tools

Notebook tools are a standalone command group beside `cms` and `vault`:

```sh
uv run at notebook map
uv run at notebook find "attention weights"
uv run at notebook count post/attention
uv run at notebook cat post/attention --index 0:4 --context 1
uv run at notebook cat post/attention --tag hide-input
uv run at notebook cat post/attention --label fig-attention
uv run at notebook cat post/attention --with-outputs --with-revision
```

Notebook arguments accept an exact `post/<id>`, unique source stem or unique
title. `map` lists registered posts; `find` searches cell source, not outputs.
`cat` renders cells as Markdown and strips notebook JSON. Indices are zero-based;
ranges use Python slice form (`0:4`, `2:`, `:3`, or `-1`). `--context N` adds
neighboring cells. Source defaults to 4096 characters per cell; `--limit 0` shows
all. Use `--offset` and `--limit` to page through long cells.

```sh
uv run at notebook edit-cell post/attention --index 0
uv run at notebook edit-cell post/attention --label fig-attention --file cell.py
uv run at notebook append-cell post/attention --type code
uv run at notebook insert-cell post/attention --after 0 --content "## Results"
uv run at notebook remove-cell post/attention --tag generated
uv run at notebook tag post/attention --index 1 --add hide-input --remove old-tag
uv run at notebook clear-outputs post/attention --from 4
uv run at notebook clear-outputs post/attention
```

Cell locators and insertion positions are zero-based. Cell edits preserve metadata,
attachments and stored outputs. Re-run changed code when its outputs need updating.
`tag` takes repeated `--add`/`--remove` values and prints current tags when neither
is supplied. `remove-cell` requires an explicit locator; `--tag` can remove every
match, while `--label` must be unique. Other cell edits need one unique locator.
`clear-outputs` skips Markdown cells and clears every code cell
when called without a locator.

Provide source with `--content`, `--file PATH` or `--file -`; without either, the
CLI reads piped stdin or opens `$VISUAL`/`$EDITOR` in a terminal. Cell source is
capped at 20,000 characters. Saves update the post source digest and public date.
Stale editor input is preserved under `.atlas/cms/edits/`.

Insert an image from any local path, including your Desktop:

```sh
uv run at notebook figure post/attention ~/Desktop/plot.png
uv run at notebook figure post/attention "/path/to/diagram.svg" --index 0
uv run at notebook figure post/attention ~/Desktop/plot.jpeg --caption "Attention weights" --alt "A heatmap of attention weights."
```

Like `cat`, `figure` takes the notebook name first. It copies the input bytes into
`content/images/post/<post-id>-<uuid>.<ext>` and adds a Markdown cell using
[Quarto figure syntax](https://quarto.org/docs/authoring/figures.html). Each import
gets its own filename and `fig-...` label, returned with the inserted cell index.
`cat --label` also recognizes these Markdown figure IDs. `--caption` accepts plain
text and `--alt` sets an accessible description. Both are optional and editable
in the notebook afterward.

Without `--index`, the cell is appended. Indices are zero-based insertion
positions: `0` inserts before the first cell and the current cell count appends.
PNG, JPEG (`.jpg`/`.jpeg`), WebP, GIF and SVG images up to 20 MiB are accepted.
The original image stays in place; moving, editing or deleting it later does not
affect the copy. The copy, notebook and post metadata are saved together through
the recovery journal. `--expected-revision` rejects stale notebook edits.

Replace a figure image while preserving the text you edited in its cell:

```sh
uv run at notebook figure post/attention ~/Desktop/new-plot.svg --replace --index 2
uv run at notebook figure post/attention ~/Desktop/new-plot.png --replace --label 'fig-attention-<uuid>'
```

Replacement requires exactly one of `--index` or `--label` and a Markdown cell
containing one image. It changes only the image URL; captions, cross-reference
labels, alt text, sizing, surrounding prose, cell IDs and metadata are preserved.
The new file is copied into `content/images/post/`, and different input formats
are supported. Existing image copies stay available for other references.
`--caption` and `--alt` apply to insertion; omit them when using `--replace`.
Stale revisions and invalid selections fail before any new copy is committed.
Use `post edit --thumbnail PATH` or `collection edit --cover PATH` to replace
listing images; these commands also copy the supplied file automatically.

```sh
uv run at notebook output post/attention --index 8
uv run at notebook output post/attention --index 8 --output 0
uv run at notebook run post/attention
uv run at notebook run post/attention --index 8 --kernel python3 --timeout 300
uv run at notebook kernels
uv run at notebook diff post/attention --base HEAD
```

`output` prints stored text/errors and writes embedded PNG/JPEG/GIF/WebP/AVIF/SVG
images under `.atlas/cms/notebook-output/`. `run` is explicit: it uses the
notebook kernel (or `--kernel`), saves outputs and inline error results, and never
runs during a build. `--index` executes the notebook prefix in a fresh kernel but
saves output for only the selected cell. Cell errors are saved as outputs and
cause `run` to exit with status `1`. If source changes during execution,
results are retained in `.atlas/cms/execution-conflicts/`. `diff` compares cell
source against a Git ref without output JSON. `kernels` lists installed Jupyter
kernels.

## Résumé

```sh
uv run at cms resume ls
uv run at cms --json resume ls --section employment
uv run at cms resume show resume/employment-sr-machine-learning-engineer-afni
uv run at cms resume open resume/employment-sr-machine-learning-engineer-afni
uv run at cms resume edit resume/employment-sr-machine-learning-engineer-afni --subtitle "Jan 2025 -- Present"
uv run at cms resume add "Engineer · Company" --section employment --subtitle "2026 -- Present"
uv run at cms resume move resume/engineer-company --position 0
uv run at cms resume rm resume/engineer-company --yes
uv run at cms resume profile --summary "My updated opening summary."
```

Sections are `employment`, `skills`, `education`, `projects`. Each entry's body
is Markdown in a YAML block scalar. Its title/subtitle/section/order are explicit
fields in editable `content/resume/<id>.yaml`; section, position, ID and dates are
in `backend/resume/<id>.yaml`. The renderer supplies headings and section ordering; `open` exposes only
the body. Imported résumé facts, existing links and contact controls are retained.
The homepage is independent. Résumé edits reach the web page at sync; preview
and build also regenerate the downloadable PDF from the same title, summary and
ordered entries. Edit `frontend/_cms/resume-pdf.qmd` for its layout/contact links,
not the generated PDF. Workspaces without that optional template get a basic
PDF containing the résumé title, summary and entries.

## Internal authoring and publication

```sh
uv run at cms notes post/attention
uv run at cms todos post/attention --add "Add a worked example"
uv run at cms todos post/attention --index 0 --done
uv run at cms todos post/attention --index 0 --text "Revise the example"
uv run at cms todos post/attention --index 0 --position 1
uv run at cms todos post/attention --index 0 --remove
uv run at cms check
uv run at cms post publish post/attention
uv run at cms collection publish collection/transformers
uv run at cms post draft post/attention
```

Notes/to-dos work on posts and collections, persist in YAML and never enter the
frontend or change public dates. To-do indices and positions start at zero. They do
not gate publication.

A post requires a nonempty title/description, a verified image and a notebook with
nonempty Markdown/code/raw cell content. A collection requires both descriptions,
a cover and at least one published member. These local collection requirements
resolve the earlier proposal for this implementation. Publication changes
eligibility only and never publishes member posts or deploys the website.
Images may be PNG, JPEG, WebP or GIF, at most 20 MiB; format and bytes are checked.
Thumbnail and cover inputs are copied into `content/images/` from their supplied
paths, so no manual relocation is needed. The copied bytes are unchanged, and
the source file is left in place. Notebook figures additionally support SVG.

## Sync and build

```sh
uv run at cms sync --preview    # Include drafts, without rendering
uv run at cms sync              # Published content only, without rendering
make preview                   # Sync drafts, then Quarto preview on port 4200
make preview PORT=4300
make build                     # Sync published content, then Quarto render
```

Sync creates copies in `frontend/posts/` and injects title, description, creation
date, modified date, categories, image, draft status and TOC options. It preserves
notebook cells, outputs, attachments and cell options without appending navigation
links. Managed figure links are rewritten to
`frontend/assets/cms/post/`, copying only images referenced by selected posts.
Canonical notebook links keep working relative to `content/`. Notebook-relative
sidecars are copied; keep only public supporting assets next to the notebook. YAML/Markdown records
and hidden files are excluded from sidecar copies. Public collection contents
filter out drafts. Preview includes them. Public validation failures leave
the previous generated files intact. Quarto always receives `--no-execute`.

Before launching Quarto's site render or preview server, the CMS renders the
résumé PDF with Quarto's bundled Typst engine. It uses the same saved-content
snapshot as the web page, staged under `.atlas/cms/`, and atomically replaces
`frontend/assets/resume.pdf` only on success. The site then copies that fresh
download into `_site/assets/` or `_site-preview/assets/`. PDF failures stop the
command and preserve the previous download. No separate LaTeX install is needed.

Notebook, collection and résumé-entry edits outside the CLI are observed by
SHA-256 at explicit sync/build. The first observation advances the corresponding
record's public modification date in UTC;
subsequent unchanged syncs do not. The source notebook is never rewritten during
sync, and editable YAML files retain their exact bytes and comments. This records observation time rather than inventing an edit history from
filesystem modification time. Code-directory edits do not change post dates.

The preview server watches generated files. After editing source content during
a running preview, run `at cms sync --preview` in another terminal, or restart
`make preview`, to project the changes. Sync alone does not render the PDF; restart
`make preview` to refresh the download too.

## Revisions and failures

`show`, creation and edits return JSON with the logical record and SHA-256 revision
of its backend YAML bytes and, for collections and résumé entries, its editable
source bytes. Lists use a table by default; `at cms --json ... ls` returns JSON.
Mutation commands accept `--expected-revision HASH`. Editor-based writes capture
the loaded revision automatically and also compare notebook bytes, rejecting
stale writes without retrying. Entered text is preserved under `.atlas/cms/edits/`
after a rejected save. Unchanged saves keep dates and revisions unchanged.

Supported writers use a POSIX advisory lock, staged atomic file replacement and
an ignored recovery journal for related files. An interrupted save is completed
on the next command; divergent external edits stop recovery and retain the
journal for repair. Direct IDE saves do not participate in the lock, so avoid
simultaneous saves to the same source. Unknown/duplicate fields are rejected
without rewriting the file. Post/collection deletion, undo, remote deployment
and frozen release management are outside this CLI's current scope.

Exit codes: `0` success, `1` readiness diagnostics from `check` or cell errors from
`notebook run`, `2` invalid input,
format or I/O failure, `3` revision/recovery conflict, `4` unknown record. Quarto's
exit status is propagated by `build` and `preview`.
