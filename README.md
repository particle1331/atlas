# Atlas

Atlas provides the `at` CLI for content authoring and a local secret vault, and
currently targets macOS. The CMS manages posts, collections and résumé entries.
The vault uses the system keyring; secret names and values are shared across
projects for the current operating system user.

See [AGENTS.md](AGENTS.md) for agent workflows for navigating, authoring and editing content.

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
`backend/`. The build generates the Quarto copies. Start with `uv run at cms --help`; every command
also accepts `--help`.

| Where | How to edit |
| --- | --- |
| `content/posts/*.ipynb` | Edit normally in VS Code/Jupyter or use `at notebook`. |
| `content/collections/*.yaml` | Edit title, short description and introduction by hand, or use the CMS commands. |
| `content/resume.yaml`, `content/resume/*.yaml` | Edit résumé text by hand, or use the CMS commands. |
| `backend/` | Use the CLI for metadata, membership, ordering, publication, notes and to-dos. |
| Generated posts, collections, listings and résumé under `frontend/` | Recreate with sync/build. |

Commit both `content/` and `backend/`. Hand edits to notebooks and collection or
résumé entries are observed at sync/build and update their public modification
dates. The authored files are never rewritten by a build. Site templates under
`frontend/_cms/`, the landing page, theme and configuration are editable directly.

### Posts

```sh
uv run at cms post new "Understanding Attention" --tags "python,transformers"
# Edit content/posts/understanding-attention.ipynb in VS Code or Jupyter.
uv run at cms post ls
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

A new post starts as a draft with an empty notebook. `edit` handles title,
description, tags, thumbnail, code path and related-post IDs. A published post
needs a description, verified thumbnail and notebook content; publishing makes
it eligible for a build and does not deploy anything. `rm` deletes the record
and its notebook, detaches the post from collections and related-post lists, and
keeps managed images in `content/images/`. It prompts unless `--yes` is used.

Each post owns one notebook source path; sharing a source path is invalid.
`check` and both sync modes reject duplicate ownership across drafts and
published posts. `post rm` rejects a conflicting source before changing files.

Thumbnail and cover paths can point anywhere, including your Desktop. The CLI
copies the original image bytes into `content/images/`; you can move or delete
the input file afterward.

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

uv run at notebook edit-cell post/understanding-attention --index 0
uv run at notebook append-cell post/understanding-attention --type code
uv run at notebook insert-cell post/understanding-attention --before 2 --content "## Results"
uv run at notebook figure post/understanding-attention ~/Desktop/plot.png
uv run at notebook figure post/understanding-attention ~/Desktop/plot.svg --index 2 --caption "Attention weights"
uv run at notebook figure post/understanding-attention ~/Desktop/updated-plot.svg --replace --index 2
uv run at notebook remove-cell post/understanding-attention --index 3
uv run at notebook tag post/understanding-attention --index 1 --add hide-input
uv run at notebook clear-outputs post/understanding-attention --from 4

uv run at notebook output post/understanding-attention --index 8
uv run at notebook run post/understanding-attention --index 8
uv run at notebook diff post/understanding-attention
uv run at notebook kernels
```

`outline` prints JSON with the post `id`, notebook `revision`, and a `headings`
list. Each heading has `text`, `level` (1–6), a zero-based `cell_index`, and a
one-based `line` within that cell. Use `cell_index` with `cat --index` or
`edit-cell --index`. Re-run the outline after inserting or removing cells.
Its `revision` token can be passed to notebook mutations as `--expected-revision`.

`cat` prints cell source without notebook JSON and filters by index/range, tag,
or Quarto label. Long edits open `$VISUAL`/`$EDITOR`, accept `--file`, or read
stdin. Cell edits preserve outputs and metadata; explicitly run code to refresh
saved outputs. `run` is the only notebook command that executes code, and site
renders keep execution disabled. Use `uv run at notebook <command> --help` for
command options.

`figure <notebook> <image-path>` copies the image into
`content/images/post/<post-id>-<uuid>.<ext>` and inserts a Markdown figure cell.
It appends by default; `--index 0` inserts before the first cell. Optional
`--caption` and `--alt` set the caption and accessible description. PNG, JPEG
(`.jpg`/`.jpeg`), SVG, WebP and GIF are supported. The original image stays in place.

To change an existing figure's image, add `--replace --index N`, or
`--replace --label fig-...`. Only the image link changes; your edited caption,
figure ID, alt text, sizing and other cell content are preserved. The new input
is copied into managed storage, including when its format differs from the old
image. Replace thumbnails with `post edit --thumbnail PATH` and collection covers
with `collection edit --cover PATH`.

### Collections

