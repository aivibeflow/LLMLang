# Research Corpus Audit — 2026-11-20

**Research item:** PLAN.md §0.1, Reconcile the research corpus  
**Status:** Partial; complete tracked-path inventory and limited link checks recorded, semantic reconciliation still open  
**Primary snapshot revision:** `f560d0f9893f882a6756f1f0a3b070ea7ba1a09f` (inventory excludes its own manifest file)  
**Normative boundary:** This report records documentation and inventory findings only. It makes no language, architecture, identity, or implementation decisions.

## 1. Executive summary

The recursive Git tree at the primary snapshot revision contains **462 tracked research artifacts** (excluding the inventory manifest itself):

- 234 Markdown/MDX files (231 `.md` and 3 `.mdx`);
- 194 Python files;
- 22 Lean source files and one Lean toolchain pin;
- 3 JSON files;
- 1 C file, 1 Rust file, 1 TOML file, 1 Protocol Buffers schema, and 4 text files;
- 240 files under `research/PROTOTYPES/`;
- 24 files under `research/preparation/` and `research/references/`.

A machine-readable inventory snapshot records all 462 paths, Git blob SHAs, byte sizes, coarse categories, and qualified path-based traceability metadata: [RESEARCH-CORPUS-INVENTORY-2026-11-20.json](RESEARCH-CORPUS-INVENTORY-2026-11-20.json).

The main index's relative links and the preparation index's brief links resolve. Exact Git-blob comparison found one repeated blob: the same Apache-2.0 licence text is stored alongside both OCI and REAPI snapshots. This is expected shared licence content, not evidence of duplicated research.

The audit remains **partial**. The current `main` tree at the recorded baseline contains 22 Lean source modules and tests, including the paired-observation modules from PR #85 and the QF_LIA term-profile/admissibility modules added by PR #86. SCW-24/25 and SCW-29 are represented in source and CI; later Scenario 34 gates remain open. The inventory classifies paths and records tentative mappings; it does not verify every artifact's semantic contents, determine every supersession relationship, prove index completeness, or reproduce all experiments.

## 2. Evidence and checks performed

### 2.1 Repository inventory

- Retrieved the recursive Git tree for `main` at current `main` HEAD revision `f560d0f9893f882a6756f1f0a3b070ea7ba1a09f`; excluded the inventory manifest itself to avoid self-reference.
- Enumerated all 462 tracked research artifacts whose paths begin with `research/`, excluding the inventory manifest itself.
- Recorded path, Git blob SHA, byte size, coarse artifact category, and traceability metadata for every file in the inventory JSON.
- Distinguished scenario-named reports, prototype implementations, tests, prototype readmes/reports, preparation briefs, external snapshots/licences, structured fixtures, and research documents.
- Recorded direct RT/scenario identifiers as high-confidence path evidence. Prototype-family mappings are explicitly marked medium confidence; files without reliable path identifiers remain unassigned rather than receiving guessed mappings.

The inventory is pinned to the exact current `main` tree revision `f560d0f9893f882a6756f1f0a3b070ea7ba1a09f`. The inventory is a reproducible path-level snapshot. It is not a claim that every file's contents have been read or validated.

### 2.2 Markdown relative-link scan

