# RT-27 closed Git semantic records and external KV comparison

**Date** 2026-11-25 · **Plan** §4.2 · **Issue** [#320](https://github.com/aivibeflow/LLMLang/issues/320)

Two typed graph revisions contain 43 reachable objects each. One provider changes languages and creates a new implementation node and root. Every Git representation commits an explicit layout version, exact root, sorted inventory and required reverse index. The reader checks canonical representation, closes the graph through exact object bytes, and computes the expected reverse occurrences independently of the stored index.

| Candidate | Tracked files per revision | Checked reconstruction |
| --- | ---: | --- |
| One file per object | 45 | Both revisions recover from a clean Git clone. The layout uses one tracked path per object. |
| One packed canonical record file | 3 | Both revisions recover from a clean Git clone, including required reverse metadata. |
| Git manifest and external SQLite KV bytes | 2 | Both revisions recover while the exact KV objects are available. Git-only restoration declines the required external bytes. |

The runner creates six two-commit histories in Git 2.52.0 using SHA-1 and SHA-256 repository object formats. The clean clones use ordinary Git transport with `--no-local` and pass `git fsck --full`. Their origins are removed and source directories become unavailable. The six layouts and repository-format combinations preserve each revision's semantic root across different Git trees. Eight revision/layout pairs recover offline. The four manifest-only revision cases require the exact external store. The ten refusal controls cover missing external selection, corrupt KV bytes, stale required reverse metadata and misordered packed records.

A self-contained Git candidate can store canonical records in a bounded number of tracked files and bind reconstructable metadata. External KV can accelerate retrieval while a committed representation carries the required graph bytes. The one-file-per-object layout provides a reconstructed comparator and exceeds the tracked-file constraint. The packed fixture meets the scoped reconstruction and tracked-path checks of R-STORE-001 and R-STORE-002. Production SPG identities, trusted manifest issuance, container layout and scale remain open.

Reproduce with CPython 3.12.14, SQLite 3.53.1 and Git 2.52.0 from the repository root.

```bash
study=research/toolchain-and-collaboration/RT-27/GIT-CLOSED-REPRESENTATION-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two fresh sets of repositories and clones reproduced the archived roots, trees, commits and outcomes byte for byte.
