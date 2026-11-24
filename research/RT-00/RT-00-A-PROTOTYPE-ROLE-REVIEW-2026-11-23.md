# RT-00 A — Current-main prototype role review and inventory delta

**Date:** 2026-11-23  
**Repository:** `aivibeflow/LLMLang`  
**Audited main baseline:** `09db9b75f7ee928285fcfd8005f62ad1513202e7`  
**Previous inventory source revision:** `ca484a214ed464c43696e3a1f7ab1a0e0ae8d5e4`  
**Disposition:** the 36 prototype paths outside the previous individual role-triage total have now been reviewed by content. This is file-role classification, not claim-level validation, test execution, or independent reproduction.

## 1. Method and scope

The previous inventory recorded 289 prototype paths and 253 individually role-triaged files, leaving 36 outside that total. The 36 were reconciled against the per-file inventory records and reviewed using source contents, module declarations/docstrings, imports, paired test modules, explicit report references, the prototype index, and the relevant PLAN stage.

The 36 consist of:
- 30 records previously marked `not-reviewed`;
- three paired Lean test modules whose related semantic modules were already included in the 253 total;
- two RT-04 native runner files that had a role description in the semantic-traceability report but were not included in the prototype-family individual-review total;
- one LLVM preservation runner with an existing role description but not included in that total.

Three related Lean semantic modules already counted in the 253 total—`PairedObservationSemantics.lean`, `ProgramObservationSemantics.lean`, and `SymbolicCommandSemantics.lean`—were also re-read directly. Their inventory status is refined from inferred first-pass module role to content-role triage; this does not add three to the count.

Role assignments below are grounded in source and explicit report/test relationships. The listed PLAN stage is a navigation/tracking relation, not evidence that the stage's acceptance criteria are met. A test module is classified as test evidence even when no current-main execution is independently established by this review.

## 2. Individual role mappings

### 2.1 RT-26 — hierarchical resource accounting

| Path | Individual role | RT / PLAN stage | Evidence boundary |
|---|---|---|---|
| `research/PROTOTYPES/BUDGET-CANCELLATION-01/test_budget_cancellation.py` | Python model tests for cancellation admission closure, reservation settlement, spent-unit preservation, and sibling admission | RT-26 / Stage 7 | Paired with [RT-26 cancellation accounting](../RT-26/RT-26-CANCELLATION-ACCOUNTING.md); the retained run records three cancellation tests plus four reservation baseline tests. This is a serialized cooperative ledger fixture, not production enforcement. |
| `research/PROTOTYPES/BUDGET-RESERVATION-01/test_budget_reservation.py` | Python model tests for cumulative hierarchical reservation, linearization order, retry idempotence, and cancellation settlement | RT-26 / Stage 7 | Paired with [RT-26 cooperative budget reservation](../RT-26/RT-26-COOPERATIVE-BUDGET-RESERVATION.md); bounded schedules do not establish instantaneous resource metering or OS enforcement. |

### 2.2 RT-07 / Scenario 34 — source semantics, rewriting, and proof binding

