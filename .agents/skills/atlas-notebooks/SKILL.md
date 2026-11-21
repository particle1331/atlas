---
name: atlas-notebooks
description: Inspect, edit or execute Atlas post notebooks using the notebook CLI, including saved outputs and matching project source.
---

# Atlas notebooks

Run `uv run at notebook ...` from the repository root. Start with
`map`, `find`, `outline` or `cat` before reading raw notebook JSON or writing
ad hoc scripts. Use the actual post ID. Read complete target cells with
`cat --index N --with-revision --limit 0` and inspect stored outputs when
they matter. See the [notebook tools](../../../README.md#notebook-tools).

- Use the smallest applicable cell operation. `edit-cell` replaces the entire
  selected source and preserves its stored outputs. Preserve Quarto options,
  labels, attachments, metadata and surrounding content. Cell indices start
  at zero. Refresh the outline after inserts or removals. Inspect every match
  before using `remove-cell --tag`.
- Use `--content`, `--file PATH` or `--file -` for noninteractive edits. Quote
  heredoc delimiters for multiline input. Use the `notebook:<hash>` revision
  from `cat --with-revision` or `outline` for `--expected-revision`.
- Keep notebooks as ordinary cells. Leave front matter to CMS and generated
  navigation and TOCs to Quarto. Keep private plans in CMS notes or to-dos.
- Execute code explicitly when refreshed results are needed. Edits and site
  builds leave saved execution alone. Clear outputs deliberately and preserve
  unrelated results. Keep recovery files in `.atlas/cms/edits/` and
  `.atlas/cms/execution-conflicts/`. See [saved execution](../../../README.md#saved-execution).
- Use the post's CMS `code_path` and the release manifest to select matching
  code under `projects/`. Treat imported weekly snapshots as read-only and
  keep adaptations separate. Keep only public sidecars beside notebooks
  because sync copies them to the frontend. See [supporting projects](../../../projects/README.md).
