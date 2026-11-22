# External Research References and Snapshots

**Prepared:** 2026-11-20  
**Purpose:** Preserve primary technical references needed by the LLMLang research programme.  
**Status:** Reference collection only. No claims from these sources have been evaluated as LLMLang research results.

## 1. Versioned source snapshots stored in this repository

The files under `snapshots/` are verbatim source snapshots retrieved from the upstream repositories and pinned to the revisions below. The upstream licence notice is preserved in each source group. These are reference copies, not LLMLang-authored specifications.

| Source | Upstream revision | Relevant local snapshots | Use in LLMLang research |
|---|---|---|---|
| Model Context Protocol | Stable specification release `2026-07-28`, upstream commit `5f5440bb26a62e2cf3440b92da5a667efa03b267` | `snapshots/MCP/basic-index.mdx`, `authorization.mdx`, `transports.mdx`, `schema.json`; `LICENSE.md` | RT-16/19/22: protocol/transport boundary, authorization, schema source of truth, versioned server surface |
| OCI Image Specification | Upstream commit `4feed4a6674e59d301b9294f187ac46acb2de99f` (2026-10-22) | `snapshots/OCI/descriptor.md`, `manifest.md`, `image-layout.md`; `LICENSE-APACHE-2.0.txt` | RT-05/11/12: typed content descriptors, digests, size/media type, manifest/layout and content-addressed distribution |
| Alive2 | Upstream commit `3bdd4f5e1cefa47057e93110e707acd11cfe08e4` (2026-11-16) | `snapshots/Alive2/README.md`, `LICENSE-MIT.txt` | RT-07/09/13: LLVM translation validation, refinement checking and limits of the tool |
| Bazel Remote Execution API | Upstream commit `e0c0554bfc8a37abf336c3e78070684367738e1d` (2026-11-10) | `snapshots/REAPI/remote_execution.proto`, `LICENSE-APACHE-2.0.txt` | RT-11/12: action cache, content-addressed storage, remote execution and API message contracts |

### Attribution and licence notes

- MCP: the copied root `LICENSE` file records the project's licensing transition. It states that new specification contributions are under Apache-2.0, while non-specification documentation contributions are under CC-BY-4.0. The snapshots in this group are specification material. Preserve the upstream file when copying or redistributing them.
- OCI and Bazel Remote Execution API: Apache License 2.0; the upstream licence text is included alongside the snapshots.
- Alive2: MIT License; the upstream licence text is included alongside the README.
- Source blob SHA values are available in the Git history for each snapshot file. The upstream repository commit is recorded above so the source can be compared with later revisions. Exact upstream Git blob object IDs and repository paths are listed in [SNAPSHOT-MANIFEST.json](SNAPSHOT-MANIFEST.json). The copied MCP JSON Schema was parsed successfully, and all 13 stored source/licence files were checked against their upstream blob IDs.

## 2. Official materials linked for study, not copied here

Some standards and documentation are maintained as live/versioned web publications or carry separate redistribution terms. Keep them as source links and pin the exact edition/tool version at the start of each future experiment.