| Path | Individual role | RT / PLAN stage | Evidence boundary |
|---|---|---|---|
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/ObservableRewrite.lean` | Typed rewrite transformation and preservation theorem for result, failure, and ordered observable trace | RT-07 / Stage 2 | Paired with [observable rewrite correctness](../RT-07/RT-07-OBSERVABLE-REWRITE-CORRECTNESS.md); the theorem covers its declared typed scalar grammar, not arbitrary compiler rewrites. |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SourceCpcRefutation.lean` | Direct source-bound CPC gate: reconstructs the query from typed source and observation context, checks ordered assumptions, and requires a complete Logos verdict | RT-07, Scenario 34 / Stage 2 | Paired with [source-bound CPC refutation](../RT-07/RT-07-SOURCE-BOUND-CPC-REFUTATION.md); does not establish general wire correspondence or solver soundness beyond the admitted fragment. |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SourceCpcRefutationTests.lean` | Lean positive/negative controls for wrong source/query, reordered assumptions, undeclared factor, missing derivation, and out-of-profile aliases | RT-07, Scenario 34 / Stage 2 | Test source for the direct gate; file classification does not itself assert a fresh Lean execution. |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SourceQueryEnvelope.lean` | Typed JSON envelope construction/decoding and symbol-binding correspondence for source-owned relational queries | RT-07, Scenario 34 / Stage 2 | Paired with [source-owned query envelope](../RT-07/RT-07-SOURCE-OWNED-QUERY-ENVELOPE.md); the result is a bounded wire representation, not a complete canonical repository serialization. |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SourceQueryEnvelopeTests.lean` | Lean controls for source-envelope round-trip, symbol roles, sorts, and decoded query correspondence | RT-07, Scenario 34 / Stage 2 | Paired test entry point for the envelope theorem; test presence is not a run record. |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/PairedObservationTests.lean` | Lean examples and controls for paired input valuations and equality of selected observable outcomes | RT-03, RT-07, Scenario 34 / Stage 2 | Paired with the already-counted `PairedObservationSemantics.lean`; supports only its explicit observation contract and finite typed language. |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/ProgramObservationTests.lean` | Lean examples for source-program execution observations, selected state fields, and internal-state differences excluded from the observation contract | RT-03, RT-07, Scenario 34 / Stage 2 | Paired with the already-counted `ProgramObservationSemantics.lean`; does not establish semantics for constructs outside the modeled grammar. |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SymbolicCommandTests.lean` | Lean controls for symbolic command lowering, branch guards, state writes, local initialization, and command-sequence preservation | RT-03, RT-07, Scenario 34 / Stage 2 | Paired with the already-counted `SymbolicCommandSemantics.lean`; branch guards are evaluated against the modeled entry valuation. |

### 2.3 RT-05 / RT-06 / RT-09 — graph admission, scoped reads, and lowering

| Path | Individual role | RT / PLAN stage | Evidence boundary |
|---|---|---|---|
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/src/spg_admission.py` | Independent validator/admission checker for imported, acyclic, typed SPG values and executable dependency edges | RT-05 / Stage 1 | Paired with [typed SPG import validation](../RT-05/RT-05-TYPED-SPG-IMPORT-VALIDATION.md); bounded to the declared stored-value grammar and does not prove arbitrary graph encodings or source provenance. |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_spg_admission.py` | Tests integrity-versus-executable-type separation, invalid rehashed bodies, selected-history closure, and unsupported encodings | RT-05 / Stage 1 | Paired with `spg_admission.py` and the SPG representation fixtures; the report records nine rehashed invalid graphs rejected. |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/src/spg_ordered_lowering.py` | Lowers the reachable typed scalar SPG closure into an ordered instruction fixture and executes it under a fuel bound | RT-09 / Stage 6 | Paired with [ordered SPG lowering](../RT-09/RT-09-ORDERED-SPG-LOWERING.md); not machine-code generation or general target-preservation proof. |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_spg_ordered_lowering.py` | Differential tests for ordered lowering, nested calls, binding-sensitive artifact identity, recursion/fuel, and trace preservation | RT-09 / Stage 6 | Paired with `spg_ordered_lowering.py`; the report's 140 observations are finite-fixture evidence. |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt06_negative_binding_reads.py` | Differential tests for exact scoped-binding read projections, precedence, conflicts, malformed layers, and false-reuse counterexamples | RT-06 / Stage 3 | Paired with [scoped binding read dependencies](../RT-06/RT-06-SCOPED-BINDING-READ-DEPENDENCIES.md); projection is conditional on complete validated immutable layers. |

### 2.4 RT-23 / RT-24 — Git publication, mapping merge, and tree completeness

