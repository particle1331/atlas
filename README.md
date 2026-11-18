# Atlas

Atlas provides the `at` CLI for content authoring and a local secret vault, and
currently targets macOS. The CMS manages posts, collections and résumé entries.
The vault uses the system keyring; secret names and values are shared across
projects for the current operating system user.

This README covers setup, user workflows and site behavior.
[AGENTS.md](AGENTS.md) contains working rules for agents editing this repository.

```sh
uv sync
uv run at --help
```

Run `make doctor` to check the vault entries and run pytest with line and branch
coverage. The report includes uncovered line numbers. Both checks run, and the
command fails if either check fails.

## Content CMS and Quarto frontend

Install [Quarto](https://quarto.org/docs/get-started/) separately from the Python
dependencies. Editable sources live in `content/`; CLI-managed records live in
`backend/`. The build generates the Quarto copies. Start with
`uv run at cms --help`; every command also accepts `--help`.

### Source layout

| Where | How to edit |
| --- | --- |
| `content/posts/<id>.ipynb` | Canonical cells, code, outputs, attachments and cell options. Edit in VS Code/Jupyter or use `at notebook`. |
| `content/posts/<id>.yaml` | Authored `title`, `short_description` and `tags`. Edit directly in your editor or through the CMS. |
| `content/collections/<id>.yaml` | Authored `title`, `short_description` and optional `cover_caption`. Edit directly or through the CMS. |
| `content/collections/<id>.md` | Authored collection long description/introduction as ordinary Markdown. Edit directly or with `collection open`. |
| `content/resume.yaml` | Authored résumé `title` and `summary`. |
| `content/resume/<entry-id>.yaml` | Authored entry `title`, `subtitle` and Markdown `body`. |
| `backend/posts/<id>.yaml`, `backend/collections/<id>.yaml`, `backend/resume/<entry-id>.yaml` | CLI-managed IDs, metadata, source paths/digests, dates, publication, membership, ordering, notes and to-dos. |
| `backend/cms.yaml` | CLI-managed storage schema. |
| `content/images/` | Canonical imported images; use CLI image commands to copy and link them. |
| `projects/` | Supporting project code, separate from post notebooks. See [supporting projects](projects/README.md) for versioned source and execution guidance. |
| `frontend/_cms/`, `frontend/index.qmd`, frontend configuration, theme/assets and `_metadata.yml` files | Editable site templates and presentation. |
| `frontend/posts/*.ipynb`, `frontend/collections/*.qmd`, `frontend/{posts,collections,resume}.qmd`, `frontend/assets/cms/` | Ignored generated copies; recreate with CMS sync/build. |
| `frontend/_site/`, `frontend/_site-preview/`, `.atlas/cms/` | Ignored render output and CMS runtime/recovery files. |

Commit both `content/` and `backend/`. Hand edits to notebooks, post metadata,
collections and résumé entries are observed at sync/build and update their
public modification dates. The authored files are never rewritten by a build.
Keep only public supporting assets beside notebooks: sync copies notebook-relative
sidecars into the frontend.

### Workspace and record IDs

Run commands from the repository root with `uv run at ...`. On a new workspace,
run `uv run at cms init` once to import the frontend scaffold; `--empty` skips
sample import. For an existing schema 3 or 4 workspace, run `uv run at cms init`
once to upgrade the content layout. This moves post titles, descriptions and
tags into `content/posts/<id>.yaml` where needed, and extracts collection long
descriptions from YAML into `content/collections/<id>.md`. The upgrade preserves
IDs, notebook paths, authored values, dates and publication state, and refuses
to overwrite existing destination files. Repeated initialization after the
upgrade is a no-op. To select another workspace, put `--root /path/to/workspace`
immediately after `cms` or `notebook`. The default
root is this checkout regardless of the shell's current directory.

CMS commands take an exact ID, and `uv run at cms id <query>` resolves a typed
prefix or stem to that exact ID. A bare `query` matches `post/query*`,
`collection/query*` and `resume/query*`; `post/query` searches only post IDs.
Existing exact IDs are returned directly. Ambiguous queries fail and list the
matching IDs; unknown values and unrecognized kind prefixes exit with status 4.
Resolution takes the CMS lock and recovers interrupted saves before matching.
Notebook commands also accept a unique source stem or title; prefer exact IDs
in scripts.

Get IDs from `new`, `ls` or `show`; collisions can produce suffixed IDs. Changing
a title preserves the immutable ID and source filename. `post show` and
`collection show` also report the record's site `url_path`, such as
`/posts/understanding-attention.html`; résumé entries have no site page.
Use `uv run at cms --json post ls` for JSON lists.

### Posts

```sh
uv run at cms post new "Understanding Attention" --tags "python,transformers"
uv run at cms open post/understanding-attention
# Edit title, short_description and tags in content/posts/understanding-attention.yaml.
uv run at cms post ls
uv run at cms id understanding-attention  # -> post/understanding-attention
uv run at cms post show post/understanding-attention
uv run at cms post edit post/understanding-attention  # Prompt for listing fields
uv run at cms post edit post/understanding-attention --description "How attention works"

# Inspect headings and edit cells with the notebook commands below.
uv run at notebook outline post/understanding-attention
uv run at notebook cat post/understanding-attention --index 0

uv run at cms post edit post/understanding-attention --thumbnail /path/to/image.png
uv run at cms post publish post/understanding-attention
uv run at cms post draft post/understanding-attention
uv run at cms post rm post/understanding-attention --yes
```

A new post starts as a draft with an empty notebook and a matching YAML file.
Creating it automatically refreshes the [draft preview](#preview-and-build).
`cms open` takes an exact post ID and opens its source notebook and editable
`content/posts/<id>.yaml` in VS Code. It requires `code` on `PATH`.

Edit the YAML directly in VS Code or another editor; no CLI command is needed
to save these fields:

```yaml
title: Understanding Attention
short_description: Notes on how attention weights are computed.
tags:
  - python
  - transformers
```

These are the only three fields in the post YAML. Use `tags: []` to clear tags
and `short_description: ''` for a draft without a description. Tags must be a
list of nonempty text labels without commas or line breaks; surrounding spaces
and repeated tags are normalized when read without rewriting the file. Keep
text values as strings (quote values such as `123` or `true`). Reads use saved
edits immediately. Sync/build validates the YAML, updates the backend metadata
digest and public modification date, and uses the fields in post pages,
listings and collection contents. It preserves the authored YAML, including
comments and formatting. Invalid or missing YAML stops the operation without
replacing the file or the existing generated pages.

Keep both source filenames when changing a title. IDs, publication settings,
thumbnail, code path, related-post IDs, dates, notes and to-dos remain in
`backend/` and are managed through the CMS. The optional `post edit` command
writes title, description and tag changes to the same authored YAML.

A published post needs a description, verified thumbnail and notebook content;
publishing makes it eligible for a build and does not deploy anything. `rm`
deletes the record and its notebook and metadata YAML, detaches the post from
collections and related-post lists, and keeps managed images in `content/images/`. It prompts
unless `--yes` is used.

Repeat `--related` to set ordered related-post IDs; `--clear-related` clears
them. CLI `--tags` values are comma-separated; `--tags ""` clears them.

Each post owns one notebook source path; sharing a source path is invalid.
`check` and both sync modes reject duplicate ownership across drafts and
published posts. `post rm` rejects a conflicting source before changing files.

See [Images](#images) for importing and replacing figures, thumbnails and covers.

### Notebook tools

Notebook navigation and cell operations are separate from CMS record editing.
`outline` reads headings from the Markdown cells inside a post's source `.ipynb`.
It includes headings inside lists and blockquotes and skips code cells, code
blocks, HTML blocks and comments. Website TOC visibility and depth are configured
globally under `format.html` in `frontend/_quarto.yml` with `toc: true` and
`toc-depth: 3`.

```sh
uv run at notebook map
uv run at notebook find "attention weights"
uv run at notebook outline post/understanding-attention
uv run at notebook count post/understanding-attention
uv run at notebook cat post/understanding-attention --index 0:4 --context 1
uv run at notebook cat post/understanding-attention --with-revision
uv run at notebook cat post/understanding-attention --label fig-attention
uv run at notebook cat post/understanding-attention --tag hide-input

uv run at notebook edit-cell post/understanding-attention --index 0
uv run at notebook append-cell post/understanding-attention --type code
uv run at notebook insert-cell post/understanding-attention --before 2 --content "## Results"
uv run at notebook remove-cell post/understanding-attention --index 3
uv run at notebook tag post/understanding-attention --index 1 --add hide-input
```

`outline` prints JSON with the post `id`, notebook `revision`, and a `headings`
list. Each heading has `text`, `level` (1–6), a zero-based `cell_index`, and a
one-based `line` within that cell. Use `cell_index` with `cat --index` or
`edit-cell --index`. Re-run the outline after inserting or removing cells.
Its `revision` token can be passed to notebook mutations as `--expected-revision`.

`find` searches cell source, excluding outputs. `cat` prints cell source without
notebook JSON and filters by index/range, tag or Quarto label. `--index` accepts
Python slices and negative indices. Source is truncated at 4096 characters per
cell by default; use `--offset`/`--limit` to page or `--limit 0` for full source.
Add `--with-outputs` when stored outputs matter.

Notebook edits accept `--content`, `--file PATH` or `--file -` for stdin.
Without explicit input, they read piped stdin or open `$VISUAL`/`$EDITOR`.
A quoted heredoc avoids shell expansion in multiline source:

```sh
uv run at notebook edit-cell post/understanding-attention --index 0 --file - <<'EOF'
## Attention

Write the replacement cell source here.
EOF
```

Cell source is limited to 20,000 characters. `edit-cell` replaces the entire
selected source and preserves metadata, attachments and stored outputs. Keep
Quarto options and labels in the replacement text. A unique `--label` or `--tag`
can locate a cell across index changes. `remove-cell --tag` removes every
matching cell.

Source notebooks contain ordinary cells. The CMS supplies document metadata
during sync, and Quarto supplies the TOC; no front matter, planning cells or
generated navigation/contents lists are required. Use
`uv run at notebook <command> --help` for command options.

### Saved execution

```sh
uv run at notebook output post/understanding-attention --index 8
uv run at notebook kernels
uv run at notebook run post/understanding-attention --index 8 --kernel python3 --timeout 300
uv run at notebook clear-outputs post/understanding-attention --from 4
uv run at notebook diff post/understanding-attention --base HEAD
```

`run` explicitly executes code; editing and site builds never run it. With
`--index N`, it executes the prefix in a fresh kernel but saves outputs only for
the selected cell. Omit `--index` to run the whole notebook. Code errors are
saved and produce exit status 1. Execution conflicts preserve results in
`.atlas/cms/execution-conflicts/`.

`output` reads stored outputs and extracts embedded images under
`.atlas/cms/notebook-output/`. `clear-outputs` clears outputs for a locator or
from `--from N`; omitting both clears every code cell's output.

### PDF tools

```sh
uv run at pdf info ~/Downloads/some-book.pdf
uv run at pdf outline ~/Downloads/some-book.pdf
uv run at pdf read ~/Downloads/some-book.pdf --pages 25-53
uv run at pdf find ~/Downloads/some-book.pdf "handoff" --pages 54-72
```

Read local PDFs without leaving the terminal. `info` prints page count, title,
author and bookmark count; `outline` prints the bookmark tree with one-based
PDF page numbers; `read` prints extracted text for a page range; `find`
searches text case-insensitively and prints matching lines with page numbers.
Page ranges accept `25-53`, a single page `25`, `25-` (to the end) and `-25`
(from the start), always as one-based positions in the file. `~` in paths is
expanded. Text extraction uses pdfminer.six; structure and metadata use pypdf.
PDF page numbers can differ from printed page numbers when a document has
unlabeled front matter.

### Images

```sh
uv run at notebook figure post/understanding-attention ~/Desktop/plot.png
uv run at notebook figure post/understanding-attention ~/Desktop/plot.svg --index 2 --caption "Attention weights" --alt "A heatmap of attention weights."
uv run at notebook figure post/understanding-attention ~/Desktop/updated-plot.svg --replace --label fig-attention
uv run at cms post edit post/understanding-attention --thumbnail ~/Desktop/thumbnail.png
uv run at cms collection edit collection/transformers-from-scratch --cover ~/Desktop/cover.png
```

Input paths can point anywhere, including your Desktop. The CLI copies the
original image bytes into `content/images/` and leaves the input file in place;
you can move or delete the input file afterward. Thumbnails and covers accept
verified PNG, JPEG (`.jpg`/`.jpeg`), WebP or GIF up to 20 MiB; notebook figures
additionally accept SVG.

`figure <notebook> <image-path>` copies the image into
`content/images/post/<post-id>-<uuid>.<ext>` and inserts a Markdown figure cell.
It appends by default; `--index 0` inserts before the first cell. Optional
`--caption` and `--alt` set the caption and accessible description.

To change an existing figure's image, add `--replace --index N`, or
`--replace --label fig-...`. Only the image link changes; your edited caption,
figure ID, alt text, sizing and other cell content are preserved. The new input
is copied into managed storage, including when its format differs from the old
image. Replacement requires exactly one of `--index` or `--label`; omit
`--caption`/`--alt` to preserve them. Use the returned `fig-...` label for later
replacement, and keep existing managed copies that may still have references.
Replace thumbnails with `post edit --thumbnail PATH` and collection covers with
`collection edit --cover PATH`. Replacing a cover preserves its caption.

### Collections

```sh
uv run at cms collection new "Transformers from Scratch"
uv run at cms open collection/transformers-from-scratch
uv run at cms collection ls
uv run at cms collection edit collection/transformers-from-scratch --description "A reading sequence"
uv run at cms collection edit collection/transformers-from-scratch --cover /path/to/cover.png
uv run at cms collection edit collection/transformers-from-scratch --cover-caption '*Cover title* by Artist'
uv run at cms collection open collection/transformers-from-scratch
uv run at cms collection add collection/transformers-from-scratch post/understanding-attention
uv run at cms collection move collection/transformers-from-scratch post/understanding-attention --position 0
uv run at cms collection remove collection/transformers-from-scratch post/understanding-attention
uv run at cms collection show collection/transformers-from-scratch
uv run at cms collection rm collection/transformers-from-scratch --yes
```

New collections start as drafts with metadata YAML and an empty Markdown file.
Creating one automatically refreshes the [draft preview](#preview-and-build).
`cms open` takes an exact collection ID and opens both files in VS Code.
The YAML contains `title`, `short_description` and optional `cover_caption`;
the matching `.md` file contains the long description/introduction as ordinary
Markdown, without required front matter or a `long_description:` wrapper. Edit
either file directly in your editor without a CLI save step. Saved edits are
read immediately and reach generated pages on the next sync/build, which
preserves both files' comments and formatting. Both sources participate in
revision checks and public modification dates; missing files or invalid YAML
stop the operation without replacing authored files or existing generated pages.
Keep both filenames when changing the collection title.

`collection open` edits the Markdown introduction; the ordered contents table is
generated from post IDs and shows each member's position, title, short description
and last modified date. Positions start at zero; adding
without `--position` appends. Removing membership preserves the post. `publish`
requires descriptions, a cover and at least one published member; `draft` returns
the collection to draft. `rm` deletes the collection record, metadata YAML and
Markdown introduction but leaves its member posts and managed images untouched. Collection changes never
publish or delete the member posts; after deleting a member post, `check` may
report a published collection that no longer has a published member.
`--cover-caption` adds a Markdown caption beneath the cover on the collection
page. Edit `cover_caption` in the collection YAML or pass `--cover-caption ""`
to clear it. Replacing the image preserves the caption.

### Résumé

```sh
uv run at cms resume ls
uv run at cms resume ls --section employment
uv run at cms resume show resume/employment-sr-machine-learning-engineer-afni
uv run at cms resume open resume/employment-sr-machine-learning-engineer-afni
uv run at cms resume edit resume/employment-sr-machine-learning-engineer-afni --subtitle "Jan 2025 -- Present"
uv run at cms resume add "Engineer at Example" --section employment --subtitle "2026 -- Present"
uv run at cms resume move resume/engineer-at-example --position 0
uv run at cms resume rm resume/engineer-at-example --yes
uv run at cms resume profile --summary "My updated opening summary."
```

Sections are `employment`, `skills`, `education` and `projects`. Editable titles,
subtitles and bodies live in `content/resume/`. Section assignments and zero-based
order live in `backend/resume/`; the CLI generates the section/page structure.
`make preview` and `make build` refresh the downloadable PDF when its inputs
change, using the same saved résumé title, summary and ordered entries as the site.
See [Résumé PDF](#résumé-pdf) for layout, fonts and caching.

### Writing, notes and storage

`collection open` and `resume open` edit the selected body through
`$VISUAL`/`$EDITOR`. Use `--file PATH` or `--file -` for file/stdin input.
`notes` also accepts `--file`. Metadata `edit`
commands can prompt if no field flags are supplied. Supply explicit inputs for
noninteractive work.

```sh
uv run at cms notes post/understanding-attention
uv run at cms todos post/understanding-attention --add "Add a worked example"
uv run at cms todos post/understanding-attention --index 0 --done
uv run at cms check
```

Notes and to-dos work on posts and collections. They remain private to the
authoring source, do not change public modification dates and do not gate
publication. To-dos support `--index N --done`, `--text`, `--position` and
`--remove`. `check` reports invalid references and publication blockers.

#### Revisions

When saving changes based on an earlier read, pass `--expected-revision` to
reject stale writes. CMS mutations use the record revision returned by `show`;
notebook mutations use the `notebook:<hash>` token from `cat --with-revision` or
`outline`. These tokens are different. Refresh the relevant token after each
mutation.

On a stale-write conflict, re-read the current record/cells and reconcile the
edit. Failed editor input is preserved in `.atlas/cms/edits/`; keep it available.
Do not bypass conflicts by dropping revision checks or deleting recovery files.
Avoid simultaneous CLI and IDE saves to the same source.

### Preview and build

```sh
make preview                  # Live preview at http://localhost:4200
make preview PORT=4300        # Use a different port
make build                    # Render frontend/_site/
uv run at cms build --preview  # Render frontend/_site-preview/ once
uv run at cms sync --preview   # Regenerate draft copies without rendering
uv run at cms sync             # Regenerate published copies without rendering
```

Builds and live preview first sync source notebooks with title, description,
dates, categories and publication metadata into `frontend/posts/*.ipynb`.
Quarto applies the global TOC settings when rendering. Atlas generates
collection contents and post links from ordered IDs and builds the résumé
from its YAML entries.
These projections are gitignored. Private notes, to-dos and revision data stay out
of the frontend. Builds never write back to or execute source notebooks.

Preview includes drafts in `frontend/_site-preview/`; public builds include only
published content in `frontend/_site/`. The existing 11 stub posts, 3 collections
and 12 résumé entries have been imported. Incomplete samples are drafts until
their publication requirements are met. `uv run at cms check` reports references
and publication blockers for drafts as well as published records; exit status 1
can be expected for unfinished drafts.

`post new` and `collection new` save the draft and automatically refresh its
page and listing in `frontend/_site-preview/`. When live preview is running,
its watcher handles the refresh. Otherwise the creation command renders the
draft site once. If Quarto is unavailable or the render fails, the command
still returns the saved draft and reports the preview problem. Use
`uv run at cms build --preview` to retry the render after fixing it.

Keep `make preview` running while editing. It watches `content/` and `backend/`
(including notebook sidecars, metadata and CMS record changes), debounces saves,
and automatically syncs the frontend. Only changed projections are written, so
Quarto can incrementally render affected pages and reload the browser rather than
rebuilding the whole site. When pages are added or removed, Atlas restarts
Quarto at the same preview URL so it can render the updated page list.

Individual posts use a 792 px desktop body grid set in
`frontend/posts/_metadata.yml`. Page titles and section headings are left-aligned;
body paragraphs retain their existing alignment. HTML post tables use
`tbl-colwidths: false` so the browser sizes columns from their content rather than
applying Markdown-derived width hints. The posts listing sets its own grid in
`frontend/_cms/posts.qmd` to fit the table and right-hand filters. The
posts-only table styles in `frontend/assets/styles.css` give the title and
description columns a 3:5 width ratio.
The right-hand listing sidebar shows date filters before categories.
Collection contents tables reserve 18% of their width for the last modified
date, with 34% for titles and 46% for short descriptions.

Résumé edits also refresh the downloadable PDF; unchanged PDF inputs reuse the
cached download. CMS templates under `frontend/_cms/` and bundled fonts are watched
as well. Invalid intermediate saves report an error without stopping preview;
fix the source and save again to retry. Hidden files and notebook checkpoints are
ignored. Builds and preview never execute notebook code. Press Ctrl-C to stop.

#### Résumé PDF

`frontend/_cms/resume-pdf.qmd` and `frontend/_cms/resume-pdf/` control
the PDF layout and contact links; its title, summary and entries come from the
same YAML sources as the web page.

The A4 PDF uses the Ubuntu name font, bundled Latin Modern Sans body fonts,
orange bullets and right-aligned dates. Set
`resume-pdf-main-roles` in the PDF template to choose how many employment entries
appear before the page break (default: four); remaining roles appear under Early
Employment after education. The web page retains the CMS section order.
PDF subtitles use generated `.resume-subtitle` divs for the layout filter.

Body fonts and licenses are bundled under `frontend/_cms/resume-pdf/fonts/`.
The isolated render stages the PDF support directory and
`frontend/assets/fonts/`, so it needs no system font installation. Preview and
build render it with Quarto's bundled Typst engine before Quarto copies assets
into the site output. No separate LaTeX installation is needed. No build reads
the Watchtower checkout.

Unchanged content, PDF layout/support files and fonts reuse
`frontend/assets/resume.pdf` without rewriting it, avoiding PDF timestamp
changes in Git. The ignored
`.atlas/cms/resume-pdf.cache.yaml` records input and output hashes; a missing
cache, missing/changed PDF or changed renderer triggers a fresh render.
A failed PDF render stops the command and preserves the previous download.

## Vault

```sh
# Create or replace a secret; prompts for a hidden value and confirmation.
uv run at vault set API_TOKEN

# Read a value from stdin; removes one trailing line ending.
uv run at vault set API_TOKEN --stdin < /path/to/token

# Copy the value when running interactively; write it to stdout when piped.
uv run at vault get API_TOKEN

# Delete the local value; prompts for confirmation.
uv run at vault rm API_TOKEN

# Delete without prompting, including in scripts.
uv run at vault rm API_TOKEN --yes  # or -y

# Check the names declared in the Atlas repository root's .env.example.
uv run at vault check
```

Declare expected names in the Atlas repository root's `.env.example`, for example:

```dotenv
# Required secrets
API_TOKEN=
DATABASE_URL=
```

Use one `NAME=` entry per line with an empty value. Blank lines and full-line `#`
comments (including indented comments) are skipped. `export` declarations, inline
comments, quoted values, and multiline values are not supported. Duplicate names
are checked separately. The path is fixed by Atlas's project root; it does not
depend on the current directory and has no override option.

`check` reports `[ok]` for each stored name and `[no]` for each missing name,
followed by a missing-count summary if needed. It does not print stored values.
The manifest must exist; a missing file raises `FileNotFoundError` and exits with
code `1`. A manifest containing only blank lines or comments, or an empty manifest,
succeeds and reports `No secrets declared.`

`set` requires a terminal for hidden input unless `--stdin` is used. Empty secret
values are rejected. `rm` requires a terminal for confirmation unless `--yes`
or `-y` is used.

`get` copies a secret to the clipboard when stdout is a terminal. When stdout is
redirected or piped, it writes the stored value to stdout without adding a newline.

In Python, import the vault reader and pass its return value directly to the
client that needs it.

```python
from atlas.vault import get_secret

api_key = get_secret("API_TOKEN")
```

`get_secret` returns the value silently, returns `None` when the entry is absent,
and raises `atlas.vault.VaultError` on keyring failure.

Vault commands leave `.env.example` unchanged. Deleting a value makes its name
appear as missing on the next check. Remove a name from `.env.example` when the
project stops requiring it.

Exit codes are `0` for success (including cancelled deletion), `1` for missing
secrets or a missing manifest, and `2` for invalid manifest entries, input errors,
or keyring/clipboard errors.
Python keyring chooses the credential backend; unavailable or disabled backends
produce an error. Run `uv run keyring diagnose` to inspect backend configuration.

Vault commands write a local audit log to `.atlas/logs/vault.jsonl` in the Atlas
repository root. This directory, including lock and temporary files, is gitignored.
Each JSON line records a UTC timestamp, operation, targeted secret names, outcome
(`success`, `failure`, or `cancelled`), exit code, and process ID. Set the optional
`ATLAS_VAULT_SESSION_ID` environment variable to attach a self-reported session
label (limited to 256 characters). Secret values, stdin, and exception messages
are never recorded.

Only records within the last 30 days are kept. Expired records are removed when
each command starts and finishes; there is no background cleanup while Vault is
idle. Malformed, undated, or future-dated records are discarded during cleanup.
New log files are created with owner-only permissions, and concurrent commands
serialize updates. A logging failure emits a sanitized warning to stderr without
changing the command result. These logs cover calls through Vault, not direct
keyring access, and are not protected against changes by the same OS user.

## Other stuff, utilities 

### OpenCode

Project-local agents, commands and configuration checks are documented in
[.opencode/README.md](.opencode/README.md). Agent definitions live in
`.opencode/agents/`.

From the repository root, inspect the resolved agent models and reasoning
variants (requires `jq`):

```sh
opencode debug agents | jq '.[] | select(.model) | {agent: .id, model: .model}'
```

OpenCode reports the model ID and reasoning `variant` as separate JSON fields;
filtering with `grep gpt` hides the variant.

### Commands

Project slash commands live in `.opencode/commands/` and run inside OpenCode.

| Command | Purpose |
| --- | --- |
| `/commit` | Review changes, group related work and create local Conventional Commits. Does not push or rewrite history. |
| [`/quiz`](.opencode/README.md#technical-mock-assessments) | Run a technical mock assessment on an Atlas post or collection. |
| `/reload` | Force a configuration refresh after editing agents or commands. |

Pass optional guidance after `/commit`:

```text
/commit keep the content updates separate from tooling changes
```

For commit safeguards, model selection and review-only usage, see the
[command documentation](.opencode/README.md#local-commits).

## Git hooks

Install the pre-commit tool and enable the repository hook once per clone:

```sh
uv tool install pre-commit
pre-commit install
```

Before each commit, the hook scans staged files for likely secrets with
`detect-secrets`. To scan all tracked files manually, use
`pre-commit run --all-files`. Run `uv run at vault check` to check vault entries.