```sh
uv run at cms collection new "Transformers from Scratch"
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

`open` edits the introduction; the ordered contents list is generated from post
IDs. Positions start at zero; adding without `--position` appends. `publish`
requires descriptions, a cover and at least one published member; `draft` returns
the collection to draft. `rm` deletes the collection record and introduction but
leaves its member posts and managed images untouched. Collection changes never
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
`make preview` and `make build` regenerate the downloadable PDF from
the same saved résumé title, summary and ordered entries before rendering the site.

### Writing, notes and storage

`open` edits only the selected body through `$VISUAL`/`$EDITOR`; use `--file PATH`
or `--file -` for file/stdin input. The source notebook contains your editable
cells, outputs and attachments, with no required metadata or navigation cells.
Renaming a title keeps its ID and notebook path.

```sh
uv run at cms notes post/understanding-attention
uv run at cms todos post/understanding-attention --add "Add a worked example"
uv run at cms todos post/understanding-attention --index 0 --done
uv run at cms check
```

Notes and to-dos work on posts and collections. They remain private to the
authoring source and do not change public modification dates. `check` reports
invalid references and publication blockers.

```text
content/posts/<stable-id>.ipynb    # Editable notebook
content/collections/<id>.yaml     # Editable title and descriptions
content/resume.yaml               # Editable résumé title and summary
content/resume/<entry-id>.yaml    # Editable title, subtitle and body
content/images/                  # Canonical image assets
backend/posts/<stable-id>.yaml   # CLI-managed listing fields, dates, notes/to-dos
backend/collections/<id>.yaml    # CLI-managed membership, cover, status and dates
backend/resume/<entry-id>.yaml   # CLI-managed section, position and dates
backend/cms.yaml                 # Storage schema
```

### Preview and build

```sh
make preview             # Live preview at http://localhost:4200
make preview PORT=4300    # Use a different port
make build               # Render frontend/_site/
uv run at cms sync --preview  # Regenerate draft copies without rendering
uv run at cms sync            # Regenerate published copies without rendering
```

Both targets first sync source notebooks with title, description, dates, categories
and publication metadata into `frontend/posts/*.ipynb`. Quarto applies the global
TOC settings when rendering. Collection contents and post links are generated
from ordered IDs; the résumé is generated from its YAML entries.
These projections are gitignored. Private notes, to-dos and revision data stay out
of the frontend. Builds never write back to or execute source notebooks.

Preview includes drafts in `frontend/_site-preview/`; public builds include only
published content in `frontend/_site/`. The existing 11 stub posts, 3 collections
and 12 résumé entries have been imported. Incomplete samples are drafts until
their publication requirements are met. Use `at cms check` to see blockers.

The landing page and theme remain under `frontend/`. Listing and résumé templates
live in `frontend/_cms/`; generated listings, posts, collections and résumé pages
are ignored. `frontend/_cms/resume-pdf.qmd` and `frontend/_cms/resume-pdf/` control
the PDF layout and contact links; its title, summary and entries come from the
same YAML sources as the web page. The A4 PDF uses the Ubuntu name font, bundled
Latin Modern Sans body fonts, orange bullets and right-aligned dates. Set
`resume-pdf-main-roles` in the PDF template to choose how many employment entries
appear before the page break; remaining roles appear under Early Employment
after education. This grouping only affects the PDF. Its generated subtitles
use `.resume-subtitle` divs for the layout filter. The isolated render stages
the PDF support directory and `frontend/assets/fonts/`, so it needs no system
font installation. Preview and build render it with Quarto's bundled Typst
engine and replace `frontend/assets/resume.pdf` before Quarto copies assets into
the site output.
A failed PDF render stops the command and preserves the previous download.
No separate LaTeX installation is needed. No build reads the Watchtower checkout.

During a running preview, run `uv run at cms sync --preview` after source edits
to refresh the generated copies, or restart `make preview`. Sync alone does not
render the PDF; restart `make preview` to refresh the download as well.

See [Posts](#posts), [Collections](#collections) and
[Writing, notes and storage](#writing-notes-and-storage) for publication,
ordering, concurrency and the complete authoring workflow. On a new workspace, run
`uv run at cms init` once to import the frontend scaffold. Repeated initialization
of the same workspace is a no-op.
Use `at cms --json post ls` for JSON lists and `--expected-revision HASH` on edits
to reject stale writes. `at cms --root /path/to/workspace ...` selects another
workspace explicitly.

## Git hooks

Install the pre-commit tool and enable the repository hook once per clone:

```sh
uv tool install pre-commit
pre-commit install
```

Before each commit, the hook scans staged files for likely secrets with
`detect-secrets`. To scan all tracked files manually, use
`pre-commit run --all-files`. Run `uv run at vault check` to check vault entries.

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
