# Working in Atlas

Atlas is a notebook-first CMS with a Quarto website. Run CLI commands from the
repository root with `uv run at ...`. Use [README.md](README.md#content-cms-and-quarto-frontend)
for workflows and examples, and CLI `--help` for syntax and matching rules.
Update the relevant documentation when behavior changes.
Use `at pdf` to inspect local PDFs. See the [PDF tools](README.md#pdf-tools).

## Repository skills

- Use [atlas-notebooks](.agents/skills/atlas-notebooks/SKILL.md) to inspect, edit
  or execute post notebooks and work with their supporting source.
- Use [atlas-cms](.agents/skills/atlas-cms/SKILL.md) for managed content, images,
  publication, sync and preview.
- Use [atlas-writing](.agents/skills/atlas-writing/SKILL.md) for post, collection
  and résumé prose.

## Source and validation rules

- Edit canonical notebooks through `at notebook`, and use `at cms` for managed
  backend records. Preserve immutable IDs, source filenames on title changes,
  and publication state unless the task requires changing it.
- Edit site templates, configuration, theme assets and `_metadata.yml` under
  `frontend/`. Regenerate projected pages through CMS sync. Treat
  `frontend/_site/`, `frontend/_site-preview/` and `.atlas/cms/` as generated
  output or runtime and recovery files. See the [source layout](README.md#source-layout).
- Pass `--expected-revision` when writing from an earlier read. Refresh the
  token after each mutation. On a conflict, re-read and reconcile the edit
  while keeping revision checks and recovery files in place. See [revisions](README.md#revisions).
- Run `uv run at cms check` for content changes and report relevant diagnostics.
  Use the CMS preview or build when rendering is affected. Re-read edited
  cells or records and inspect `notebook diff` and `git diff` as applicable.
  Run relevant pytest tests for CLI implementation changes. Prose-only edits
  can skip the full `make doctor` checks.
- Run the [repository secret scan](README.md#secret-scanning) before sharing
  changes. Never print suspected credential values.

## Commit command handoff

`/commit` authorizes its child session to stage clear, in-scope changes and
create new local commits. Pushes and history rewrites are outside that scope.
When it returns, relay the actual commit count,
hashes, messages, checks, exclusions and remaining changes in the main
conversation, including failures or partial completion. Leave the review and
commit work to the child session.