| Area | Official reference | Relevant preparation brief | Handling |
|---|---|---|---|
| SMT solver input language | [SMT-LIB 2.7 standard, release 2026-09-09 (PDF)](https://smt-lib.org/papers/smt-lib-reference-v2.7-r2026-09-09.pdf) | RT-03/06/07 path feasibility | Link-only here. The official PDF permits verbatim redistribution if copyright/permission notices remain and no modified version is made. The PDF was not retrievable into this repository in this session. |
| Solver proof evidence | [cvc5 1.4.2 proof production](https://cvc5.github.io/docs/cvc5-1.4.2/proofs/proofs.html) | RT-03/06/07; RT-07 evidence | Link-only; the cvc5 1.4.2 versioned proof page is linked. Pin the solver binary and chosen proof format (CPC/Alethe) during execution. |
| Lean proof kernel/reference | [Lean Language Reference](https://lean-lang.org/doc/reference/latest/) · [Lean releases](https://github.com/leanprover/lean4/releases) | RT-03/06/07; Scenario 34 | Link-only. The online reference currently identifies itself as 4.37.0-rc1; the latest stable release listed at preparation time is 4.36.0. Use the exact `lean-toolchain` pinned by the LLMLang checkout for reproducible work. |
| LLVM semantics | [LLVM Language Reference](https://llvm.org/docs/LangRef.html) · [LLVM UB Manual](https://llvm.org/docs/UndefinedBehavior.html) | RT-07/09/10/13 | Link-only; live docs can change. Pin LLVM release/commit, target triple and flags in each result. |
| Rust resource semantics | [Rust Reference — Destructors and Drop Scopes](https://doc.rust-lang.org/reference/destructors.html) | RT-03/04 source semantics and ownership | Link-only; pin the Rust toolchain/reference release used in the experiment. |
| Go concurrency | [The Go Memory Model](https://go.dev/ref/mem) | RT-03/04; RT-04 provider reconciliation | Link-only; record exact Go release and test/runtime settings. |
| C++ concurrency | [C++ working draft — data races](https://eel.is/c++draft/intro.races) | RT-03/04; RT-07/13 | Link-only; this is a living working draft, not a frozen published standard. Record access date and relevant revision. |
| SQLite resource lifetime | [sqlite3_close / sqlite3_close_v2](https://www.sqlite.org/c3ref/close.html) · [Online Backup API](https://www.sqlite.org/c3ref/backup_finish.html) · [SQLite threading modes](https://www.sqlite.org/threadsafe.html) | RT-04 provider reconciliation and guard coverage | Link-only; reproduce against an explicitly pinned SQLite release/build configuration. |
| Git object/storage/protocol | [Git pack format](https://git-scm.com/docs/gitformat-pack) · [Git protocol v2](https://git-scm.com/docs/gitprotocol-v2) | RT-05/06 identity; RT-16/19/20/22/23 lifecycle | Link-only; record Git version and object format (SHA-1/SHA-256) used. |
| Nix content addressing | [Nix content-addressed store objects](https://nix.dev/manual/nix/2.35/store/store-object/content-address.html) · [Store Path Specification](https://nix.dev/manual/nix/2.35/protocols/store-path.html) | RT-05/06 and RT-11/12 | Link-only; these are versioned Nix 2.35 manual references. |
| POSIX system contract | [The Open Group — POSIX Issue 8 online specifications](https://pubs.opengroup.org/onlinepubs/9799919799/) | RT-03/04 and LL-013–019 | Link-only; do not redistribute the standard text from this repository. Select the precise POSIX edition and clauses before experiments. |

## 3. Recommended reading order

1. **Before source/solver work:** SMT-LIB 2.7, cvc5 proof production, Lean version pinned by LLMLang, and Scenario 34's current SCW ledger.
2. **Before ownership/FFI work:** Rust drop scopes, Go memory model, C++ memory-model draft, and SQLite close/backup/threading contracts.
3. **Before identity/package/cache work:** OCI descriptors and manifests, Nix store paths, Bazel REAPI, and the LLMLang Draft Glossary.
4. **Before backend work:** LLVM LangRef/UB manual and Alive2, with target/compiler versions pinned.
5. **Before Toolchain/MCP work:** the stored MCP release sources/schema, Git pack/protocol docs, and the selected POSIX clauses.

## 4. Use rules

- Read the source as one member of the linked LLMLang document cluster; do not treat a copied document as a research conclusion.
- Pin moving web references to a release, commit or dated edition before using them in an experiment.
- Preserve exact source versions, access dates, licence notices and raw test data.
- Separate the source's normative scope from LLMLang's candidate design questions.
- Do not copy additional third-party standards into the repository until their redistribution terms are checked.
- Research briefs remain the source of execution questions and exit criteria: [Preparation Pack](../preparation/README.md).


## 6. Snapshot provenance and integrity verification (2026-11-20)

The four upstream revisions were resolved and their recursive Git trees were inspected. For every entry in `SNAPSHOT-MANIFEST.json`, the blob at the declared upstream path matches the manifest's upstream blob ID, and the local snapshot's Git blob ID matches the same value.

| Source | Resolved upstream commit | Upstream tree | Verified files |
|---|---|---|---:|
| MCP stable specification 2026-07-28 | `5f5440bb26a62e2cf3440b92da5a667efa03b267` | `8957e31e8ecd6fd7f52df82d44b3827cb44cecb1` | 5/5 |
| OCI Image Specification | `4feed4a6674e59d301b9294f187ac46acb2de99f` | `db49a85ed9c7cf9ea73c3e686587e9d11de3d085` | 4/4 |
| Alive2 | `3bdd4f5e1cefa47057e93110e707acd11cfe08e4` | `00afc2cc9bf27749415d1ab1ac48750d4818a2fe` | 2/2 |
| Bazel Remote Execution API | `e0c0554bfc8a37abf336c3e78070684367738e1d` | `1fc34a272f266ba16d6dd82f6ef21dac9dbdff18` | 2/2 |
| **Total** |  |  | **13/13** |

There are no missing upstream paths, unmanifested local snapshot files, or blob mismatches. The local MCP schema parses as JSON Schema draft 2020-12 and contains 155 entries under `$defs`; this is a syntax/structure check, not a full semantic validation of the schema. The OCI and REAPI Apache-2.0 licence copies intentionally share the same blob ID. **No external snapshot or licence content was modified.**


### 6.1 Upstream signature and snapshot-completeness notes

GitHub reports valid verified signatures for all four upstream commits listed above. The local `SNAPSHOT-MANIFEST.json` is not itself signed; it records the pinned commits, trees, and blob identities but is not a signed provenance attestation.

- **MCP:** the schema contains 155 top-level `$defs` and 277 local `$ref` references; all local references resolve. This is a JSON syntax/reference check, not full JSON Schema meta-schema validation.
- **MCP documentation pages:** the global link audit found 44 unresolved relative-link occurrences across `authorization.mdx` (11), `basic-index.mdx` (23), and `transports.mdx` (10), pointing to omitted pages under the pinned specification tree and `docs/draft`. This is separate from schema `$ref` closure; the selected documentation snapshot is not self-contained.
- **OCI:** the three copied specification documents contain 32 unresolved relative-link occurrences pointing to seven documents not included in this partial snapshot.
- **Alive2:** the copied README contains six unresolved relative-link occurrences (five image assets and `BugList.md`). Only README and MIT license are copied; the Alive2 tool source is not.
- **REAPI:** the copied `remote_execution.proto` imports eight other proto files. The local snapshot contains none of them; one is present in the pinned upstream repository and seven are external Google API/Protobuf files. This is a source-file reference, not a self-contained proto compilation closure.

These completeness limits do not affect the verified 13/13 upstream/local blob identity. Do not treat a partial snapshot as a self-contained build or documentation bundle.


### 6.2 Curated external-reference reachability check

The external URLs in §2 were checked individually on 2026-11-21. Sixteen returned page/PDF content; the POSIX Issue 8 endpoint returned HTTP 403 to the checker and remains indeterminate rather than classified as broken. This is a one-time availability observation, not a version/content validation. See [RT-00 E-02 — Curated External Reference Reachability Check](../RT-00-E-02-CURATED-EXTERNAL-REFERENCE-REACHABILITY-2026-11-21.md).