| Path | Individual role | RT / PLAN stage | Evidence boundary |
|---|---|---|---|
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt23_commit_recovery.py` | Native Git fixture tests for prepared commits, operation receipts, retries, ref movement, and compare-and-swap recovery | RT-23 / Stage 4 | Paired with [exact-tree commit recovery](../RT-23/RT-23-EXACT-TREE-COMMIT-RECOVERY.md); local Git model, not a production multi-writer coordinator. |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt23_interface_mapping_merge.py` | Tests deterministic disjoint-key mapping merge, same-key review, duplicate export claims, signature conflicts, and revision-bound publication | RT-23 / Stage 4 | Paired with [interface mapping merge](../RT-23/RT-23-INTERFACE-MAPPING-MERGE.md); disjoint keys can still claim the same export. |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_call_target_merge.py` | Tests exact call-target retarget composition, same-selector conflicts, guard-change exclusion, and upstream pin constraints | RT-24 / Stage 4 | Paired with [call-target merge](../RT-24/RT-24-CALL-TARGET-MERGE.md); narrow structural law for unchanged caller declarations, not arbitrary source occurrence continuity. |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_git_replay.py` | Tests source closure after real Git cherry-pick/rebase histories and rejects unrelated-parent or incomplete replay evidence | RT-24 / Stage 4 | Paired with the RT-24 Git replay/source-closure study; replay cleanliness alone is not proof of semantic patch correspondence. |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_merge_tree_gate.py` | Tests closed source inventories, exact Git-tree enumeration, semantic import, reverse-reference completeness, and merge-tree gates | RT-24 / Stage 4 | Paired with [merged-tree source completeness](../RT-24/RT-24-MERGED-TREE-SOURCE-COMPLETENESS.md); closed fixture schema, not a production repository reader. |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_semantic_merge_core.py` | Tests explicit three-way slot selection, conflict reporting, source completeness, and graph reconstruction | RT-24 / Stage 4 | Paired with the RT-24 semantic merge studies; candidate merge behavior remains bounded to the closed inventory fixture. |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_tree_bound_cip.py` | Tests binding an approved change-impact plan and migration disposition to the exact publishable Git tree and receipt | RT-24 / Stage 4 | Paired with [tree-bound CIP publication](../RT-24/RT-24-TREE-BOUND-CIP-PUBLICATION.md); does not establish a complete general caller-migration policy. |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_typed_tree_diff.py` | Tests typed semantic edge differences across independently imported Git trees, including moves, retargets, replacement, and incomplete inputs | RT-24 / Stage 4 | Paired with [typed tree diff](../RT-24/RT-24-TYPED-TREE-DIFF.md); semantic diff output is not itself proof of merge completeness. |

### 2.5 RT-17 — diagnostic replay and publication

| Path | Individual role | RT / PLAN stage | Evidence boundary |
|---|---|---|---|
| `research/PROTOTYPES/DIAGNOSTIC-REPLAY-01/test_diagnostic_replay.py` | Tests UTF-8/16/32 source-position conversion, diagnostic snapshot validity, deterministic multi-file staging, and behavioral repair validation | RT-17 / Stage 7 | Paired with [diagnostic replay](../RT-17/RT-17-DIAGNOSTIC-REPLAY.md); finite in-memory fixture, not human/agent usability evidence. |
| `research/PROTOTYPES/DIAGNOSTIC-REPLAY-01/test_diagnostic_publication.py` | Tests publication ordering for overlapping diagnostic requests, stale/partial result rejection, cancellation, and edits during analysis | RT-17 / Stage 7 | Paired with [diagnostic publication](../RT-17/RT-17-DIAGNOSTIC-PUBLICATION.md); modeled asynchronous schedules, not a production editor protocol. |

### 2.6 RT-05 identity bytes; RT-04/RT-10/RT-13 native and backend probes

