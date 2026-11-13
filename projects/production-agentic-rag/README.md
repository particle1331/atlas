# Production Agentic RAG: weekly source snapshots

These are unmodified source snapshots from [Jam With AI's course
repository](https://github.com/jamwithai/production-agentic-rag-course), not
implementations authored for Atlas. Each folder contains the complete tracked
tree for its release, including the upstream README, notebooks, lockfile, tests,
assets, and MIT `LICENSE`. There are no nested Git repositories or submodules.

The [release manifest](releases.json) records exact commit IDs and post IDs.
The commits, rather than the movable tags or `main`, define these snapshots.

The upstream Week 5 README contains unresolved conflict markers. These and
upstream whitespace issues are preserved for fidelity; `git diff --check` on
the initial import reports them. They are not local merge conflicts.

| Post | Local source | Upstream release |
| --- | --- | --- |
| Week 1: infrastructure | [`week1/`](week1/) | [week1.0](https://github.com/jamwithai/production-agentic-rag-course/releases/tag/week1.0) |
| Week 2: ingestion | [`week2/`](week2/) | [week2.0](https://github.com/jamwithai/production-agentic-rag-course/releases/tag/week2.0) |
| Week 3: keyword search | [`week3/`](week3/) | [week3.0](https://github.com/jamwithai/production-agentic-rag-course/releases/tag/week3.0) |
| Week 4: hybrid search | [`week4/`](week4/) | [week4.0](https://github.com/jamwithai/production-agentic-rag-course/releases/tag/week4.0) |
| Week 5: generation | [`week5/`](week5/) | [week5.0](https://github.com/jamwithai/production-agentic-rag-course/releases/tag/week5.0) |
| Week 6: caching and observability | [`week6/`](week6/) | [week6.0](https://github.com/jamwithai/production-agentic-rag-course/releases/tag/week6.0) |
| Week 7: agents | [`week7/`](week7/) | [week7.0](https://github.com/jamwithai/production-agentic-rag-course/releases/tag/week7.0) |

## Reading and running a week

Use the folder matching the post. Later releases retain earlier tutorial
notebooks, but their application code has changed; an old notebook inside
`week7/` is not a substitute for the Week 1 source. Compare adjacent folders
when explaining how an implementation evolves:

```sh
git diff --no-index projects/production-agentic-rag/week1/src \
  projects/production-agentic-rag/week2/src
```

Exit status 1 from that command means differences were found.

Run the Docker lab from the selected weekly directory, not from the Atlas root:

```sh
cd projects/production-agentic-rag/week1
# First setup only; do not overwrite an existing local .env.
cp -n .env.example .env
docker compose --project-name rag-week1 config --quiet
docker compose --project-name rag-week1 up --build -d
```

Use each release's own dependencies and Python version, separately from Atlas's
environment. Run only one course stack at a time: published ports and explicit
container names can conflict despite different Compose project names. Stop the
current stack with `docker compose --project-name rag-week1 down` before changing
weeks; do not routinely add `--volumes`, which deletes stored state. Review
volume reuse and schema/model compatibility before starting another release.
The upstream instructions include development credentials, exposed services,
and sometimes destructive reset commands; do not treat them as public-host
deployment guidance. No Docker stack was executed as part of importing these
snapshots.

## Provenance and changes

The snapshots were copied with `git archive <commit>` from the commits in
`releases.json`. To reproduce an import, clone the upstream repository outside
Atlas, fetch the matching tag, confirm its peeled commit with
`git rev-parse 'week1.0^{commit}'`, and archive the manifest's exact commit into a
new empty directory. Compare the result before replacing anything; never
overwrite local experiments or `.env` files. Preserve each release's license.

Keep the weekly reference trees unchanged. Put deliberate adaptations in a
separately named project directory and document how they differ from upstream.
Root Atlas tests/formatters exclude these imported projects; run the upstream
tests from the appropriate isolated project environment when needed. The
committed `.env.test` files in Weeks 3–7 are upstream test fixtures, not local
credentials; actual `.env` files remain ignored.
