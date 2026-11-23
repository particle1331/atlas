# Atlas

Atlas provides the `at` CLI for authoring and managing posts, collections and
résumé entries.

This README covers setup, user workflows and site behavior.
[AGENTS.md](AGENTS.md) contains working rules for agents editing this repository.

## Local development with Docker Sandboxes

**We use Docker Sandboxes for local development.** Run the setup and development
commands below inside your sandbox unless a step says to run it on the host.

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and
[Gitleaks](https://github.com/gitleaks/gitleaks) (`brew install gitleaks` on macOS).
Run this from the repository root:

```sh
make init
```

`make init` enables the [secret-scanning Git hook](#secret-scanning) in this
clone and installs the locked Python dependencies. It confirms that the hook is
enabled; the scan runs when you commit, not during setup. Cloning does not enable
hooks from the cloned repository or copy its local Git configuration.

Run `make doctor` to [scan the local workspace for secrets](#secret-scanning),
including Git-ignored files, and run pytest with line and branch coverage.
Both checks run, and the command fails if either check fails.

### Sandbox Python environment

When your sandbox shares the Atlas checkout with a Mac, keep the sandbox's
Linux virtual environment outside the checkout. Otherwise, `uv` uses `.venv`
on both sides, and the two environments are not interchangeable.

On Linux, including Docker Sandboxes, `make init` uses
`~/.local/share/atlas/venv`. If `/etc/sandbox-persistent.sh` exists and is
writable, it adds the export unless the line is already there. New sandbox
shells pick it up automatically; in your current shell, run
`. /etc/sandbox-persistent.sh`. If the file is missing or read-only,
`make init` prints the command to run before using `uv`:

```sh
export UV_PROJECT_ENVIRONMENT="$HOME/.local/share/atlas/venv"
```

After recreating a sandbox, run `make init` again.

**On your Mac**, leave the variable unset so `uv` uses `.venv`. Leave a working
`.venv` as is. If the sandbox already replaced it with a Linux environment,
delete only that broken `.venv` and run `uv sync --locked` from the Atlas root
on your Mac to recreate it.

### Connect VS Code to the sandbox over SSH

On the host, sign in to Docker Sandboxes and install the
[Remote - SSH extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-ssh)
in VS Code. Then run these commands on the host:

```sh
sbx setup ssh
sbx ls
ssh opencode-atlas.sbx
```

Use the name of your existing sandbox from `sbx ls` in place of `opencode-atlas`.
`sbx setup ssh` configures the host's SSH client. The Docker Sandboxes daemon
handles the connection locally, so you don't need to install `sshd`, publish a
port, or create an SSH key.

Once terminal SSH works, run **Remote-SSH: Connect to Host...** from the VS Code
Command Palette and type `opencode-atlas.sbx` (or your `<sandbox-name>.sbx`)
manually; it may not appear in the host picker. The first connection installs
VS Code Server in the sandbox. Use **File → Open Folder** to open the Atlas
checkout inside the sandbox, not the default `/home/agent` folder. For notebooks,
select the [sandbox Python kernel](#vs-code-notebook-kernel).

If VS Code gets stuck reconnecting on macOS, set `remote.SSH.useLocalServer`
to `false` in your local VS Code user settings. See
[Docker's VS Code SSH guide](https://docs.docker.com/ai/sandboxes/integrations/vscode/)
for troubleshooting.

### Global custom secrets

Run `sbx secret set-custom` **on the host** to register a provider API key.
Omit `--sandbox` to set the secret globally, so you can use it across sandboxes
on that host. For example, to enter your DeepSeek key at the prompt:

```sh
sbx secret set-custom --host api.deepseek.com --env DEEPSEEK_API_KEY
```

The command also accepts `--value '<api_key_value>'`, but prefer the prompt:
passing a real value as an argument can expose it in shell history and process
listings.

Inside the sandbox, the notebooks read `DEEPSEEK_API_KEY` from the environment.
It holds a placeholder; the Docker Sandboxes proxy substitutes the real key in
requests to `api.deepseek.com`. If the variable is missing in an existing
sandbox, follow
[Docker's custom secret instructions](https://docs.docker.com/ai/sandboxes/configuration/credentials/#custom-secrets)
to configure the placeholder for future sessions, then reconnect VS Code and
restart the notebook kernel. Keep real keys out of the shared checkout.

If you used the old Atlas vault, register your provider keys with `sbx`.
Atlas does not migrate or delete existing keyring entries; you can remove the
old `atlas.vault` entries from your system keyring once you've verified the new setup.

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

A published post needs a description and notebook content. Thumbnails are
optional and must pass image validation when supplied. Publishing makes the
post eligible for a build and does not deploy anything. `rm`
deletes the record and its notebook and metadata YAML, detaches the post from
collections and related-post lists, and keeps managed images in `content/images/`. It prompts
unless `--yes` is used.

Repeat `--related` to set ordered related-post IDs; `--clear-related` clears
them. CLI `--tags` values are comma-separated; `--tags ""` clears them.

Each post owns one notebook source path; sharing a source path is invalid.
`check` and both sync modes reject duplicate ownership across drafts and
published posts. `post rm` rejects a conflicting source before changing files.

See [Images](#images) for importing and replacing figures, thumbnails and covers.

#### Browse companion source

To add a 📁 `source` link to a post, run
`uv run at cms post edit post/<id> --code-path PATH`. Use an existing project
directory relative to the workspace root, such as `projects/my-project`.

The browser follows the post's publication status and shows eligible files up to
1 MiB committed at `HEAD`, subject to Git ignore rules. Markdown opens as formatted
text with a **View source** link. Code is syntax-highlighted where available.
Notebooks show code, Markdown and saved text or Markdown outputs without running
a kernel. Relative links work for visible files and folders.

The browser does not run its own secret scan. The [Pages build](#deploy-to-github-pages)
checks the repository before generating the site. Local previews and regular
builds do not run that check; review companion source before sharing them.

After committing companion changes or editing a nested ignore or exclude file,
restart `make preview` or run `uv run at cms build --preview` with live preview
stopped.

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

For a dense design table, a fenced div with
`{.column-screen-inset .design-traps-table}` centers a wider table,
capped at 1060px (about one-third wider than the desktop text), rather than
using the full page width. Narrow screens use the normal text column.
Keep any `tbl-colwidths` attribute inside the div with the table.
Mermaid diagram labels are centered without hyphenation, independently of the
justified article prose. Use `<br/>` inside quoted Mermaid labels to break long
text at natural phrases.

### VS Code notebook kernel

Open the Atlas repository root in VS Code with the Python and Jupyter
extensions installed. After `make init` on macOS, open a notebook under
`content/posts/` and choose **Select Kernel → Python Environments**. Select
the interpreter from this checkout's `.venv`.

If VS Code is [connected over SSH](#connect-vs-code-to-the-sandbox-over-ssh) to
the Linux sandbox, use the sandbox interpreter
(`~/.local/share/atlas/venv/bin/python`), not the Mac's `.venv`. If the
interpreter you want is missing from the picker, run the following in the same
environment where VS Code runs Jupyter, from the Atlas root:

```sh
uv run --locked python -m ipykernel install --user --name atlas --display-name "Python (Atlas)"
```

Then choose **Select Kernel → Jupyter Kernel → Python (Atlas)**. This registers
the current Atlas environment for your user; rerun it if the environment moves.
To verify the active kernel, run `import sys; print(sys.executable)` in a
notebook cell and check that the path points to the intended Atlas environment.

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
make preview SOURCES=0        # Skip the project source browser when editing posts
make build                    # Render frontend/_site/
uv run at cms build --preview  # Render frontend/_site-preview/ once
uv run at cms sync --preview   # Regenerate draft copies without rendering
uv run at cms sync             # Regenerate published copies without rendering
```

Preview includes drafts. Public builds include published content. Both refresh
the generated pages from their authored sources without executing notebooks.
`uv run at cms check` reports invalid references and publication blockers,
including blockers for unfinished drafts.

`make preview` watches `content/`, `backend/`, CMS templates and bundled fonts.
If a save reports an error, fix the source and save again. Use
`make preview SOURCES=0` or `uv run at cms preview --no-source-browser` to skip
companion source pages while editing posts. Press Ctrl-C to stop preview.

`post new` and `collection new` save the draft and refresh its preview page and
listing. If rendering fails, the saved draft is available and
`uv run at cms build --preview` retries the render.

#### Deploy to GitHub Pages

Set the publishing source to **GitHub Actions** in the repository's **Settings → Pages**.
The [Pages workflow](.github/workflows/pages.yml) runs on pushes to `master` and
can also be started from the Actions tab on that branch. It installs a pinned
Gitleaks release and runs `make build-pages`. The target requires `frontend/_site/`
to be absent and runs the publication regression tests before building the site.
GitHub Pages deploys the verified `frontend/_site/` artifact.

Run `make build-pages` locally from a fresh checkout with Quarto and Gitleaks on
`PATH`. The target uses `at cms build --for-pages`, which runs the
[repository secret scan](#secret-scanning) before rendering. It then scans the
rendered paths and UTF-8 contents before upload. It also rejects hidden or
unrendered source files, links, Git-ignored frontend assets, and browser pages
without a current CMS projection. Draft preview output stays outside the artifact.

#### Résumé PDF

Preview and build update the downloadable résumé using Quarto's bundled Typst
engine. The PDF and web page share the same YAML sources. Edit the PDF layout
and contact links in `frontend/_cms/resume-pdf.qmd` and
`frontend/_cms/resume-pdf/`. Set `resume-pdf-main-roles` in the template to choose
how many employment entries appear before the page break. The default is four.

If PDF rendering fails, the command stops and preserves the previous download.

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

## Secret scanning

With Gitleaks on `PATH` (Pages uses 8.30.1), run the same source check used by the
Pages build, without rendering:

```sh
uv run --locked at cms scan-secrets
```

The scan checks all tracked files, including those that now match an ignore rule,
and untracked files not ignored by Git. It checks paths and UTF-8 contents,
including raw notebooks and the decoded cell source and saved text outputs shown
by the companion browser. It also checks the index and `HEAD` when they differ
from the working tree. It does not audit earlier commits or binary contents.

`make doctor` also audits the workspace on disk, including Git-ignored files
such as local `.env` files, generated output, and dependencies. To run just
that scan:

```sh
uv run --locked at cms scan-secrets --workspace
```

This local scan checks file paths and UTF-8 text (including decoded notebook
cells and saved text outputs), plus symlink names and link text without following
links. It skips `.git` metadata and special files and does not inspect binary
contents or unpack archives. It scans only the selected workspace, not the
entire machine, Git index, or commit history. Findings can include fixtures and
dependency examples; the report shows paths and rule IDs, not matched values.
This scan does not change what agents can read.

To scan a different directory, use
`uv run --locked at cms --root /path/to/audit scan-secrets --workspace`.

Rules recognize provider token formats, quoted password assignments, and
likely literal passwords in unquoted uppercase environment assignments. The
unquoted rule skips simple variable references and the two exact Redis
assignments used as example placeholders. A bare random string, Base64 value,
or hex value may be indistinguishable from ordinary data; a clean scan does not
prove that no secrets are present.

`make init` configures the native Git hook with
`git config --local core.hooksPath .githooks`. No `pre-commit` package is needed.
If a different hooks path or executable hooks already exist, setup stops rather
than bypassing them. To keep that setup, add the staged scan command below to
your existing pre-commit hook (or create one in that directory) and run
`uv sync --locked` separately. On Linux, use the
[sandbox Python environment](#sandbox-python-environment) for both commands.

The hook runs `uv run --locked at cms scan-secrets --staged` over the full index,
not just changed lines. This checks what the next commit would contain without
blocking a cleanup commit over a secret present only in `HEAD`.

Pages CI runs after a push: it can block publication, not prevent a credential
from reaching the remote. Enable GitHub secret scanning and push protection if
available. Revoke or rotate any real credential that has been committed, even
if a later commit removes it.
