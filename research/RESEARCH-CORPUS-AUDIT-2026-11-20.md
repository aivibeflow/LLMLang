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

A separate llvm-preservation job has now been added to the Research Native Reproduction workflow. It installs the exact Debian Trixie llvm-19 package 1:19.1.7-3+b1, verifies the package archive SHA-256 and toolchain versions, and reruns both probes. Its first execution is pending. Until it passes, the 96A/96B results remain historically reproduced evidence with pinned provenance, not a fresh current-branch reproduction.

**Cross-area status:** Scenarios 90–93 map to still-open identity/cache decisions (LL-004, LL-005, LL-001, LL-021); Scenario 95 remains partial research; Scenario 96 informs LL-020 but does not settle backend selection. These reports must not be promoted into normative language rules or accepted architecture decisions without the corresponding review.


### 2.17 Fresh LLVM preservation reproduction — Scenarios 96A/96B

The llvm-preservation job in [Research Native Reproduction run 44773422416](https://github.com/aivibeflow/LLMLang/actions/runs/44773422416) passed both native probes. The environment matched the recorded toolchain: Debian Trixie/glibc 2.41, Python 3.12.14, libffi 3.4.8, Debian llvm-19 package 1:19.1.7-3+b1, GCC 14.2.0, and GNU ld 2.44. The downloaded Debian package SHA-256 matched the report exactly: 0b1b7263f4f45e261099240fdbf00fc14b42b88410fd829e041bf83ea45866cb. Both probes use the explicit x86_64-unknown-linux-gnu triple, x86-64 CPU, PIC, and O0/O3 pipelines.

- **96A integer preservation:** 20,978 traces at O0 and 20,978 at O3, zero mismatches. Outcome counts per level were ok 17,552; overflow 1,765; shift_count 1,566; zero_divisor 95. The verifier-accepted missing-overflow-branch mutant disagreed at the signed-maximum witness. Three unsupported source forms and one invalid dominance relation were rejected. Input IR SHA-256 matched the report: c46111f6b77eb621a5c154b17645044e1d76c7cb2808fe80189a63f447dc173d.
- **96B byte-view preservation:** 9,800 traces at O0 and 9,800 at O3, zero mismatches. Outcome counts per level were bounds 4,100; ok 580; overflow 1,200; wrong_origin 3,920. The verifier-accepted one_past_read and erased_origin controls disagreed with the source reference. Input IR SHA-256 matched the report: ddb41ceb866c77e957df865cd2102f7a02d3a468150fc82f79c7a7fb2bf782d0.

Artifact [14647744441](https://github.com/aivibeflow/LLMLang/actions/runs/44773422416/artifacts/14647744441) preserves the runtime manifest and both probe outputs. This is a fresh reproduction of the recorded fixtures and toolchain on the current PR revision. It does not expand the claim beyond the fixed x86-64 fixture, target, integer/view operations, and O0/O3 configurations.

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
- [ ] Validate prototype claims, test evidence, generated outputs, exact tool versions, and reproducibility at content/experiment level. Bounded passes now cover Scenarios 97–118 and 119–134; see §§2.9–2.15 and the semantic traceability report. Native execution is reproduced for Scenarios 120–128, 130, and 133; Scenarios 109–118 are finite model tests, while 127/129/131/132 remain bounded model/source-fixture evidence. Broader claim validation remains open.
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

**Conclusion:** the repository-wide path inventory, coarse artifact classification, Git-blob duplicate check, inline relative-link scan across the 233-file historical baseline, first-pass triage of 36 low-confidence entries, and individual role mapping for all 240 prototype-tree files are recorded. Bounded claim/evidence passes now cover Scenarios 97–118 and 119–134. They preserve the open SymPy UNSAT integration boundary and Scenario 102 test-count discrepancy, distinguish native evidence from finite-model/standards evidence, and record Scenario 134's non-active applicability under the accepted architecture decision. The full corpus evidence audit, current-corpus link/anchor scan, semantic duplicate/supersession/orphan/contradiction analysis, and remaining experiment provenance checks are still open. One LLMLang-authored broken link was fixed; 38 unresolved occurrences are confined to partial verbatim external snapshots. PLAN.md §0.1 remains partially validated until content-level and reproducibility validation for all 240 individually role-mapped prototype artifacts, index completeness, explicitly preserve RT-24's non-normative candidate status, supersession/orphan/contradiction analysis, external snapshot provenance/completeness, and reproducibility verification are complete.