| Path | Individual role | RT / PLAN stage | Evidence boundary |
|---|---|---|---|
| `research/PROTOTYPES/IDENTITY-BYTES-01/compare.py` | Python oracle and cross-implementation comparator for typed canonical identity byte encodings | RT-05 / Stage 1 | Paired with [portable identity bytes](../RT-05/RT-05-PORTABLE-IDENTITY-BYTES.md); finite typed domains, not an accepted canonical encoding/hash policy. |
| `research/PROTOTYPES/IDENTITY-BYTES-01/encode.mjs` | Node.js implementation of the typed identity byte encoder used by the Python/JavaScript comparison | RT-05 / Stage 1 | Must be interpreted with `compare.py` and its report; no universal Unicode or digest policy is selected. |
| `research/PROTOTYPES/LLVM-PRESERVATION-01/llvm_mutable_view_probe.py` | LLVM/C++ probe for mutable overlapping byte-view access, aliasing, and transactional preservation | RT-09, RT-13 / Stage 6 | Paired with [mutable byte-view preservation](../RT-09/RT-09-13-MUTABLE-BYTE-VIEW-PRESERVATION.md); bounded local/native probe and recorded target/toolchain, not general pointer provenance. |
| `research/PROTOTYPES/ORDERED-EFFECTS-01/compare.py` | Finite Boolean-fragment model for ordered interprocedural effects, trace composition, and failure propagation | RT-04 / Stage 5 | Paired with [ordered call effect summaries](../RT-04/RT-04-ORDERED-CALL-EFFECT-SUMMARIES.md); finite executable model, not general alias/effect analysis. |
| `research/PROTOTYPES/POSIX-INTERRUPT-01/read_interrupt.c` | Native POSIX/Linux pipe-read probe comparing EINTR return and restart behavior | RT-10 / Stage 5 | Paired with [POSIX read interruption](../RT-10/RT-10-POSIX-READ-INTERRUPTION.md); Linux x86-64 and recorded libc/kernel environment only. |
| `research/PROTOTYPES/POSIX-IO-01/nonblocking_pipe.c` | Native comparison of libc and raw Linux x86-64 nonblocking pipe I/O outcomes | RT-10 / Stage 5 | Paired with [POSIX nonblocking pipe I/O](../RT-10/RT-10-POSIX-NONBLOCKING-PIPE-IO.md); raw adapter is explicitly ABI/target-specific. |
| `research/PROTOTYPES/STRUCTURED-SCOPE-01/scope_join.py` | Finite schedule model for nested task-scope completion, cleanup joins, and safe terminal publication | RT-10 / Stage 5 | Paired with [structured scope join](../RT-10/RT-10-STRUCTURED-SCOPE-JOIN.md); finite cooperative task-event model, not runtime scheduler correctness. |
| `research/PROTOTYPES/WASM-VIEWS-01/compare.mjs` | Node/WABT differential harness comparing Wasm memory32 byte views with an exact-integer logical oracle | RT-13 / Stage 6 | Paired with [Wasm memory32 views](../RT-13/RT-13-WASM-MEMORY32-VIEWS.md); report-declared finite observations, with arbitrary descriptors, memory growth, allocation lifetime, and cross-engine behavior still open. |
| `research/PROTOTYPES/RT-04-01/run_native_probes.py` | Native orchestration runner for selected SQLite C-API, durable-receipt, and generated-Rust probes | RT-03, RT-04, RT-10, RT-13 / Stages 2, 5, 6 | Paired with [RT-04 native reproduction](../RT-04/RT-04-NATIVE-REPRODUCTION.md) and the RT-04-01 evidence graph; the runner's existence is not the native execution result. |
| `research/PROTOTYPES/RT-04-01/test_rt04_native_probe_runner.py` | Four command-inventory, suite-composition, tracked-path, and toolchain-gate tests for the native runner | RT-03, RT-04, RT-10, RT-13 / Stages 2, 5, 6 | These tests validate runner metadata and gates; they do not execute the ten native commands. |
| `research/PROTOTYPES/LLVM-PRESERVATION-01/run_llvm_preservation_probes.py` | Native reproduction runner for the bounded LLVM integer and byte-view preservation probes | RT-07, RT-09, RT-13 / Stages 2, 6 | Paired with [LLVM preservation reproduction](../RT-13/LLVM-PRESERVATION-REPRODUCTION.md); recorded runs are separate from Required CI and remain fixture/target/toolchain bounded. |

## 3. Reconciled prototype-family coverage

The previous aggregate was 253 individually role-triaged paths out of 289. The 36 paths above now have individual role entries. The family-level totals reconcile as follows:

