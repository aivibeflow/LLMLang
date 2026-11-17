# LLMLang Project Plan

**Updated:** 2026-11-17

This file tracks project-level work that is not yet fully specified in the draft language definition. Research reports and ADRs record evidence and architectural decisions; this plan records execution status and next steps.

## Current workstreams

| Workstream | Status | Outcome / next step |
|---|---|---|
| Git representation and semantic merge research | **Completed** | Report: [research/GIT-SEMANTIC-REPOSITORY.md](research/GIT-SEMANTIC-REPOSITORY.md). ADR-014 records the current Proposed direction. |
| Git-backed source representation | **Next** | Specify the minimal canonical textual repository representation, import/export rules, and reproducible reconstruction of the Semantic Program Graph. |
| Semantic identity and hashing | **In progress** | Keep Git object identity separate from semantic hashes; verify canonicalization and hash-relevant inputs against the existing semantic-cache model. |
| Semantic diff and three-way merge | **Planned** | Define stable-ID operations and conservative conflict rules; cover independent edits, update/update, delete/update, rename/move, and split/merge. |
| Git integration | **Planned** | Prototype a custom merge driver, explicit local setup/doctor commands, repository-level graph validation, and temporary-repository integration tests. |
| Merge evaluation | **Planned** | Benchmark correctness, false-conflict rate, runtime, cache/store reconstruction, and failure behavior on missing context. |

## Completed

- [x] Research Git object storage, content-addressed semantic stores, semantic diff/merge approaches, and Git integration mechanisms.
- [x] Save the full research report in `research/GIT-SEMANTIC-REPOSITORY.md`.
- [x] Extract the architectural decision into [ADR-014](docs/adr/014-git-semantic-merge.md).

## Next acceptance gate

The Git-representation workstream is ready to move beyond research when the prototype demonstrates all of the following:

1. A clean checkout can reconstruct the semantic graph from repository source and pinned dependencies without relying on an irreplaceable local KV cache.
2. Formatting-only changes and file moves preserve semantic identity where the language rules say they are non-semantic.
3. A semantic change changes the relevant semantic hash and invalidates only computations whose exact action inputs depend on it.
4. Three-way merge is deterministic for identical base/ours/theirs inputs and policy versions.
5. Ambiguous or unsafe merges fail closed and report structured conflicts.
6. A completed Git merge passes repository-wide graph and reference validation.

## Planning notes

- ADR-014 is **Proposed**, not accepted as an irreversible final architecture. Revisit it after prototype evidence.
- A Git merge driver is an initial integration point, not proof that a multi-file graph merge is complete.
- Do not make the external KV store the only recoverable source of program meaning.
