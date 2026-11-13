# Supporting projects

Supporting project code lives here, separately from the canonical post notebooks
under `content/posts/`. A post's CMS `code_path` identifies its companion source;
follow that path rather than assuming the latest implementation matches a lesson.
Project files are not copied into the Quarto site by CMS sync.

## Versioned reference sources

- [Production Agentic RAG](production-agentic-rag/README.md) contains seven weekly
  upstream snapshots. Its [release manifest](production-agentic-rag/releases.json)
  maps each post to an exact upstream commit.

Keep imported reference trees unchanged, including their licenses. Document
provenance and release mappings in each project's guide and manifest. Put
adaptations or experiments in a separately named directory and describe how they
differ from the reference source.

## Running project code

Read the selected project's guide and release-specific instructions first.
Use its own dependencies and Python environment, separate from Atlas's root
environment. Atlas's root tests and formatters exclude these imported trees;
validate project changes in the relevant project environment.

Keep local credentials and runtime data out of Git. Review upstream examples
before starting services: development credentials, published ports, shared
volumes and reset commands may be unsuitable for a public host or an existing
local installation. Follow the project guide for isolation and cleanup rather
than assuming different releases can run together safely.