- Scanned inline Markdown links in the **233-file historical baseline** under `research/` at the PR #79 baseline; later changes in PRs #80/#82 affected three distinct Markdown files, whose 30 local relative links were rechecked against the refreshed inventory tree.
- Checked **1,330 relative-link occurrences** across the 233-file historical baseline against the tracked repository tree (1,323 in the initial full scan; three Markdown files changed by PRs #80/#82 were rechecked after their latest edits (30 local links total), with a net increase of seven link occurrences). External HTTP(S)/mailto links, fragment-only links, and root-absolute paths from copied upstream documentation were excluded from local path resolution.
- Found one broken relative link in the LLMLang-authored `research/RT-04-PROTOTYPE-01-SCENARIOS.md`; corrected it to point to the sibling `RT-04-RT-03-CROSS-PROFILE-TRACES.md` file. A repeat check of the corrected file resolves.
- Found **38 unresolved relative-link occurrences inside verbatim external snapshots only**: six in the Alive2 README (five image assets and `BugList.md`) and 32 in OCI snapshot documents (references to seven OCI source documents not included in the partial snapshot). These files were not rewritten because they are preserved upstream source snapshots.
- The MCP snapshot contains root-absolute links into the upstream documentation site; these are not repository-relative paths and were not treated as missing local files.
- The current main index has 98 unique relative targets (99 inline relative-link occurrences); all resolve against the full repository tree. The preparation index has 11 unique relative targets and the references index has two; all resolve.

**Result:** no broken inline relative links were found in the historical baseline of LLMLang-authored research documents. The full current-corpus scan remains open. The 38 missing targets in copied upstream snapshots reflect the deliberately partial vendored source sets. This scan does not validate external URL availability, heading anchors, reference-style Markdown links, or index completeness against every artifact.

### 2.3 Taxonomy and dependency map

- `research/RESEARCH-TAXONOMY.md` contains 24 research-area entries, RT-01 through RT-24.
- `research/RESEARCH-DEPENDENCY-MAP.md` contains 94 dependency IDs, DEP-001 through DEP-094, with no gaps in that ID range.
- The previous Stage 0.3 summary in `PLAN.md` reported 18 areas and 35 edges; this was stale.

**Correction:** PLAN.md §0.3 now reports the current counts (24 areas and 94 edges); RT-24 was added as a candidate research area with eight explicitly provisional dependency edges (DEP-086–DEP-093), while RT-14 retains DEP-078–DEP-085. The taxonomy and dependency map remain evolving research registers; the existence of an edge does not make it an accepted architecture rule.

### 2.4 Preparation pack and external references

- The preparation index links eight preparation briefs; all eight resolve.
- The briefs distinguish preparation instructions from executed research evidence and specify reproducibility expectations such as source revisions, tool versions, fixtures, commands, raw outputs, negative/UNKNOWN cases, limitations, and decision boundaries.
- The external-reference register identifies four pinned snapshot groups: MCP, OCI, Alive2, and Bazel Remote Execution API.
- The reference register states that 13 stored source/licence files were checked against upstream blob IDs. This audit did not independently retrieve and re-hash those upstream files.

### 2.5 First-pass semantic traceability

- Reviewed the 36 inventory entries previously marked low confidence using document titles, scope/status declarations, section structures, explicit research-area declarations, and related-document references.
- Assigned candidate RT-area mappings or explicit Stage 0 research-management ownership to all 36 entries; recorded the basis and candidate plan stages in [the semantic traceability report](RESEARCH-CORPUS-SEMANTIC-TRACEABILITY-2026-11-20.md) and inventory JSON.
- Added `plan_stages` metadata to all 462 inventory records. A taxonomy/header/content crosswalk now maps all 136 Scenario reports to candidate RT areas: 63 from taxonomy links/ranges and 73 from first-pass report scope review. The first-pass individual role review now covers all 240 prototype artifacts across eight families and the Scenario 34 Lean extension; no prototype-tree artifacts remain without individual file-role mappings. The 104-file RT-04-01 family has received a separate content-based RT-03/RT-04 traceability review (39 RT-03-only, 59 RT-04-only, and 6 shared artifacts). The final five previously family-only files are now individually mapped: two RT-16 authorization artifacts and three RT-19 Toolchain Server artifacts. Content/claim and reproducibility validation remains open. Nine vendored technical source documents now have use-case mappings; seven reference/provenance files plus one prototype-family index remain Stage 0-only. RT-24 is registered in the taxonomy with candidate edges DEP-086–DEP-093; its candidate contract remains non-normative.
- The semantic review is explicitly first-pass triage, not full claim-level verification or acceptance of the proposals described by the documents.
- Scenario numbering review found 136 report files representing 135 unique IDs: Scenario 95 has a main study and an explicitly cross-referenced execution follow-up; Scenario 16 has no report in the current corpus. Its absence is recorded as unresolved (reserved number versus missing artifact), not silently renumbered.

**Result:** the previous 36 low-confidence records no longer have blank/unassigned path-only mappings. The RT-04-01 family no longer uses directory-name inference as its RT mapping basis; the corpus-wide semantic traceability gate remains open.

### 2.6 Initial section-level supersession review

Three explicit cases were recorded in the inventory; none supersedes its whole document:

- Scenario 31's first text-based query representation is superseded by the typed canonical query IR v2 in Scenario 32; the Scenario 31 profile analysis remains relevant.
- Scenario 32 §9's parser-state bridge sketch is superseded by the compiled Logos implementation in `PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/`; the query IR document remains relevant.
- The embedded ADR-0001 external-KV-authoritative proposal in `GIT-SEMANTIC-REPOSITORY.md` is historical and superseded by Proposed ADR-014 and `GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md`; the surrounding research remains background.

**Result:** three section-level cases are explicit; no entire document was marked superseded. This is not a complete semantic duplicate/orphan/contradiction audit.

### 2.8 Reproducibility instructions and CI coverage

The prototype READMEs and workflow definitions provide reproducibility instructions for the principal executable slices:

| CI suite | Pinned environment | Executed scope |
|---|---|---|
| Logos binding | Lean 4.34.0 | Lake build and `Main.lean` parser/source-query tests |
| Package identity | Python 3.11 | Unit-test discovery and byte-compilation |
| Package index | Python 3.11 | Unit-test discovery, byte-compilation, and provider benchmark at sizes 1,000 and 5,000 |
| QF_LIA profile | Python 3.12 | Compile Dependency Graph source/tests and run `test_qf_lia_profile.py` |
| Repository structure | Python 3.12 plus pinned `mpmath==1.3.0` and `sympy==1.14.0` | Repository-structure checks and the RT-04-01 test suite |
| Semantic dependency index | Python 3.11 | Selected identity, impact-planning, semantic-index, call-site, validation, and diff tests |
| Toolchain workspace | Python 3.12 | Compile Toolchain Server prototype and run `test_toolchain.py` |

The CI configuration is a reproducibility aid, not proof that every research artifact is covered. In particular, the Semantic Dependency Index workflow selects a subset of the Dependency Graph tests; the CLI workload and LLVM preservation prototypes have no dedicated job in the current `ci-required` workflow. Scenario reports also describe additional one-off commands and native-tool observations that are not all repeated by CI.

PR #88's merged head `ad49cb161e9abbd1eb65ea0fac0bafca843a9ea3` passed both Required CI and Required CI policy. The `logos-binding / lean-build-and-test` and `qf-lia-profile / focused-tests` jobs completed successfully, as did the other required suites. This CI run compiles the configured Lean proof modules and exercises the bounded parser/semantic tests; it does not execute every experiment or validate every artifact in the corpus.

### 2.7 Exact blob comparison

Git blob SHA comparison across the 450 inventory entries found one repeated blob:

| Blob SHA | Paths | Assessment |
|---|---|---|
| `d645695673349e3947e8e5ae42332d0ac3164cd7` | `research/references/snapshots/OCI/LICENSE-APACHE-2.0.txt`; `research/references/snapshots/REAPI/LICENSE-APACHE-2.0.txt` | Expected shared Apache-2.0 licence text; retain both colocated copies for snapshot attribution. |

No other byte-identical files were found by this Git-blob comparison. This does not detect near-duplicates, overlapping research, or superseded documents with different contents.


### 2.9 First bounded evidence audit — RT-03/04 Scenarios 97–108

The first claim/evidence pass reviewed the scenario reports, linked implementation and test modules under PROTOTYPES/RT-04-01, the shared COR-13 corpus description, and the preparation brief. The review distinguishes finite fixture results from source-language or production claims.

| Scenario | Claim checked against code/tests | Evidence supported | Boundary or finding |
|---:|---|---|---|
| 97 | Cleanup outcome composition across six candidate policies; ownership/debt projection | Twelve discriminators × six policies (72 observations); the test exhausts 13,230 finite combinations. The obligation auditor is a separate module and imports neither the operational composer nor its helpers. | Both sides share the fixture vocabulary and consume the same observation schema; this is an independent implementation check of ownership projection, not an independent language specification. Cleanup dispositions are inputs, not inferred native resource states. |
| 98 | Structural path coverage for a generated depth-3 binary AST | Seven condition markers, 128 concrete assignments, eight predicted paths; both RT-03 evaluators are compared with the path model on traces and final resources. | Hand-generated AST only; evaluator agreement and path coverage do not establish parser/CFG completeness. |
| 99 | Repeated marker identity across sequential branches | Two concrete assignments produce only TT/FF paths; focused path-model suite includes the regression. | Marker identity is assigned by the fixture; source name resolution, mutation, and general predicate equivalence remain outside scope. |
| 100 | Feasibility in a finite pure Boolean predicate IR | Exhaustive four-assignment domain yields three route vectors and replayable witnesses; unsupported forms fail closed. | Immutable Boolean fragment only; exactness comes from finite enumeration, not general symbolic reasoning or source extraction. |
| 101 | SymPy 1.14.0 DPLL2 against the same finite predicate IR | Solver route sets are compared with the truth-table analyzer and replayed against concrete evaluators; the report records a local conjunction-family timing table. | Integration gap: rt03_sympy_predicate_paths.py directly omits routes when SymPy returns False. The conservative result mapper added in Scenario 102 is a separate module and is not called by this adapter. Treat Scenario 101 as a bounded differential experiment, not a safe may-analysis/pruning interface. |
| 102 | SAT/UNSAT/UNKNOWN result handling and pruning basis | Replayed complete SAT models establish feasibility; timeout, unsupported/error, malformed or incomplete models remain UNKNOWN; UNSAT is accepted only with an explicit basis. | The mapper does not authenticate the caller-supplied UNSAT basis; its docstring leaves that to the caller. The current test_rt03_feasibility_outcomes.py contains eight test methods, while the report says seven focused tests passed. Reconcile the count or pin the historical test revision. |
| 103 | Real wall-clock timeout using an isolated SymPy worker | Four focused tests include a real 12-pigeon/11-hole timeout; the worker is killed/reaped and timeout remains UNKNOWN. Request IDs and one-process-per-query scope are visible in the implementation. | No memory/CPU/descendant bound, persistent worker pool, or broad crash/startup/malformed-response matrix; measured timings are machine-specific. |
| 104 | Predicate identity across a Boolean mutation | Three tests exhaust the two-value fixture and distinguish name-conflation, independent versions, and versions plus transition relation. | Hand-authored finite oracle; no source parser, SSA extraction, heap aliasing, loops, or concurrent writes. |
| 105 | Call mutation summaries | Five tests compare pure, toggle, may-write/unknown, and unsafe name-conflated summaries over all four before/after Boolean pairs. | Summaries are supplied by the fixture; no source-derived effect/call graph or dynamic dispatch. |
| 106 | Field-sensitive call-site alias sets | Five tests compare exact, disjoint, may-alias, unknown, and incorrect no-alias assumptions over the two-field fixture. | Alias sets and mutator footprint are supplied; no points-to analysis, heap graph, or source completeness proof. |
| 107 | Source-derived call aliases in a Python-shaped AST subset | The adapter recognizes one direct toggle mutator, propagates bounded reference targets through assignments/branch joins, and rejects unsupported constructs; tests include omitted-target and unsupported-source counterexamples. | This is not LLMLang parsing or general Python analysis. Concrete execution and extraction share the Python AST grammar and bounded semantic contract. |
| 108 | Path-sensitive alias precision | Ten tests compare joined may-alias and path-sensitive enumeration over 16 finite input combinations, including correlated and independent aliases. | Both executors share the AST grammar and toggle contract; fixed finite enumeration, not a scalable relational points-to analysis or independent source-to-CFG oracle. |

**CI evidence:** Required CI run 44767733362, commit 30a064cf5f276a63c2110f8309f7f306af75f987, completed the repository-structure / structure job successfully. Its Test RT-04 prototype 01 step ran python -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_*.py' -v after installing the pinned requirements-solver.txt; that step passed. At the time of this report, other Required CI jobs were still running, so the overall workflow was not yet complete.

**Audit result:** Scenarios 97–108 have traceable bounded implementation/test evidence, but none establishes general LLMLang source semantics or source-to-CFG completeness. The Scenario 101/102 solver-pruning boundary and Scenario 102 test-count discrepancy are recorded as open audit findings. The broader 104-file RT-04-01 suite passing CI is execution evidence for that checked-out test corpus, not proof of every research claim.


### 2.10 COR-13 and native FFI evidence — Scenarios 119–133

A second bounded pass cross-checked the scenario claims, named test modules, native-probe entry points, and the repository workflow. The reports describe a progression from static result-shape inference through SQLite dependency/close behavior, multi-resource role reservations, cancellation receipts, crash recovery, a shared owned-result workload, caller recovery, and generated Rust.

| Scenario(s) | Evidence represented in the reports and linked tests | Audit boundary |
|---:|---|---|
| 119 | AST-derived owned-result shapes compared with the COR-13 disposition model over 450 contract combinations and 4,096 fixture inputs; ten focused tests cover inference and caller matching. | One direct named call, two scopes, hand-built AST and shared disposition assumptions; no parser, general caller recovery, or native resource behavior. |
| 120–123 | SQLite 3.46.1 probes distinguish BUSY-retained connections, finalize-error consumption, deferred close, source/snapshot freshness, and caller-visible close outcomes. Scenario 121 reports 356 admitted native plans; Scenario 123 reports 114 native policy/input pairs. | Native probes are standalone scripts. The Required CI workflow does not invoke them; this audit did not rerun them. Reported return codes/callbacks remain manual experiment evidence pinned to the recorded SQLite source ID. |
| 124–125 | Two-thread scheduling across 11 schedules; callback reentry and dependency-coverage checks include statements, incremental BLOBs, and unfinished backups. | One SQLite version, bounded wrapper, controlled schedules and callback behavior; general FFI alias authority and broader dependent kinds remain open. Native harnesses are not CI-gated. |
| 126–128 | Multi-resource source/destination role model, 144 configurations per policy, source-correlated alias oracle over 147,456 inputs, and foreign outcome policies over 1,728 inputs per policy. SQLite probes cover overlapping backups and a consuming finish-error path. | Finite identities and declared role contracts; the native probe validates selected consuming outcomes, not every synthetic retained/indeterminate outcome. No general points-to or foreign contract extraction. |
| 129–130 | Invocation-specific cancellation evidence and durable receipts; scheduled two-thread tests plus ten process-interruption traces with file-backed SQLite. | CancelIoEx is API-documentation evidence; the fixture does not call the Windows API. Crash tests model a local SQLite journal, not distributed/external provider recovery. |
| 131–132 | Shared COR-13 workload compared by composed and direct-transition evaluators over 5,184 inputs; caller forwarding/recovery extended to 20,736 inputs per fixture. | The compared evaluators share the parsed fixture representation and disposition inputs. The independent test oracle is bounded to the same source fragment; no full-language lowering. |
| 133 | Generated Rust compared with the Python reference over 62,976 traces per optimization level (125,952 total at opt-level 0 and 3); Rust 1.85.1/LLVM 19.1.7 are recorded. | The CI test file checks the generator only and explicitly does not require a Rust toolchain. The native Rust compile/run command is separate and is not invoked by Required CI. This audit did not rerun it. |

**CI coverage boundary:** the successful Required CI repository-structure step runs unittest discovery over all RT-04-01 files named test_*.py. This covers the Python model/checker tests and the Rust generator's three tests. It does not execute sqlite_*_probe.py, the SQLite native matrix commands, or rt04_rust_owned_probe.py's native Rust compilation/comparison. A green Python suite therefore must not be cited as fresh reproduction of the native SQLite or Rust results.

**Audit result:** the corpus has layered evidence: finite model/test evidence, selected native SQLite observations, and one generated-Rust conformance report. The layers are linked but not equivalent. Native probes and Rust compilation remain manual, version-pinned evidence until a reproducible CI or captured-run protocol executes them. The next useful action is to make those commands reproducible in a controlled environment and retain machine-readable outputs; do not promote model-only cases to native guarantees.


### 2.11 Native reproduction preflight — SQLite packaging identity

The first execution of the new native workflow built upstream SQLite 3.46.1 from the official autoconf archive. The library reported source ID `2024-08-13 09:16:08 c9c2ab54ba1f5f46360f1b4f35d849cd3f080e6fc2b6c60e91b16c63f69a1e33`, while Scenarios 120–128 record the distribution build source ID ending `alt1`. The version number alone was therefore insufficient to claim an exact environment match. The runner correctly skipped all eight C-API probes; the durable-receipt probe and generated-Rust comparison both passed. The output artifact was uploaded as [run 44770125449](https://github.com/aivibeflow/LLMLang/actions/runs/44770125449).

The workflow has been changed to use the Ubuntu 26.04 distribution SQLite package, with the same exact source-ID preflight retained. This change is a hypothesis about obtaining the historical distribution build, not a verified result. The next run must confirm the package's source ID before any C-API probe can be counted as reproduced.


### 2.12 Successful native reproduction run — RT-04 Scenarios 120–133

The corrected workflow run [44770566744](https://github.com/aivibeflow/LLMLang/actions/runs/44770566744) completed successfully on commit `a4914f72bf9aaa03ffb33652c27e9ffa60bd152f`. The environment was Ubuntu 26.04.1, Python 3.12.14, Rust `1.85.1 (4eb161250 2025-03-15)`, and SQLite 3.46.1 with the exact source ID recorded by Scenarios 120–128: `2024-08-13 09:16:08 c9c2ab54ba1f5f46360f1b4f35d849cd3f080e6fc2b6c60e91b16c63f69aalt1`.

All ten runner commands passed with zero failures and zero skips:

- Eight C-API probes: base cleanup contracts, recovery matrix, snapshot freshness, close call boundary, close interleavings, callback reentry/dependent coverage, backup roles, and backup outcomes.
- Scenario 130 durable invocation receipts.
- Scenario 133 generated-Rust conformance.

The run uploaded [artifact 14647056715](https://github.com/aivibeflow/LLMLang/actions/runs/44770566744/artifacts/14647056715), containing the JSON environment/command manifest and per-command stdout/stderr. This is successful execution evidence for the exact C SQLite source ID and Rust version. The Python `sqlite3` runtime version for Scenario 130 is recorded in the manifest; its equality with the historical 3.53.1 baseline has not yet been inspected. Per-case stdout must still be compared with the numerical observations in Scenarios 120–133 before the scenario claims are marked fully reproduced.


### 2.13 Per-case comparison of native outputs — Scenarios 120–128 and 133

The workflow log for [run 44770910183](https://github.com/aivibeflow/LLMLang/actions/runs/44770910183) was compared with the corresponding scenario reports. The eight C-API probes used SQLite 3.46.1 with the exact recorded distro source ID and passed the following discriminators:

| Scenario | Captured native result | Comparison with report |
|---:|---|---|
| 120 | sqlite3_close with a live statement returned 5; finalization and later close returned 0; step/finalize after integer overflow returned 1; close_v2 returned 0 and the destructor count advanced from 0 to 1 only after finalization. | Matches the reported BUSY, consuming finalize-error, and deferred destruction observations. |
| 121 | Compared 356 admitted traces; rejected 154 plans before execution. | Matches the report's 356 native plans and 154 precondition rejections. |
| 122 | Empty snapshot closed successfully; an intervening prepare made close return 5; after finalize and a fresh empty observation, close returned 0. | Matches the reported snapshot-freshness discriminator. |
| 123 | Compared 114 call boundaries; source proof rejected 30 plans. | Matches the 114 admitted pairs and 30 source-proof rejections. |
| 124 | All 11 scheduled interleavings produced the model's expected observations. | Matches the report's 11-schedule matrix, including the shared-guard and split-validation races. |
| 125 | All 12 callback cases and all 8 dependent-kind/close-operation cases matched the model. | Matches the reported callback and statement/BLOB/backup coverage matrix. |
| 126 | Twelve shared-source backup traces ran; same-identity initialization was rejected; read/write destination transaction failures were followed by successful retry. | Matches the reported native role and initialization checks. |
| 128 | Writable destination: backup_step 101 and finish 0. Read-only destination: step 8 and finish 8. In both cases the source was destroyed at finish and destination remained usable. | Matches the report's consuming finish-error behavior. |
| 133 | 125,952 generated-Rust observations matched the Python reference: 62,976 at each of opt-level 0 and 3. The six per-fixture start counts also match the report: 1,856/2,576, 2,816/2,996, and 2,368/2,590. | Matches the reported native comparison totals and admission counts. |

**Scenario 130 version follow-up:** run 44770910183 first passed the durable-receipt cases on SQLite 3.46.1, which did not match the report's 3.53.1 runtime. The workflow then built SQLite 3.53.1 separately and selected it for the durable-receipt child process. The version-matched rerun 44771268838 also passed all ten commands; its runtime preflight reported Python 3.12.14 with SQLite 3.53.1 and source ID `2026-05-05 10:34:17 c88b22011a54b4f6fbd149e9f8e4de77658ce58143a1af0e3785e4e6475127e9`. The historical report records the version but not this source ID, so version matching is established, not byte-identical provenance.

The run uploaded [artifact 14648440097](https://github.com/aivibeflow/LLMLang/actions/runs/44770910183/artifacts/14648440097), with the manifest and command output. Scenarios 127 and 129 remain finite model/API-documentation evidence; Scenarios 131–132 remain bounded source-fixture/model evidence, not separate native executions.


### 2.14 Scenario 130 version-matched native rerun

The follow-up [run 44771268838](https://github.com/aivibeflow/LLMLang/actions/runs/44771268838) completed with all ten commands passed, zero failures, and zero skips. Its runtime manifest confirms Python 3.12.14 and the separately loaded Python sqlite3 3.53.1 runtime. The latter source ID is `2026-05-05 10:34:17 c88b22011a54b4f6fbd149e9f8e4de77658ce58143a1af0e3785e4e6475127e9`. The C-API probes still used the independent SQLite 3.46.1 distro build/source ID, and the generated Rust runner used Rust 1.85.1.

The durable-receipt probe reports all ten crash/recovery observations: the atomic path keeps the effect live through before_effect/after_effect/after_record, then commits the terminal record before delivery; the separate path records the effect as no longer live before the terminal record is committed, exposing the documented intermediate recovery states. Both complete with a terminal record and delivered result. The output identifies itself as Python sqlite3 library 3.53.1, matching Scenario 130's reported version. The new source ID is preserved in the artifact but cannot be compared with the historical run because that report did not record it.

Artifact [14647107612](https://github.com/aivibeflow/LLMLang/actions/runs/44771268838/artifacts/14647107612) contains the version-matched runtime manifest and all ten command outputs. Scenario 130 is now reproduced at the documented version level; its exact historical SQLite build identity remains unavailable.


### 2.15 Bounded evidence audit — Scenarios 109–118 and 134

The missing scenario slice was checked against its named prototype/test modules, current Required CI execution, the accepted architecture decision, and the draft glossary.

| Scenario | Implementation and test evidence | Supported result | Boundary |
|---:|---|---|---|
| 109 | optional_presence_model.py; 8 focused tests. | Distinguishes absent, explicit null, value, decode error, and uninitialized read. One-level Optional collapses absent/null; nested Optional and presence-bit-plus-nullable payload preserve the three valid states. | One integer JSON field only; not an LLMLang serializer, schema, type checker, ABI, or layout experiment. |
| 110 | schema_evolution_model.py; 6 focused tests. | A finite producer/consumer matrix checks v1/v2 field addition, consumer defaults, explicit false, null policy, and strict/permissive unknown-key handling. | One added Boolean field and JSON objects; no real schema registry, old binaries, migration, canonicalization, or ABI tests. |
| 111 | unknown_variant_model.py; 7 focused tests. | Reject, fallback/discard, and opaque-preservation policies are distinguished; nested unknown payload can be relayed semantically. | JSON sum-case fixture only; preservation is not byte-for-byte and no Protobuf/Avro/CBOR runtime was run. |
| 112 | scheduler_fairness_model.py; 5 focused tests. | Weak fairness excludes starvation for continuously enabled B; intermittent enablement can starve under weak but not strong fairness. Two-task round-robin selects an always-runnable B within the stated 0/1-turn bound. | Explicit finite cycles and fixed two-task policy; no real scheduler, executor, I/O, lock, crash, or liveness proof. |
| 113–117 | rt04_store_buffering.py; 12 shared focused tests across the memory-order fixtures. | Finite witnesses cover store buffering, message passing, lost-update prevention, read-read/write-write/read-write/write-read coherence, release-sequence relay, C++17/C++20 membership difference, and fence synchronization premise. | Axiom/premise-driven fixtures; no source extraction, full C++/Rust/Go model, compiler litmus, hardware execution, or LLMLang memory-model decision. |
| 116 | LLVM Language Reference and Atomic Instructions guide analysis; no executable backend test. | Relaxed→LLVM monotonic is a candidate mapping; unordered is too weak for the stated per-object coherence contract. Atomic widths and lock-free constraints are target-dependent. | LLVM documentation was unversioned and no compiler/target was run. Mapping and fallback policies remain hypotheses, not accepted lowering rules. |
| 118 | rt04_atomic_execution.py and test_rt04_atomic_execution.py; 7 focused tests. | Enumerates 4,096 layouts (two threads, two operations each, two locations, two order choices per operation); the interleaving oracle checks six schedules per layout. Global-order witnesses agree; weaker policy adds full witnesses in 242 layouts and read values in 98. | At most six operations, constant stores, direct release/acquire only. Independent oracle corroborates the global-order projection; weaker relations still need independent memory-model and compiler/target validation. |
| 134 | Analytical Protobuf/Avro/CBOR standards comparison; no runtime tests. | Shows compatibility is multidimensional and distinguishes parsing fingerprint, evolution policy, registry locator, and semantic wire contract. | The accepted architecture decision makes cross-version wire compatibility, schema negotiation, persisted-message migration, and unknown-field forwarding non-requirements for the current architecture. Do not implement the proposed runtime matrix unless a listed reconsideration trigger occurs. |

**CI evidence:** Required CI run [44771268684](https://github.com/aivibeflow/LLMLang/actions/runs/44771268684) passed all 364 RT-04-01 unittest-discovery tests. The run log contains the optional-presence, schema-evolution, unknown-variant, fairness, store-buffering, and atomic-execution tests listed above. This validates the checked-in finite models/tests in that revision; it does not turn them into source-language, scheduler, compiler, or hardware guarantees.

**Architecture and glossary cross-check:** [the accepted decision](../draft/ARCHITECTURE-DECISIONS.md) requires compatibility within a single coherent toolchain build and explicitly declines cross-version wire compatibility. It says the proposed Protobuf/Avro/CBOR runtime matrix must not be started unless independently built component exchange, cross-toolchain linking, dynamic loading, external RPC, persisted messages, or a separately versioned binary/plugin ABI is introduced. The [draft glossary](../draft/GLOSSARY.md) currently defines ContractHash, OpHash, ImplHash, CCHash, and optional CandidateSetHash; it does not define a wire-schema fingerprint. Scenario 134's wire identity dimensions must not be conflated with those semantic hashes. No new wire-hash glossary term is warranted while the accepted applicability boundary holds.

**Audit result:** Scenarios 109–111 and 112–118 have traceable bounded test evidence; Scenario 116 and 134 are explicitly source/standards analyses rather than executable claims. Scenario 134 is reference material under the accepted architecture decision, not an active implementation backlog item. The full corpus semantic audit remains open.


### 2.16 Evidence audit — Scenarios 89–96 and LLVM preservation follow-ups

| Scenario | Evidence reviewed | Supported conclusion | Boundary / remaining work |
|---:|---|---|---|
| 89 | ECMAScript 2026 automatic-semicolon-insertion specification compared with the Scenario 53 Go/Rust/Swift profiles. | ASI is grammar/parser driven and includes restricted productions; it adds relevant prior art for statement termination and formatter safety. | Proposed discriminating source pairs only. No ECMAScript parser/formatter or execution trace was run; no LLMLang separator policy selected. |
| 90 | Rust Hash, Swift Hasher, Python salted hashes, Go map iteration, and NIST FIPS 180-4 compared. | Runtime hash contracts, iteration order, stable fingerprints, cryptographic digests, and persistent artifact identity are separate concerns. | No cross-process/architecture/compiler experiment; no hash algorithm, width, seed, map order, or identity model selected. |
| 91 | Git object formats, OCI digests, IPFS CIDv1, semantic address layers, and digest migration alternatives. | Canonical representation, semantic content identity, digest suite, and logical lineage must remain distinct. | No canonical SPG envelope, digest suite, migration policy, or SCC scheme selected; LL-004/LL-005 remain open. |
| 92 | WIT, REAPI Action, Nix derivations, OCI descriptors, and candidate Operation/Interface/Contract/OpHash/Implementation/Binding/Action identities. | A semantic operation, a concrete implementation, and a build/test/proof action make different identity claims. | No OpHash envelope or binding model selected; no executable binding or compatibility test. LL-001 remains open. |
| 93 | REAPI Action Cache/CAS, Nix declared inputs/sandbox, GitHub Actions cache semantics, candidate ActionResult envelope and conservative reuse gate. | Exact Action identity, dependency completeness, environment control, cacheability, result completeness, evidence applicability, and producer trust are independent gates. | Candidate model only; no cache prototype or falsifying fixture executed. LL-021 remains open. |
| 94 | Go, Tokio, Erlang/OTP, Rust async, and Swift task-group fairness/lifetime contracts. | Preemption, weak/strong fairness, resource fairness, termination, and structured joining must not be conflated. | Analytical only; Scenario 112's five-test finite model is the bounded follow-up, not a real runtime fairness test or general liveness proof. |
| 95 | Executed comparative review of Rust diagnostics, LSP 3.18, TypeScript Language Service, Elm, and a 2024 human study; Q1–Q5 quality-gate assessment. | Diagnostic fact, presentation, transport, repair proposal, and authority/acceptance are separate contracts. | No LLMLang compiler/LSP, no structural fixtures executed, and no human-subject or coding-agent experiment. Q4 adversarial coverage is partial; no diagnostic schema or repair authority selected. |
| 96 | LLVM UB/poison/undef/freeze, Rust overflow/validity, WebAssembly traps, and candidate source-to-LLVM mappings. | LLVM verifier acceptance is structural, not proof of source-to-IR semantic correspondence; poison and source UB are not interchangeable. | No general lowering rule or LLVM backend role selected; LL-020 remains open. |
| 96A | Bounded native integer experiment: 20,978 comparisons at each O0/O3 (41,956 total), zero mismatches; verifier-accepted overflow mutant detected. | Tested fixed-width integer/error/effect mapping agrees with the Python reference for the declared fixture and LLVM 19.1.7 target. | One x86-64 target and bounded fixture; whole-domain proof, other targets, constant folding, and general translation validation remain open. |
| 96B | Bounded native byte-view experiment: 9,800 comparisons at each O0/O3 (19,600 total), zero mismatches; two verifier-accepted controls violate logical bounds/origin. | Logical view identity and end-pointer-versus-read distinction are preserved for the tested allocation/view fixture. | One live allocation and byte loads; general provenance, stale pointers, forged descriptors, and complete source-to-LLVM validation remain open. |

**LLVM experiment provenance:** Scenario 96A records pre-experiment baseline d58df1640caa72c1bed4e58f02ef78f89185bc7c and experiment source commit a80d94e795d8d2b613d01c09687c181df592c7f5. Scenario 96B records baseline a80d94e795d8d2b613d01c09687c181df592c7f5 and experiment source commit 2a9b6e5072efc542e823c529cf3cdee838f9ad36. The reports pin LLVM 19.1.7, Python 3.12.14, target/tool versions, per-experiment input IR SHA-256, and the Debian LLVM package SHA-256. These native runs are not part of Required CI.

A separate llvm-preservation job has now been added to the Research Native Reproduction workflow. It installs the exact Debian Trixie llvm-19 package 1:19.1.7-3+b1, verifies the package archive SHA-256 and toolchain versions, and reruns both probes. Its successful fresh execution is recorded in §2.17; the comparison matrices and negative controls match the reports.

**Cross-area status:** Scenarios 90–93 map to still-open identity/cache decisions (LL-004, LL-005, LL-001, LL-021); Scenario 95 remains partial research; Scenario 96 informs LL-020 but does not settle backend selection. These reports must not be promoted into normative language rules or accepted architecture decisions without the corresponding review.


### 2.17 Fresh LLVM preservation reproduction — Scenarios 96A/96B

The llvm-preservation job in [Research Native Reproduction run 44773422416](https://github.com/aivibeflow/LLMLang/actions/runs/44773422416) passed both native probes. The environment matched the recorded toolchain: Debian Trixie/glibc 2.41, Python 3.12.14, libffi 3.4.8, Debian llvm-19 package 1:19.1.7-3+b1, GCC 14.2.0, and GNU ld 2.44. The downloaded Debian package SHA-256 matched the report exactly: 0b1b7263f4f45e261099240fdbf00fc14b42b88410fd829e041bf83ea45866cb. Both probes use the explicit x86_64-unknown-linux-gnu triple, x86-64 CPU, PIC, and O0/O3 pipelines.

- **96A integer preservation:** 20,978 traces at O0 and 20,978 at O3, zero mismatches. Outcome counts per level were ok 17,552; overflow 1,765; shift_count 1,566; zero_divisor 95. The verifier-accepted missing-overflow-branch mutant disagreed at the signed-maximum witness. Three unsupported source forms and one invalid dominance relation were rejected. Input IR SHA-256 matched the report: c46111f6b77eb621a5c154b17645044e1d76c7cb2808fe80189a63f447dc173d.
- **96B byte-view preservation:** 9,800 traces at O0 and 9,800 at O3, zero mismatches. Outcome counts per level were bounds 4,100; ok 580; overflow 1,200; wrong_origin 3,920. The verifier-accepted one_past_read and erased_origin controls disagreed with the source reference. Input IR SHA-256 matched the report: ddb41ceb866c77e957df865cd2102f7a02d3a468150fc82f79c7a7fb2bf782d0.

Artifact [14647744441](https://github.com/aivibeflow/LLMLang/actions/runs/44773422416/artifacts/14647744441) preserves the runtime manifest and both probe outputs. This is a fresh reproduction of the recorded fixtures and toolchain on the current PR revision. It does not expand the claim beyond the fixed x86-64 fixture, target, integer/view operations, and O0/O3 configurations.


### 2.18 Specification-level prior-art audit — Scenarios 81–88

| Scenario | Research question and cross-links | Evidence status | Decision/implementation boundary |
|---:|---|---|---|
| 81 | Import binding syntax, aliases, wildcard imports, re-exports, scope, and compile-time versus runtime loading; scoped against Scenario 43 module/package behavior and Scenario 50 name resolution. | Comparative language-specification review of Rust, Go, Swift, Java, and Python; proposed discriminating fixtures only. | No import syntax, path form, wildcard policy, or re-export model selected; no LLMLang parser run. |
| 82 | Source-file structure, header/prelude, imports, declarations, top-level statements, and file-to-module relationship; cross-linked to Scenarios 43 and 81. | Comparative source-file grammar review of Go, Rust, Java, Swift, and Kotlin. | No file layout, package/module identity, initialization, or entry-point spelling selected; no parser/compiler experiment. |
| 83 | Numeric token grammar, radix prefixes, separators, decimal/hex floats, suffixes, and sign representation; explicitly separated from numeric typing/conversions (73) and runtime floating-point behavior (78). | Comparative lexer/specification review of Rust, Go, Swift, and Zig; fixture proposals only. | No numeric token grammar, suffix policy, radix set, or sign model selected; no target lexer benchmark or conformance run. |
| 84 | Function signature/call surface: labels, receiver, variadics, defaults, return form, overloads, and external declarations; separated from argument sequencing (77), higher-order types (58), closures (56), and generic dispatch (42). | Comparative language-specification review of Rust, Go, Swift, and Java. | No signature or call syntax selected; no compiler or API-compatibility experiment. |
| 85 | Local binding declaration syntax, mutability markers, initialization, inference, redeclaration, destructuring, and scope; cross-linked to Scenarios 50, 60, 67, 68, and 74. | Comparative prior-art review of Rust, Go, Swift, and Zig; proposed discriminators only. | No declaration spelling, redeclaration/shadowing rule, or initialization policy selected; no type-checker/parser run. |
| 86 | Async declaration markers, await operator placement/scope, async closures/blocks, propagation, and top-level await; explicitly separates syntax from runtime/task semantics in Scenarios 40, 57, and 58. | Comparative grammar/context review of Rust, Swift, C#, and ECMAScript 2026. | No async syntax, context inheritance, cleanup restriction, or top-level await rule selected; no runtime comparison. |
| 87 | Language-neutral parser/diagnostic corpus for await contexts, precedence, line breaks, module goals, cleanup, and protected critical sections. | Corpus design with 13 discriminating fixture IDs and normalized diagnostic fields. | No LLMLang grammar, adapter, fixture execution, or diagnostic wording chosen; this is a proposed experiment plan. |
| 88 | Default-argument evaluation epoch, lookup environment, effects/order, mutable-value reuse, dispatch/version source, and API compatibility. | Comparative specification review of Swift, Kotlin, Python, and C++; explicit experiment designs only. | No default-argument policy, call-site lowering, effect restriction, or source/binary compatibility promise selected; no compiler/runtime experiment. |

**Architecture cross-check:** none of Scenarios 81–88 has a corresponding accepted decision in draft/ARCHITECTURE-DECISIONS.md. Their candidate axes remain research inputs, not normative language behavior. Their sources are primarily rolling language references updated 2026-11-19; any later conformance suite must pin the exact language/spec/compiler versions before interpreting differences as regressions.

**Audit result:** this slice is correctly classified as specification-level research and experiment preparation, not implementation evidence. Scenario 87 is a fixture design, not a passing parser test suite; Scenario 88's proposed discriminator cases are not executed results.


### 2.19 Specification-level prior-art audit — Scenarios 73–80

| Scenario | Scope checked | Evidence classification and boundary |
|---:|---|---|
| 73 | Numeric literal typing, exact/untyped compile-time constants, runtime numeric conversions, and mixed-expression peer typing. | Comparative language-reference analysis (Go, Zig, Swift, Rust) plus proposed discriminators. No LLMLang lexer/type checker, compiler matrix, or numeric conformance tests were executed. No literal, conversion, or peer-type policy selected. |
| 74 | Refutable pattern failure, binding availability, definite assignment, and control-flow behavior across branch, exit-on-failure, Boolean-test, and value-level forms. | Comparative specification analysis (Rust, Swift, Go, C#) and experiment design. No LLMLang parser/type checker or ownership-aware partial-match experiment. No failure/binding policy selected. |
| 75 | Automatic disposal triggers, ownership-bound drop, lexical defer, ARC, GC finalizers, and cleanup failure/reentry/async boundaries. | Comparative language/runtime documentation and six proposed discriminators. No executable resource-lifetime prototype or native cleanup experiment in this scenario. No disposal policy selected. |
| 76 | Regex dialect, worst-case resource bounds, matching priority, captures, Unicode, offsets, cancellation, and compilation identity. | Comparative API/reference review and adversarial-pattern experiment plan. No regex engine benchmark, resource-bound measurement, or LLMLang API test. No dialect/engine selected. |
| 77 | Function-call argument sequencing, nested calls, conversions/defaults, preconditions, abrupt outcomes, and async task-body start. | Comparative specification review and common effect-trace corpus design. No compiler matrix or optimizer experiment was run; no permitted-outcome set was measured. No evaluation-order rule selected. |
| 78 | Floating-point formats, IEEE edge behavior, rounding, NaN/signed zero, relaxed math, and cross-target reproducibility. | Comparative documentation review, candidate profiles, and falsifiers. No target/compiler matrix or bitwise reproducibility experiment. No float profile or determinism guarantee selected. |
| 79 | String/byte literal syntax, raw delimiters, escapes, Unicode, interpolation, conversion/effect behavior, and context-specific escaping. | Comparative syntax/security analysis and discriminator design. No LLMLang lexer, formatter, interpolation evaluator, or security test was run. No literal/interpolation syntax selected. |
| 80 | Comments, doc-comment attachment, build directives, newline/trivia behavior, source maps, and semantic/artifact hash boundaries. | Comparative language/tool documentation and open-question analysis. No lexer, formatter, documentation generator, directive parser, or hashing prototype was run. No comment/doc/trivia policy selected. |

**Cross-scenario boundaries:** Scenario 73 keeps lexical numeric formation separate from conversion/type rules and Scenario 78 runtime IEEE behavior. Scenario 74's binding/failure policy interacts with ownership and cleanup but does not select it. Scenario 75 distinguishes deterministic resource cleanup from memory reclamation. Scenario 76 treats regex complexity as an API/resource contract, not merely syntax. Scenario 77 is distinct from short-circuit semantics (Scenario 59) and async/task semantics (Scenarios 40, 57–59). Scenario 79 keeps Text versus Bytes (Scenario 46) and destination-context escaping separate. Scenario 80 coordinates comment newlines with statement separation (Scenario 53) and separates documentation/provenance outputs from executable semantics.

**Architecture cross-check:** these eight reports provide research axes and candidate experiments, not accepted language decisions. No corresponding accepted decision was found in `draft/ARCHITECTURE-DECISIONS.md`. Their rolling/version-sensitive references must be pinned before a future implementation conformance suite. This pass classifies the evidence; it does not independently revalidate every external source citation.


### 2.20 Final PR validation run — RT-04 and LLVM

The final focused Research Native Reproduction workflow run before PR #97 was merged completed successfully on PR merge-ref commit `8c4a82c91f039309bba769c49bd00515e3713feb` (the merge of PR head `0496ad43783bc86105dd617fdc4d679cdf4637b8` into base `4d7580504962d60bb98e29127eae39263c84bb0c`). PR #97 was merged as `b808c3a8f984bbc5c175ecf45d61e0e8db7a00bb`; Required CI on that main commit passed.

- **RT-04 native job:** run [44774296240](https://github.com/aivibeflow/LLMLang/actions/runs/44774296240), artifact [14650095720](https://github.com/aivibeflow/LLMLang/actions/runs/44774296240/artifacts/14650095720). All 10 commands passed, zero failed/skipped. SQLite C probes used 3.46.1 and the recorded distro source ID; durable receipts used Python 3.12.14 with SQLite 3.53.1 and the newly recorded source ID; generated Rust used rustc 1.85.1 and all 125,952 observations matched.
- **LLVM job:** the same run's artifact [14650040345](https://github.com/aivibeflow/LLMLang/actions/runs/44774296240/artifacts/14650040345) records both probes passing. Integer preservation: 20,978 traces per optimization level; byte-view preservation: 9,800 traces per level. Both O0/O3 runs had zero mismatches, and the expected negative controls disagreed with the source reference.
- The manifests identify the tested checkout as merge-ref commit `8c4a82c...`; do not label these artifacts as execution on the final main merge commit `b808c3a...`. The final main commit did receive a successful Required CI run [44774552406](https://github.com/aivibeflow/LLMLang/actions/runs/44774552406).

This rerun strengthens reproducibility confidence for the same bounded fixtures and pinned dependencies. It does not broaden target coverage, prove production FFI behavior, or promote the separate native workflow into Required CI.


### 2.21 Specification-level prior-art audit — Scenarios 65–72

| Scenario | Scope checked | Evidence classification and boundary |
|---:|---|---|
| 65 | Fatal failure, panic/assertion/abort distinctions, stack unwinding, cleanup, child-task/process boundaries, and FFI unwind behavior. | Comparative prior-art analysis (Rust, Go, Swift, Zig) and six discriminating experiments. The report does not identify an executed LLMLang prototype or runtime experiment. No fatal-failure, double-fault, supervision, or FFI-unwind policy selected. |
| 66 | Copy/move/clone/borrow, shallow versus deep copying, reference-bearing descriptors, capture, COW, and physical copy elision. | Comparative prior-art analysis (Rust, Go, Swift, Zig) and six proposed experiments. No executed LLMLang assignment/parameter/return prototype or ABI benchmark is cited. No value-flow policy selected. |
| 67 | Binding reassignment, direct and alias mutation, deep immutability, interior mutability, constants, and concurrency distinction. | Comparative prior-art analysis (Rust, Go, Swift, Zig) and six proposed experiments. No LLMLang mutability checker, alias experiment, or optimizer evidence is cited. No mutability model selected. |
| 68 | Complete initialization, zero/default values, constructors/builders, partial construction failure, escape prevention, and invariant preservation. | Comparative prior-art analysis (Rust, Go, Swift, Zig) and six proposed experiments. No LLMLang construction checker, runtime probe, or API-evolution experiment is cited. No construction/initialization contract selected. |
| 69 | Nominal versus structural compatibility, subtyping/assignability/coercion, generic variance, function variance, and mutable-container safety. | Comparative prior-art analysis (Rust, Java, Go, Swift) and six proposed experiments. No LLMLang type-checker, generic inference, or compatibility matrix is cited. No subtyping/variance rule selected. |
| 70 | Type aliases, nominal newtypes, opaque abstraction, representation guarantees, and source/binary/wire compatibility. | Comparative prior-art analysis (Rust, Go, Swift, Zig) and six proposed experiments. No LLMLang type identity, layout, or cross-version ABI experiment is cited. No alias/newtype/opaque representation policy selected. |
| 71 | Interface/trait conformance ownership, orphan/coherence rules, overlap, structural satisfaction, lookup scope, and package evolution. | Comparative prior-art analysis (Rust, Go, Swift, Haskell) and seven proposed experiments. No LLMLang conformance resolver, separate-compilation, or dependency-upgrade experiment is cited. No implementation ownership/coherence policy selected. |
| 72 | Sum-type tag/payload layout, niche optimization, calling convention, foreign representation, invalid encodings, and evolution. | Comparative prior-art analysis (Rust, Zig, Swift, C) and six proposed experiments. No LLMLang cross-target layout/ABI probe or version-skew interoperability test is cited. No sum-type ABI profile selected. |

**Cross-scenario boundaries:** Scenario 65 distinguishes recoverable errors (64) from fatal failure and process termination. Scenario 66 separates source-level value/reference behavior from physical copies and ABI. Scenario 67 separates binding immutability, object/graph immutability, and race safety. Scenario 68 treats valid construction as an invariant and connects partial initialization to cleanup (65) and ownership (66). Scenario 69 separates type compatibility from behavioral substitutability (14) and implementation ownership/coherence (71). Scenario 70 separates nominal identity from layout/ABI and connects to Scenario 72. Scenario 71 is the ownership/lookup side of generic dispatch and coherence, not merely method syntax. Scenario 72 separates source-level sum-type semantics and exhaustiveness (47, 54) from target representation and foreign ABI.

**Architecture cross-check:** the eight reports state that no LLMLang policy is selected. Their candidate axes and proposed experiments are research inputs, not normative language behavior. Their external references are primarily rolling or version-sensitive; pin language editions, compiler releases, target triples, and ABI before treating future measurements as conformance evidence.


### 2.22 Specification-level prior-art audit — Scenarios 57–64

| Scenario | Scope checked | Evidence classification and boundary |
|---:|---|---|
| 57 | Structured child-task lifetimes, supervision, cancellation/join, failure propagation, and explicit detachment. | Comparative prior-art analysis and task-tree experiment design. No LLMLang task runtime or task-handle implementation is cited. Scenario 40 covers cancellation/cleanup; Scenario 112 later provides only a finite abstract fairness model. No task hierarchy or spawn policy selected. |
| 58 | Async function types, eager/lazy body start, future construction, task creation, scheduling, suspension, and parallelism. | Comparative prior-art analysis and proposed event-trace/runtime matrix. No LLMLang async lowering, executor, scheduler, or compiler/runtime experiment is cited. No async type or execution policy selected. |
| 59 | Boolean short-circuiting, strict operator order, effects/errors/divergence, overloads, and optimizer freedom. | Comparative prior-art analysis and proposed effect-trace/optimizer corpus. No LLMLang operator implementation or compiler optimization differential test is cited. No short-circuit/evaluation-order policy selected. |
| 60 | Local/generic/contextual inference scope, annotation boundaries, ambiguity, solver budgets, diagnostics, and interface hashing. | Comparative prior-art analysis and proposed matched compiler/human-agent corpus. No LLMLang inference compiler measurements or annotation-repair experiment is cited. No inference boundary selected. |
| 61 | Shared mutable state, data races versus logic races, ownership/isolation, synchronization, memory order, and unsafe/FFI escapes. | Comparative prior-art analysis and litmus-test design. Scenario 113 adds bounded abstract store-buffering observations, but is not a complete LLMLang memory model or hardware/compiler conformance suite. No concurrency-safety or memory-order model selected. |
| 62 | Optional values, nullable references, absence versus failure/uninitialized state, nesting, layout, and FFI. | Comparative prior-art analysis. Scenario 109 adds an eight-test JSON presence round-trip model for absent/null/value; it does not settle language optional types, runtime representation, or FFI. No absence/nullability policy selected. |
| 63 | Value equality, reference identity, partial/equivalence relations, comparability, hash compatibility, ordering, NaN, and Unicode. | Comparative prior-art analysis and proposed value/key corpus. No LLMLang equality/hash implementation, collection contract, or stable-hash experiment is cited. No equality/identity policy selected. |
| 64 | Error values versus propagation control flow, context/cause identity, classification, recovery, and public API boundaries. | Comparative prior-art analysis and proposed call-graph/error-injection experiments. Scenario 97 later exercises finite cleanup-error composition, but does not select general error propagation or cause-privacy semantics. No error policy selected. |

**Cross-scenario boundaries:** Scenario 57 task lifetime is separate from cancellation/cleanup (40) and fairness (112). Scenario 58 separates async function values from spawned tasks and scheduler behavior (57). Scenario 59's conditional right-operand rule is distinct from general call argument ordering (77). Scenario 60 inference must be reconciled with generic dispatch (42), signatures (84), and interface hashing. Scenario 61 distinguishes memory data races from higher-level race conditions; Scenario 113 is a finite abstract store-buffering slice only. Scenario 62 keeps absence distinct from error (64) and uninitialized state; Scenario 109's JSON presence encoding is only a serialization model. Scenario 63 equality/hash contracts are relevant to semantic identity but do not determine the hash schema. Scenario 64 recoverable errors remain distinct from fatal failure/unwinding (65); Scenario 97 covers only cleanup composition.

**Architecture cross-check:** these reports leave the corresponding LLMLang policies open. The linked later models (109, 112, 113, and 97) provide bounded evidence for selected subquestions only and must not be promoted to complete runtime/type-system contracts.


### 2.23 Specification-level prior-art audit — Scenarios 49–56

| Scenario | Scope checked | Evidence classification and boundary |
|---:|---|---|
| 49 | Operator inventory, precedence/associativity, overloads, conversions, and parse/evaluation agreement. | Comparative prior-art review and proposed parser/type-checker/evaluator/formatter fixture. No LLMLang precedence table, operator resolver, or parse/evaluation differential experiment is cited. No operator/coercion policy selected. |
| 50 | Name introduction/visibility, nested and module scopes, shadowing, namespaces, imports, prelude, and declaration order. | Comparative prior-art review and proposed minimal resolver profiles. Later RT-03 source-alias fixtures (Scenarios 107–108) do not implement this complete name-resolution model. No LLMLang name-resolution policy selected. |
| 51 | Module/package access control, exports, re-exports, interface construction, and public-signature restrictions. | Comparative prior-art review and proposed access-check extension to Scenario 50 fixtures. No LLMLang visibility checker or module-interface export experiment is cited. No access/export policy selected. |
| 52 | Unicode identifier repertoire, normalization, Unicode-version compatibility, confusables, and source/tooling safety. | Comparative language/Unicode standards review and proposed lexer/security/usability corpus. No LLMLang lexer run, Unicode-version matrix, or confusable audit is cited. No identifier/security profile selected. |
| 53 | Statement termination, explicit terminators, newline-sensitive parsing/ASI, continuation, comments, and block results. | Comparative prior-art review and two-parser-prototype experiment design. No LLMLang parser prototype or formatter round-trip experiment is cited. No statement-termination policy selected. |
| 54 | Pattern repertoire, exhaustiveness, guards, wildcard/future variants, and ownership of matched payloads. | Comparative prior-art review and finite-ADT prototype proposal. No LLMLang pattern parser/type checker or exhaustiveness experiment is cited. No pattern/exhaustiveness policy selected. |
| 55 | Loop forms/results, labels, break/continue targets, control transfer, and cleanup. | Comparative prior-art review and CFG/typing prototype proposal. No LLMLang loop CFG/type checker or cleanup-on-transfer experiment is cited. No loop/control-transfer policy selected. |
| 56 | Closure capture modes, callability cardinality, escaping lifetime, identity, and concurrency transfer. | Comparative prior-art review and bounded closure type/lifetime prototype proposal. No LLMLang closure type/lifetime implementation or async capture experiment is cited. No closure/capture policy selected. |

**Cross-scenario boundaries:** Scenario 49 separates parse grouping, operand evaluation, type-directed operator selection, and implicit conversion. Scenario 50 is the base for access checking (51) and affects dependency extraction/invalidation. Scenario 52 is lexical/source-integrity policy, not identifier-to-symbol resolution (50). Scenario 53 must coordinate comment/newline behavior (80) and block-result/control-flow rules (55). Scenario 54's exhaustiveness is distinct from refutable binding failure (74). Scenario 55 must preserve cleanup obligations on all exits (65, 75). Scenario 56 links function values and ownership to async/task capture (57–58) and copy/move semantics (66).

**Architecture cross-check:** the reports retain these choices as unresolved research questions. Candidate profiles and experiment proposals are not accepted LLMLang grammar, type-system, or runtime contracts. Pin the relevant language/compiler/Unicode versions before implementing conformance tests.


### 2.24 Specification-level prior-art audit — Scenarios 41–48

| Scenario | Scope checked | Evidence classification and boundary |
|---:|---|---|
| 41 | Typed error representation, error-set precision, handling obligations, unknown cases, and source/ABI/API evolution. | Comparative prior-art and compatibility analysis. Later Scenario 97 exercises finite cleanup-error composition and Scenario 109–111 exercise selected wire cases, but neither implements the general typed-error/API evolution contract. No LLMLang error model selected. |
| 42 | Generic constraints, trait/interface dispatch, existential/dynamic abstraction, coherence, specialization, and dictionary identity. | Comparative prior-art analysis and shared-fixture experiment plan. Scenarios 69 and 71 later isolate variance and conformance coherence; no LLMLang generic mechanism or dispatch implementation is selected by this report. No compiler matrix or emitted-representation experiment is cited. |
| 43 | Module/package boundaries, imports/re-exports, initialization effects, cycles, dynamic providers, and dependency identity. | Comparative prior-art analysis and proposed resolver/dependency prototype. Later source-alias fixtures (107–108) cover a restricted Python adapter, not a module system or initialization graph. No LLMLang module policy selected. |
| 44 | Compile-time execution, syntax/AST macros, phase separation, sandboxing, deterministic expansion, provenance, and build capabilities. | Comparative prior-art/security analysis and proposed pinned-toolchain prototype. No LLMLang macro/comptime evaluator, sandbox, or expansion-provenance implementation is cited. No metaprogramming or trust model selected. |
| 45 | Integer width/overflow, arithmetic traps/wrapping, floating-point modes, target variance, and proof/backend correspondence. | Comparative prior-art analysis and language-neutral outcome fixture design. Scenarios 96A/96B later provide bounded LLVM integer/byte-view preservation experiments, but they do not cover the complete numeric profile or floating-point semantics. No LLMLang numeric profile selected. |
| 46 | Text versus bytes, encoding validity, indexing/iteration units, normalization, equality, and Unicode-version/hash boundaries. | Comparative prior-art analysis and proposed Text/Bytes API corpus. No LLMLang string API, Unicode conformance, normalization, or indexing experiment is cited. No string model selected. |
| 47 | Public record/variant evolution, field/case additions, openness/frozen policies, source/ABI/wire compatibility, and identity. | Comparative compatibility analysis. Scenario 110 later tests selected old/new JSON producer-consumer defaults; it does not establish source API or ABI compatibility. No LLMLang public data-type evolution policy selected. |
| 48 | Wall-clock instants, monotonic elapsed time, suspend accounting, deadlines, timers, timezone data, and virtual-clock testing. | Comparative prior-art analysis and proposed cross-platform injected-clock experiment. No LLMLang clock/timer API or OS/runtime timing measurement is cited. No time model selected. |

**Cross-scenario boundaries:** Scenario 41 separates recoverable typed errors from fatal failure (65) and general propagation/recovery (64). Scenario 42 is refined by variance (69) and implementation ownership/coherence (71), but none alone selects generic dispatch. Scenario 43 connects names/scope (50), access control (51), and dependency extraction. Scenario 44 separates deterministic macro expansion from sandbox/security guarantees and provenance. Scenario 45's LLVM preservation studies (96A/96B) cover selected integer/view operations, not floating point or all arithmetic. Scenario 46 distinguishes text validity/indexing from identifier security (52) and string literal syntax/interpolation (79). Scenario 47's wire-format follow-up (110) is not source or ABI evolution. Scenario 48's clock API questions are distinct from a timer widget or host clock measurement; the report itself contains no target timing experiment.

**Architecture cross-check:** the reports explicitly leave the corresponding LLMLang policies open. Related later experiments are narrow evidence for individual subquestions and do not close these language-level decisions.


### 2.25 Executable/formal evidence audit — Scenarios 33–40

| Scenario | Implementation and validation evidence | Supported claim | Unresolved boundary |
|---:|---|---|---|
| 33 | Pinned Logos CPC parser-state wrapper, fail-closed declaration binder, typed query AST, independent Eo.Term renderer, and strict version-2 canonical JSON decoder; Logos-binding CI. | Exact parser-state-derived UConst identities are bound to the declared factor symbols; the complete ordered assumption list is structurally compared, and the factor-pair inequality is independently reconstructed/checked. | This is a parser/query binding contract, not a source-program-to-query semantic proof. The CPC proof checker was not run on a generated proof in the report; Logos/Lean revision and CI run must be read from the specific scenario sections. |
| 34 | Lean formalization of the checked Int/Bool fragment and canonical relational formula; QF_LIA profile/admissibility checks and adversarial rejection fixtures. | The report states a formal satisfiability/counterfactual-dependence correspondence for the delimited fragment, with lowered terms in the strict QF_LIA profile. | Solver-facing declaration closure, JSON correspondence, and source-derived CPC binding remain open. No claim extends to arbitrary LLMLang programs or cvc5 correctness. |
| 35 | rt03_return_cleanup.py and related return/cleanup fixture projection; selected compatible cleanup portions are cross-checked against evaluator/path-model outputs. | The fixture distinguishes staged versus transfer-first ownership, cleanup success/failure, returned value/error observations, and owner state across named cases. | Transfer rules are encoded by one model and observations are hand-specified; no static borrow checker, full source/SPG call binding, branch-sensitive ownership proof, async/FFI semantics, or general source correspondence. |
| 36 | rt03_recursion_fuel.py, rt03_fuel_cleanup.py, rt03_fuel_owned_return.py, independent owner-state audit, and cleanup-fuel stack probe. | One recursive countdown uses the abstract cost 4*n+2; a divergent loop exhausts every finite budget while divergence remains separate metadata. Fuel/cleanup probes compare fixed reserve, depleted cleanup fuel, staged return, and transfer-first observations. | Fuel modules have no dedicated paired test module in the 44-file suite (per README); selected direct-run probes are not a termination checker, machine gas, runtime fuel semantics, or complete effects/cleanup model. One comparison was explicitly run without a full test suite. |
| 37 | RT-03 A/D evaluators, deterministic fixture handlers, observable traces, COR-10 state-handler and COR-11 actor-schedule models/tests; RT-04 declaration checker has effect-bound summaries. | The bounded models distinguish declared effect bounds from realized ordered events and expose finite handler/actor outcomes with replayable traces. | Effect-row syntax/unification and general algebraic handlers are not implemented; call-graph completeness is fixture-asserted, not authenticated. Actor schedules are finite scripts, not a production scheduler or complete effect semantics. |
| 38 | rt04_model.py effect/capability propagation, scoped grant/delegation/revocation fixtures and tests; separate RT-16 authorization prototype. | The checker can reject known out-of-bound effects, require explicit call-site grant delegation, validate scoped grant ancestry and fail closed to UNKNOWN on missing completeness/delegation evidence. | It is a declaration-level checker over supplied calls/grants, not a source type checker or runtime authorization boundary. Capability possession, runtime import availability, actual effect execution, and trust in completeness evidence remain distinct. |
| 39 | Comparative cleanup/ownership-transfer report; related return-disposition and owned-call models in RT-04-01 plus COR-13/Scenario 97 follow-ups. | Later bounded fixtures explore selected transfer timing, cleanup-error composition, and caller-visible owner/result states. | Scenario 39 itself is a language-mechanism comparison, not executable cross-language conformance. The related models do not select one cleanup/ownership policy or prove general ownership correctness. |
| 40 | Synchronous cancellation semantics in RT-03 evaluators; separate rt04_cancel_receipts.py process/scheduled-worker model and Scenario 129 tests. | The synchronous evaluator distinguishes cancellation from Result errors and preserves prior effects; Scenario 129 checks finite cancellation reservation/receipt outcomes and late results after role reuse. | Neither establishes general asynchronous cancellation semantics, cancellation propagation, cleanup completion before join, async destructors, or external I/O rollback. Runtime-specific references remain guidance, not language guarantees. |

**Cross-scenario evidence boundary:** the later RT-04-01 README and tests link several studies into a coherent finite corpus, but shared fixtures and explicit completeness inputs remain trust boundaries. Scenario 33's exact syntax binding is not the source semantics theorem required by Scenario 34. Scenario 34's theorem is conditional on the checked fragment and observation model. Scenarios 35/39/40/97 form a resource-return/cleanup/cancellation sequence, not interchangeable or superseding studies. Scenario 36's abstract source fuel is distinct from runtime metering and verifier timeouts. Scenarios 37/38 separate static effect bounds, authority grants, runtime availability, and observed traces.


### 2.26 Formal dependency-analysis and proof-pipeline audit — Scenarios 25–32

| Scenario | Implementation and validation evidence | Supported claim | Unresolved boundary |
|---:|---|---|---|
| 25 | Research/architecture analysis of formal semantic dependency derivation and proof obligations; no implementation result is claimed by the report. | Establishes a proposed formal direction and separates semantic dependence from observed/candidate dependence. | Proposal only; no source semantics, dependency proof engine, or soundness theorem is implemented. |
| 26 | Python finite deterministic core and exhaustive paired-execution analyzer over a declared finite input domain, with selected tests against pair enumeration. | Can produce replayable influence witnesses or independence only within the exact finite domain, initial state, deterministic semantics, and observation boundary. Unsupported constructs/resource exhaustion yield UNKNOWN. | No machine-checked proof of the Python evaluator/analyzer, unbounded or SMT proof, complete type checker, source-to-IR correspondence, loops/recursion/concurrency/pointers/foreign calls, or machine arithmetic. |
| 27 | Symbolic relational query/SMT-LIB backend prototype. | Constructs candidate relational queries with independent factor inputs and shared non-factor inputs; emits witnesses/query text for the restricted model. | The report explicitly says actual Z3 integration was not executed. Solver-reported UNSAT is not independent proof evidence; no persistent proof record/cache identity. |
| 28 | Typed IR validation and proof-boundary prototype. | Separates IR validity, explicit observation boundary, and query/toolchain identity as obligations before accepting solver evidence. | Independent SMT proof checking is not implemented; candidate validation does not establish encoder soundness or source correspondence. |
| 29 | logos_runner.py process-boundary adapter with 15 tests using fake executables; executable hashes, CPC invocation, proof-byte preservation, timeout, and fail-closed status mapping. | Tests the host process boundary and deliberately returns CHECKER_REPORTED_CORRECT_UNBOUND rather than PROVEN_INDEPENDENCE. | No real cvc5 or Logos binary was available for the reported test; no actual proof integration, assumption binding, or source/query theorem. |
| 30 | Source-level audit of pinned Logos parser/API and CPC assumption representation. | Identifies that source spellings are not enough to bind proof assumptions; retained parser declaration state and exact uninterpreted-constant identity are needed. | The report itself records no compiled wrapper or real proof integration. Scenario 33 later implements a bounded parser-state binding/decoder, but source-program-to-query correspondence remains open. |
| 31 | Strict QF_LIA profile design and local implementation against a compatibility fixture; 26 focused tests and compileall passed. | Defines conservative Bool/Int-only candidate query construction and rejects unsupported constructs/nonlinear multiplication before emitting QF_LIA. | Local tests were not run against a complete repository checkout; no solver invoked, no Logos-Term renderer, no source-to-query theorem, and no PROVEN status. Scenario 32/34 provide later typed-IR and formal-fragment work, not a general proof. |
| 32 | Python typed canonical relational query IR, independent SMT-LIB renderer, deterministic version-2 JSON exporter; 30 focused Python tests. Lean v2 decoder, parser-state binding, independently constructed factor-pair inequality, and adversarial fixtures are implemented. | Closes the exercised factor-pair substitution gap: Lean resolves both factor references through retained parser state, reconstructs the inequality, and compares the complete ordered CPC assumption list. | Does not prove Python source-to-query encoder correctness, intended source-variable binding, cvc5/Logos end-to-end proof checking, or source-program-to-query semantic correspondence. |

**Cross-scenario trust boundary:** Scenarios 25–32 progressively narrow the proof pipeline from architecture proposal to finite oracle, symbolic query, typed IR, process runner, parser binding, and strict profile. These are not interchangeable proof claims. In particular, (a) finite-model independence is scoped to a declared finite model; (b) SMT-LIB emission is not an SMT proof; (c) a checker process reporting correct is not a bound proof; (d) CPC assumption binding is not source semantics; and (e) QF_LIA admissibility is not encoder correctness. Scenario 34 supplies a formal correspondence result only for its declared Int/Bool fragment and remains conditional on the still-open source/query boundaries.


### 2.27 Dependency discovery and counterfactual-analysis audit — Scenarios 20–24

| Scenario | Prototype and tests | Supported claim | Unresolved boundary |
|---:|---|---|---|
| 20 | Dependency Graph Prototype 01: dependency_discovery.py and test_dependency_discovery.py. | Normalizes evidence-bearing candidates from explicit declarations/static/dynamic/sandbox/proof sources and requires explicit semantic classification before candidates enter the hash-relevant dependency set; unknown candidates block completeness. | It consumes normalized observations and does not implement static analyzers, tracers, sandboxing, proof extraction, or authoritative semantic classification. |
| 21 | counterfactual_analysis.py and test_counterfactual_analysis.py. | Compares normalized repeated baseline/treatment records for one declared factor; distinguishes observable behavioral influence, trace-only changes, no observed difference, and inconclusive experiments. | Does not execute programs, pin or isolate external state itself, or prove irrelevance from no observed difference. |
| 22 | coverage_guided.py and test_coverage_guided.py. | Generates typed finite-domain single-factor and t-way intervention candidates, adds extrema/optional static-taint targets, deduplicates by pinned artifact/context/observation identity, and schedules by deterministic greedy set cover under an execution budget while preserving uncovered targets. | Planner only: it does not execute interventions or prove dependency completeness. The initial scheduler's joint-intervention candidates were not yet consumable by Scenario 21's single-factor API. |
| 23 | multifactor_analysis.py and test_multifactor_analysis.py. | Separates joint intervention from factorial interaction; repeated 2×2 blocks can measure difference-in-differences for numeric outcomes and limited conditional equality patterns for categorical outcomes. | Consumes normalized run records; does not execute programs, establish causal attribution beyond its stated design, solve input constraints, or prove completeness. |
| 24 | adaptive_discovery.py and test_adaptive_discovery.py. | Schedules repeated single-factor trials, complete pairwise 2×2 factorial blocks, evidence-triggered higher-order blocks, and bounded retries under an actual-execution budget; preserves untested targets and separates scheduled coverage from observed feedback. | Planner only: it consumes normalized feedback and does not execute programs, solve constraints, or prove dependency completeness. Adaptive coverage is budgeted exploration, not exhaustive evidence. |

**Cross-scenario boundary:** these prototypes form a staged pipeline: candidate discovery (20), one-factor counterfactual evidence (21), finite candidate generation/scheduling (22), factorial analysis (23), and adaptive scheduling (24). The data structures preserve provenance and scope, but the experiment runner and actual program instrumentation are external inputs. A planned or executed intervention is not itself a semantic dependency; an observed effect is positive evidence within the declared context; no observed difference is not proof of irrelevance; and a coverage percentage is not a completeness proof.


### 2.28 Requirement evolution and impact planning audit — Scenarios 18–19

| Scenario | Prototype and tests | Supported claim | Unresolved boundary |
|---:|---|---|---|
| 18 | Dependency Graph Prototype 01: requirement_evolution.py and test_requirement_evolution.py. | Models immutable requirement revisions, snapshot-local selection, hash-relevant semantic dependency edges, separate lineage/provenance, direct/transitive impact, verification-key changes, split/merge, and three-way concurrent branch merge. | Does not compute semantic diffs for arbitrary typed IR, resolve all cross-snapshot aliases/contextual ownership, automatically merge semantic conflicts, prove dependency completeness, or provide a distributed atomic commit. Provenance-only classification still requires explicit review. |
| 19 | impact_planning.py and test_impact_planning.py. | Audits whether independently observed dependency identities are covered by declared dependencies within exact artifact/scope/evidence bindings; distinguishes GAP_FOUND, SUPPORTED_WITHIN_SCOPE, UNKNOWN, and NOT_CHECKED; maps impacted artifact kinds to typed actions and forces HUMAN_REVIEW + FULL_REVALIDATION when completeness is unsupported. | It is not a dependency extractor, runtime tracer, proof checker, or action executor. A NO_ACTION decision only checks that a matching PROVEN non-interference certificate record is bound; it does not verify the proof. |

**Cross-scenario boundary:** Scenario 18 models how explicit typed semantic dependencies propagate change impact, but does not establish that the graph is complete. Scenario 19 makes that completeness question explicit and fails closed when scoped evidence is missing. Scenarios 20–24 then add evidence-bearing candidate discovery and counterfactual/coverage planning; those planners do not remove the need for independent completeness evidence. The complete chain must not treat graph traversal, normalized observation records, or a bound certificate record as proof validation.


### 2.29 Business intent and typed Requirement IR audit — Scenarios 15–17

| Scenario | Prototype and tests | Supported claim | Unresolved boundary |
|---:|---|---|---|
| 15 | Dependency Graph Prototype 01 business-intent experiment (Prototype 16): immutable intent sources, explicit clarification decisions, caller-scoped business rules, provenance-carrying formal clauses, candidate acceptance gates, effective-date examples/counterexamples, and a two-caller tax-policy evolution fixture. | Demonstrates that a caller-owned policy change can affect that caller's selected semantic value while leaving a generic callee contract and another caller unchanged in the finite fixture. | Not a natural-language parser, authorization system, general formal logic engine, or proof that an accepted clause matches stakeholder intent. Human/authoritative acceptance remains a separate trust boundary. |
| 16 | No Scenario 16 report is present in the current research tree. | No evidence claim can be assigned to this missing number. | Preserve the numbering gap; do not infer a report or renumber later scenarios. |
| 17 | Dependency Graph Prototype 01 typed Requirement IR experiment (Prototype 17): typed predicates/Boolean composition, ownership/scope, provenance, triggers/actions, temporal metadata, assumptions, unresolved questions, required dimensions, finite-domain contradiction/underdetermination checks, and satisfying/violating scenario generation. | Replaces opaque predicate strings with a typed, provenance-preserving representation and produces bounded finite-domain examples/counterexamples for the implemented operators. | Finite-domain only; temporal fields are metadata, not temporal logic. No arithmetic expression tree, units, quantification, solver integration, authority check, implementation proof, or arbitrary-system traceability/test completeness. |

**Cross-scenario boundary:** Scenario 15 distinguishes proposing a formal interpretation from accepting it as the business contract; proof of implementation conformance cannot prove intent fidelity. Scenario 17 supplies typed semantic structure and finite analysis but does not validate stakeholder authority or implementation correctness. Scenario 18 then adds immutable evolution/impact, still conditional on complete typed dependency edges.


### 2.30 Project identity, binding, and behavioral refinement audit — Scenarios 12–14

| Scenario | Prototype and tests | Supported claim | Unresolved boundary |
|---:|---|---|---|
| 12 | Dependency Graph Prototype 01 execution.py models BuildSnapshot, BuildArtifact, DeploymentSnapshot, ExecutionSnapshot, ReleaseManifest, and compare-and-swap release-channel publication. | Separates declared build inputs from produced artifact bytes, deployment wiring, request/external execution inputs, and immutable release joins. | Exploratory model, not a build system, deployment orchestrator, execution recorder, secret store, or proof of bit-for-bit reproducibility. Actual build reproducibility requires comparing artifact digests under equivalent pinned inputs. |
| 13 | scoped_binding.py models project/tenant/request binding layers, precedence, override permissions, and pinned resolution decisions. | Distinguishes implementation substitution under a behavioral contract from business-policy selection as a semantic input; records scope and winning resolution. | Not an authorization system or behavioral-equivalence proof. A declared implements edge is not conformance evidence; the precedence model does not prove that an override preserves behavior. |
| 14 | contract_model.py finite observable-trace refinement model and focused tests. | Distinguishes PROVEN/DISPROVEN/UNKNOWN for finite contract and implementation trace models; PROVEN only applies when both models explicitly declare complete semantics and every modeled implementation trace is allowed by the contract. | Exhaustive proof of finite models only, not arbitrary source code. Completeness declarations are model inputs; no source-to-contract or implementation-to-model proof, general concurrency/runtime semantics, or independent proof kernel. |

**Cross-scenario boundary:** Scenario 12 separates project/build/artifact/deployment/execution identity; Scenario 13 separates implementation binding from caller-owned business-policy selection; Scenario 14 supplies a finite behavioral refinement model for deciding whether an implementation may substitute for a contract. These identities and proof obligations must remain separate: same signature or declared implements edge does not establish refinement, and equal build recipes do not establish equal outputs.


### 2.31 Content-addressed evolution, implementation binding, and persistence audit — Scenarios 9–11

| Scenario | Prototype and tests | Supported claim | Unresolved boundary |
|---:|---|---|---|
| 9 | Conceptual content-addressed dependency model and 100-caller/three-caller stress analysis; no separate executable prototype is identified by the scenario report. | Shows how immutable semantic values and exact dependency references can represent selective caller migration without requiring a persistent identity for every occurrence in the stated direct-call example. | Model argument, not a completed prototype or falsification suite. Dynamic dispatch, hidden environment inputs, recursion/cyclic dependencies, governance identity, and whole-system sufficiency remain open. |
| 10 | Dependency Graph Prototype 01 binding.py and test_binding.py. | Models immutable contract/implementation values and binding snapshots; callers may depend on contracts while a snapshot selects concrete implementations. Binding selection is kept separate from caller semantic identity and can enter build/deployment/execution roots when behavior can change. | Exploratory persistence model only; atomic integration with project snapshots, dynamic dispatch, compatibility checking, runtime loading, and formal conformance are unimplemented. |
| 11 | Dependency Graph Prototype 01 project_state.py and test_project_state.py. | Composes graph and binding serializers into one deterministic, checksummed envelope; tests graph/binding round-trip, root preservation, deterministic reserialization, checksum tampering, dangling implementation references, and schema-version rejection. | Envelope integrity is not a multi-writer transaction or atomic concurrent update. The prototype does not decide which binding root a project snapshot must select or prove implementation conformance. |

**Cross-scenario boundary:** Scenario 9's direct-call content-addressing model motivates separating contract identity from concrete implementation selection (10), then preserving graph and binding roots together on reload (11). A checksummed envelope does not solve atomic branch-head selection, and an implementation binding does not prove behavioral refinement (14). Keep immutable object identity, snapshot selection, persistence integrity, atomic publication, and conformance proof as distinct claims.

## 3. Findings and actions

| ID | Finding | Action / status |
|---|---|---|
| RCA-01 | The corpus has 462 tracked research artifacts in the refreshed inventory snapshot (excluding the manifest itself), but previously lacked a complete path inventory. | Added the machine-readable inventory snapshot. |
| RCA-02 | Artifact-to-item mapping is not uniformly explicit in filenames. | Added qualified path-based mappings; content-level verification remains open. |
| RCA-03 | The 233-file historical baseline was scanned for inline relative links (1,330 occurrences); the current corpus contains 234 Markdown/MDX files after adding the semantic-traceability report, so a full current-corpus scan remains open. One LLMLang-authored broken link was fixed; 38 unresolved occurrences remain only in partial Alive2/OCI snapshots. | Project-authored inline relative links resolve; external snapshot completeness, external URLs, anchors, and index completeness remain open. |
| RCA-04 | At the refreshed inventory revision, the main, preparation, and references indexes have 85, 11, and 2 unique relative targets; all resolve. | Index link existence checks complete; scientific readiness and index coverage remain open. |
| RCA-05 | PLAN.md §0.3 reported stale taxonomy/dependency counts. | Corrected to 24 research areas and 94 dependency edges; added RT-24 with candidate dependencies DEP-086–DEP-093 while retaining RT-14 edges DEP-078–DEP-085. |
| RCA-06 | One exact duplicate blob is shared by the OCI and REAPI Apache-2.0 licence files. | Classified as intentional shared licence content; no deletion proposed. |
| RCA-07 | External snapshot integrity and experiment reproducibility have not been independently re-established. | Preserve pinned revisions and existing manifest; verify source blobs and experiment environments in a later pass. |
| RCA-08 | Three section-level supersession cases are explicit; semantic near-duplicates, orphans, and contradictions are not exhaustively reviewed. | Record the three known cases without deleting whole documents; complete the corpus-wide semantic review in a later pass. |
| RCA-09 | All 104 files in `PROTOTYPES/RT-04-01/` previously inherited RT-04 traceability from the directory name, although their contents include RT-03-only and cross-profile artifacts. | Replaced path inference with individual content-based role mappings: 39 RT-03-only, 59 RT-04-only, and 6 shared; exact shared files and method are recorded in the semantic traceability report. |
| RCA-10 | Five prototype-tree files remained at family-level mapping only (two RT-16 authorization and three RT-19 Toolchain Server artifacts). | Individually reviewed their purpose and paired test/document relationships; all 240/240 prototype-tree files now have first-pass role mappings. |
| RCA-11 | Bounded path-feasibility experiments have a solver integration boundary: the raw SymPy adapter prunes UNSAT directly, while the conservative evidence mapper is separate; Scenario 102 also reports seven focused tests although its current test file contains eight methods. | Recorded both as open evidence-audit findings; do not treat the raw adapter as a safe may-analysis interface or the test count as reconciled until the code/report revision is pinned. |
| RCA-12 | SQLite native probes and the generated-Rust execution are described as evidence, but the Required CI workflow only discovers Python test_*.py files and does not invoke those native probe commands. | The separate workflow successfully reproduced Scenarios 120–128 on the exact SQLite distro source ID, Scenario 130 on Python sqlite3 3.53.1, and Scenario 133 on Rust 1.85.1. Per-case outputs match the reported observations. Scenario 130's historical SQLite source ID was not recorded, so only its version-level identity can be matched. |
| RCA-13 | The three tests for Scenario 133 exercise Rust code generation and rejection behavior without invoking rustc; the native 125,952-comparison claim is a separate manual command. | The native workflow ran Rust 1.85.1 and matched all 125,952 observations, including the six reported admission counts. The captured output is in artifact 14648440097; generator CI and native Rust conformance remain separate evidence levels. |
| RCA-14 | Scenario 134 proposes a Protobuf/Avro/CBOR runtime conformance matrix, but the current accepted architecture requires only same-build, same-toolchain caller/callee compatibility and excludes cross-version wire guarantees. | Classified Scenario 134 as prior-art/reference material, not active implementation work. Do not schedule its runtime matrix unless a documented reconsideration trigger in the accepted architecture decision is introduced. |
| RCA-15 | Scenario 130's historical report records Python sqlite3 version 3.53.1 but omits its SQLite source ID. | Reproduced at the documented version and recorded the new run's source ID; byte-identical historical build provenance cannot be established retroactively. Require source IDs in future reproducibility reports. |
| RCA-16 | Scenarios 96A/96B contain detailed historical LLVM experiment evidence, but Required CI does not execute those native probes. | The llvm-preservation job freshly reproduced both probes with the exact Debian LLVM package hash and recorded Python/GCC/linker/libc versions. Both comparison matrices and negative controls matched the reports; artifact 14647744441 preserves outputs. It remains a separate non-required native job.

## 4. Reconciliation rules

1. Do not delete or rewrite historical research merely because a newer scenario exists.
2. Keep preparation briefs distinct from executed research results.
3. Keep copied primary-source snapshots distinct from LLMLang-authored analysis.
4. Treat the taxonomy and dependency map as detailed evolving registers; do not copy stale fixed counts into other documents.
5. Treat path-derived mappings as inventory hints, not as accepted semantic traceability.
6. Keep research exploratory; architectural or language decisions must be recorded separately in the appropriate decision/specification documents.

## 5. Remaining work for full completion of PLAN.md §0.1

- [ ] Read and validate the content-level mapping for every artifact, including prototypes, tests, fixtures, generated outputs, RFCs, and snapshots.
- [x] First-pass content/heading/reference triage of 36 low-confidence entries; see the semantic traceability report.
- [x] Cross-walk all 136 Scenario reports to candidate RT areas (63 taxonomy link/range mappings; 73 first-pass content/header mappings); record Scenario 134 prior-art-only applicability; Scenario 91's RT-24 reference now resolves.
- [x] First-pass individual file-role mapping for all 240 prototype artifacts across eight families and the Scenario 34 Lean extension; no prototype-tree artifacts remain without individual role mappings.
- [ ] Validate prototype claims, test evidence, generated outputs, exact tool versions, and reproducibility at content/experiment level. Bounded passes now cover Scenarios 9–14 and 15, 17–134 (Scenario 16 absent); see §§2.9–2.31 and the semantic traceability report. Native execution is reproduced for Scenarios 120–128, 130, and 133; Scenarios 109–118 are finite model tests, while 127/129/131/132 remain bounded model/source-fixture evidence. The later PR #97 run 44774296240 independently reran the same ten RT-04 commands and both LLVM preservation probes; artifacts 14650095720 and 14650040345 preserve the run outputs. Broader claim validation remains open.
- [x] Map nine vendored technical source documents to the RT areas named by the reference register; keep seven provenance/navigation/licence files at Stage 0.
- [x] Register RT-24 and cross-link its three research documents; keep the technical contract and dependency edges explicitly provisional.
- [x] Reconcile scenario-number identity at first pass: record Scenario 95's main/follow-up relationship and the absent Scenario 16 report without renumbering.
- [ ] Identify semantically duplicate, superseded, orphaned, and contradictory documents.
- [ ] Decide whether missing relative targets in the partial Alive2/OCI source snapshots should remain documented as non-vendored upstream material or whether additional upstream files/assets should be added while preserving source provenance; validate external URLs and heading anchors if needed.
- [ ] Verify exact source revision, tool versions, commands, fixtures, expected outputs, and negative cases for each reproducibility-sensitive experiment.
- [ ] Independently re-verify external snapshot blob identities and licence provenance.
- [ ] Confirm that the research index exposes every relevant artifact or provides clear directory-level indexes for grouped artifacts.

## 6. Sources inspected

- Recursive Git tree at `a30ec074e08186f04a35535b9933bfa878713f31`; inventory excludes its own manifest file.
- `PLAN.md`
- `research/README.md`
- `research/RESEARCH-TAXONOMY.md`
- `research/RESEARCH-DEPENDENCY-MAP.md`
- `research/preparation/README.md` and its eight linked briefs
- `research/references/README.md` and `research/references/SNAPSHOT-MANIFEST.json`
- `draft/GLOSSARY.md`

---

**Conclusion:** the repository-wide path inventory, coarse artifact classification, Git-blob duplicate check, inline relative-link scan across the 233-file historical baseline, first-pass triage of 36 low-confidence entries, and individual role mapping for all 240 prototype-tree files are recorded. Bounded claim/evidence passes now cover Scenarios 9–15, 17–118 and 119–134. They preserve the open SymPy UNSAT integration boundary and Scenario 102 test-count discrepancy, distinguish native evidence from finite-model/standards evidence, and record Scenario 134's non-active applicability under the accepted architecture decision. The full corpus evidence audit, current-corpus link/anchor scan, semantic duplicate/supersession/orphan/contradiction analysis, and remaining experiment provenance checks are still open. One LLMLang-authored broken link was fixed; 38 unresolved occurrences are confined to partial verbatim external snapshots. PLAN.md §0.1 remains partially validated until content-level and reproducibility validation for all 240 individually role-mapped prototype artifacts, index completeness, explicitly preserve RT-24's non-normative candidate status, supersession/orphan/contradiction analysis, external snapshot provenance/completeness, and reproducibility verification are complete.
