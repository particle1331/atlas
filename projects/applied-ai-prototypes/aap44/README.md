# AAP-44: Designing a Natural-Language Workflow Engine

Translate requests into validated workflows with explicit execution, review, recovery and resource limits.

**Root-relative project:** `projects/applied-ai-prototypes/aap44`

**Status:** Course implementation unavailable; a separate external reference is imported.

No complete natural-language workflow engine was identified in the pinned course source. The external incident-triage experiment below follows a predefined procedure; it is not a completed implementation of this lesson's broader design.

## Imported references

No matching implementation was identified in the original `prototypes-ai` snapshot; no placeholder code was invented.

Original course-source commit: `678d9d0b579a72113c94a2d2f57671fd9f7f2a56`. The [course-source manifest](../provenance.json) records that import, including its missing-implementation status. The [course plan](../../../.atlas/plans/applied-ai-prototypes.md) contains AAP-44's outline and open gaps.

### External reference: workflow-slm

- **Repository:** [arpitbbhayani/workflow-slm](https://github.com/arpitbbhayani/workflow-slm).
- **Pinned commit:** [`e3541a6c8a01be031ca5477311eddfa10230b4b3`](https://github.com/arpitbbhayani/workflow-slm/tree/e3541a6c8a01be031ca5477311eddfa10230b4b3).
- **Local snapshot:** [reference/workflow-slm/](reference/workflow-slm/), including the unchanged [upstream README](reference/workflow-slm/README.md).
- **Provenance:** [workflow-slm-provenance.json](workflow-slm-provenance.json) records the source blobs, file modes, sizes and SHA-256 checksums separately from the original course-source manifest.
- **Write-up:** [Compiling a Workflow into a 3B Model](https://arpitbhayani.me/blogs/compiling-an-sop-into-a-3b-model/), a live external page rather than a locally pinned article.

The snapshot includes the incident-triage SOP, simulator, structured-action runtime, training and evaluation code, tests and documentation. The model selects actions within a fixed procedure; runtime checks constrain their schema and transition order, while deterministic code computes severity and paging decisions. This is reference material for bounded tool use, not evidence of arbitrary workflow synthesis, authorization, durable execution or compensation.

**License:** No license file or license declaration was found in the pinned tree. Public availability does not establish reuse or redistribution permission. Confirm terms with the author before reusing the code, pushing this snapshot to a shared repository or exposing it through Atlas's companion-source browser.

**Execution and evidence:** This import copies Git blobs without executing upstream code or installing its dependencies. No training, model/API request or benchmark was run. In particular, `src/exp/smoke.py` uses an oracle client, writes a dummy adapter configuration and supplies hard-coded summary metrics to its report generator. Despite the upstream quickstart's description, `make smoke` does not train an adapter and would not reproduce the published model accuracy or cost figures.

The bundled `docs/REPORT.md` repeats those hard-coded summary figures and marks the teacher-forced accuracy criterion of at least 95% as passed, while listing only 10–25% for several core branches. That report does not substantiate the published benchmark; establishing it would require actual trained adapters, evaluation traces and measured costs.

Read the upstream source before running it in a separate environment and disposable workspace. Training and local inference need dependencies beyond those listed in the upstream `pyproject.toml`; API-backed paths require credentials and may incur costs. Pipeline commands write artifacts and can overwrite `docs/REPORT.md`. Keep the imported snapshot unchanged and put any later runs or adaptations in a separate copy.

## Related companion projects

- [AAP-10](../aap10/README.md)
- [AAP-11](../aap11/README.md)
- [AAP-12](../aap12/README.md)
- [AAP-26](../aap26/README.md)
- [AAP-33](../aap33/README.md)
- [AAP-34](../aap34/README.md)
- [AAP-35](../aap35/README.md)
- [AAP-36](../aap36/README.md)
- [AAP-38](../aap38/README.md)
- [AAP-41](../aap41/README.md)
- [AAP-42](../aap42/README.md)
- [AAP-43](../aap43/README.md)

## Later implementation and execution

Keep `reference/` unchanged. Put authored fixes and experiments in a separate `implementation/` directory when authoring begins; none was created by this import. Review the upstream source and dependencies, and use a separate environment plus a disposable workspace for mutating or code-generation examples.

No prototype, nested test, API request or generated code was run during either import. Existing saved outputs and reports are upstream artifacts, not reproduced results or proof that the example is safe/correct.