| Family | Current paths | Individually role-triaged |
|---|---:|---:|
| ALLOCATOR-COMPAT-01 | 1 | 1 |
| BUDGET-CANCELLATION-01 | 1 | 1 |
| BUDGET-RESERVATION-01 | 1 | 1 |
| CLI-WORKLOADS-01 | 3 | 3 |
| DEPENDENCY-GRAPH-01 | 132 | 132 |
| DIAGNOSTIC-REPLAY-01 | 2 | 2 |
| IDENTITY-BYTES-01 | 2 | 2 |
| LLVM-PRESERVATION-01 | 7 | 7 |
| ORDERED-EFFECTS-01 | 1 | 1 |
| PACKAGE-IDENTITY-01 | 7 | 7 |
| PACKAGE-INDEX-01 | 17 | 17 |
| POSIX-INTERRUPT-01 | 1 | 1 |
| POSIX-IO-01 | 1 | 1 |
| RT-04-01 | 106 | 106 |
| RT-16-AUTHORIZATION-01 | 2 | 2 |
| STRUCTURED-SCOPE-01 | 1 | 1 |
| TOOLCHAIN-SERVER-01 | 3 | 3 |
| WASM-VIEWS-01 | 1 | 1 |
| **Total** | **289** | **289** |

The six Scenario 34 Lean modules are handled without double-counting: the three semantic source modules were already included in the 253 aggregate and are now directly re-reviewed; their three paired test modules are among the 36 newly mapped paths. The two RT-04 runner files and the LLVM runner are included in the 36 because they were not part of their families' previous individual-role totals.

## 4. Inventory delta after PR #237

The exact commit comparison from the PR #234 merge commit `ad5b81723ac7995408054b311ac523154fefac85` to current main `09db9b75f7ee928285fcfd8005f62ad1513202e7` contains one commit and three changed paths:
- `docs/adr/015-toolchain-server-semantic-api.md` modified;
- `docs/adr/017-mcp-agent-object-format.md` added;
- `research/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md` modified.

Thus the only changed research path in that delta is RT-19. Its manifest record is stale: old blob `555fb44b07e128598ca65d46d93f072934621d7c`, 31,844 bytes; current blob `fcc78370362f93261b7117ca86a7afcaaa09cf7b`, 32,848 bytes. The current README and G-report blob identities were checked against their manifest records and match. No research path addition or deletion is reported by this commit comparison.

ADR-017 is an accepted, deliberately scoped decision: JSON is the default for SPG objects exchanged with agents through MCP, with one JSON value per independently addressable graph object and SPG IDs for references. It does not decide the canonical Git repository representation, on-disk storage, canonicalization profile, or Content Hash. This new decision is outside the research-tree inventory; the RT-19 research document is the single changed research record.

The manifest refresh and report addition in this PR are subject to the exact recursive-tree inventory workflow. Until that workflow passes on the final PR head, the new manifest must not be described as independently verified exact.

## 5. Limits and unresolved items

- 289/289 means every prototype path has an individual file-role mapping. It does not mean every claim has been validated, every test has passed, or every experiment has been independently reproduced.
- The 137 Scenario-named paths versus 136 mapped Scenario files remains unresolved. No missing scenario ID or mapping is inferred here.
- The `ImpHash` / `ImplHash` terminology issue remains unresolved.
- RT-19's scoped MCP JSON decision is accepted by ADR-017; the general Toolchain architecture, canonical repository serialization, and hash policy remain open.
- The B3 and F reports predate ADR-017 and require a scoped follow-up to reflect the new decision without widening its scope.
- Historical results, fixtures, snapshots, and prior audit baselines are preserved. No historical finding is rewritten.
- No experiment is rerun as part of this content-role classification.

**Conclusion:** the current 289 prototype paths now have individual content-role triage. Inventory freshness remains subject to the PR-head recursive-tree workflow. RT-00 remains incomplete at claim-level traceability, semantic consistency, reproducibility, external provenance, and unresolved Scenario crosswalk layers.
