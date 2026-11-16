# Applied AI Prototypes: companion projects

Each draft post has a root-relative companion directory,
`projects/applied-ai-prototypes/aap1` through `aap44`. The matching CMS
`code_path` points to that directory. Read its local `README.md` before using
the code: a directory can contain imported reference examples or documentation
of a missing implementation, not a completed lesson implementation.

## Layout and source

```text
applied-ai-prototypes/
  README.md
  UPSTREAM_README.md
  provenance.json
  aap1/
    README.md
    reference/
      non-deterministic/
      evals/
  ...
```

Reference examples are copied from
[Arpit Bhayani's public prototype repository](https://github.com/arpitbbhayani/prototypes-ai)
at commit `678d9d0b579a72113c94a2d2f57671fd9f7f2a56`, the same revision used
for the earlier static audit. `UPSTREAM_README.md` preserves that revision's
root README. There are no nested Git repositories, submodules or automatic
updates from upstream.

The [provenance manifest](provenance.json) records every actual post ID,
companion directory, selected upstream folder, copied file, source blob and
SHA-256 checksum. Some examples support more than one post and are deliberately
copied to each matching `aapN/reference/` directory. These are independent
snapshots rather than symlinks to a moving shared implementation.

| Location | Meaning |
|---|---|
| `aapN/reference/<prototype>/` | Imported upstream files, unchanged except for the explicit environment-file omission below |
| `aapN/README.md` | Our guide to the post's sources, import status and unresolved implementation work |
| `aapN/implementation/` | Reserved convention for later authored adaptations; not created by this import |
| `.atlas/plans/applied-ai-prototypes.md` at the repository root | Course outline and open authoring gaps |

Keep references unchanged. Put deliberate fixes and experiments in
`implementation/` or another separately named directory, document their
relationship to the reference, and update the matching post when its code
changes. Imported code is available for inspection; this does not mean the
planned lesson, design exercise, acceptance tests or recorded measurements
have been implemented.

## Explicit omission and retained fixtures

The upstream tracked file `observability/.env` is **not copied**. Environment
files and `.env.*` variants other than `.env.example` are excluded before file
contents are read. No credentials from that file are needed to import, inspect
or validate the snapshots. Configure any later execution with your own local,
untracked environment settings; do not copy upstream credentials.

Other selected tracked files retain their original bytes, names and modes:
source, tests, requirements, READMEs, PDFs, web assets, saved outputs and sample
JSON. `memory_store.json` is an upstream sample/runtime fixture, not memory
collected from the author. Patcher `.orig`/`.rej` files are preserved artifacts,
not evidence that a repair succeeded. Captured model outputs can disagree with
the current source and are not reproduced results. Upstream formatting,
including whitespace issues, is preserved rather than reformatted during import.

## Missing and partial implementations

The per-post guides and manifest distinguish imported references from missing
implementations. In particular:

| Posts | Boundary |
|---|---|
| AAP-8, AAP-22, AAP-37, AAP-40, AAP-44 | No matching implementation was identified in the pinned public repository; the directory contains a guide, not invented placeholder code |
| AAP-4 | The Jev examples are available; Clairic remains an authoring-time source dependency |
| AAP-23 | Small RAG diagnostics are reference material, not a RAG system measured at ten million documents |
| AAP-28 | Patching examples and the search-source pointer are available, not Claude Code's complete implementation |
| AAP-39 | Workflow/patching examples are references, not a complete AI code reviewer |

All 35 course gaps remain open. Copying a prototype neither fixes its known
limitations nor establishes correctness, safety or production behaviour.

## Inspecting and running examples

Read the selected upstream README and source before execution. Many examples
construct clients at import time, call paid APIs from tests, execute model-written
Python/shell, overwrite files, stage Git changes or clean runtime directories.
No prototype, nested test, package installation, model request or generated-code
execution was performed as part of this import.

Use a separate environment for the selected example, not Atlas's root
environment. Review and pin dependencies as part of authoring; some upstream
manifests are incomplete or stale. Do not run API or shell tests merely because
their names begin with `test`. Perform mutating/code-generation experiments in
a disposable, appropriately isolated workspace.

For the web visualization in `aap17/reference/rrf-viz`, the Node toolchain is
separate from the Python examples. No web dependencies were installed or built.
Root Atlas pytest discovery and formatters exclude `projects/`.

Import validation checks the selected file set, checksums, paths, modes and
absence of environment files without importing or executing the examples.
