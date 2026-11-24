# RT-00 B-05 — Complete Traceability Graph Audit — 2026-11-21

**Status:** corpus-wide traceability model consolidated; end-to-end claim/evidence graph remains partially unresolved  
**Original baseline:** `main` at `b0142c27f5632a859c379b78a10cb22f500ebfd8`  
**Current-main refresh:** `535d5dc9c9eca9bb6ecfaea31a85de666c9e4091` (2026-11-21)  
**Inventory:** the original audit's 488-record manifest and 493-artifact main count are historical. The manifest was subsequently reconciled by merged PR #189 against main snapshot `9dfc01bd8acf7da602f1c927e519256bd4c810b1` (526 research artifacts); current main has advanced beyond that snapshot. No current recursive tree count is inferred here; a fresh exact-tree audit is required before treating inventory metadata as current.  
**Scope:** reconcile the research taxonomy, dependency register, corpus inventory, scenario crosswalks, prototype/test/evidence reviews, PLAN stages, and merged-tree evidence.  
**Decision boundary:** audit only. No research claim, language rule, architecture, identity policy, backend, runtime policy, or candidate vector is accepted by this report.

## 1. Executive result

The corpus has several useful traceability layers, but they do not yet form one complete claim-to-evidence graph.

The baseline contains:
- 26 registered research areas (RT-01–RT-26);
- 108 directed dependency edges (DEP-001–DEP-108);
- 136 scenario-named documents;
- 493 tracked research artifacts in current main, including 250 files under `research/PROTOTYPES/`; the previous manifest records only 488.
- 252 Markdown files, 203 Python files, and 23 Lean source files.

The strongest existing graph layer is the RT/DEP register. The inventory also provides a file-level crosswalk from artifacts to research areas, with a method, confidence, and semantic-review basis. Scenario-to-RT relationships are recorded in the taxonomy, and bounded prototype-family reviews supply detailed implementation/test/CI/evidence subgraphs.

However, the following are not yet complete corpus-wide:
1. stable claim-level identifiers and claim-to-requirement/RT links;
2. explicit scenario-to-prototype-to-test-to-evidence edges for every applicable result;
3. test-to-fixture, command, external tool, CI job, artifact, and exact revision closure;
4. a uniform evidence-status model distinguishing authored, executed, reproduced, independently checked, and accepted;
5. a complete PLAN-stage crosswalk whose links are semantically reviewed rather than inherited from file/path classification;
6. a complete, current supersession/contradiction overlay.

Therefore, **“complete traceability graph” is not a valid completion claim yet**. This audit consolidates the graph's current structure and identifies where the remaining edges are absent, ambiguous, conditional, or supported only by first-pass triage. It does not infer missing links from filenames, directory proximity, shared RT labels, or the existence of a workflow.

## 2. Graph model and edge semantics

A traceability graph must preserve distinct node types. At minimum:

| Node type | Meaning | Examples |
|---|---|---|
| ResearchArea | Registered research topic | RT-03, RT-24, RT-26 |
| Dependency | Directed cross-area hypothesis/relationship | DEP-005, DEP-088, DEP-100 |
| Claim | Atomic falsifiable statement made by a report or experiment | Scenario claim, result ID, named finding |
| Scenario | Numbered comparative or executable research study | Scenario 34, 96A, 96B, 134 |
| Artifact | Tracked source document, prototype, test, fixture, workflow, or reference | Markdown, Python, Lean, JSON, workflow YAML |
| Test | A named automated test or test case | A `test_*` method, Lean example, native probe |
| Evidence | An execution/reproduction record tied to an exact subject and environment | CI run, artifact bundle, native output, proof build |
| PlanStage | Research/development stage or task in `PLAN.md` | Stage 0, Stage 4.5, Stage 7 |
| Decision | Explicit accepted or pending project decision | ADR status, accepted compatibility policy |

Permitted edge kinds must be explicit and directional where applicable:

- `classifies`: Artifact → ResearchArea; file-level classification only.
- `investigates`: Scenario → ResearchArea; study scope, not proof of a claim.
- `depends_on`: ResearchArea → ResearchArea via a DEP node; a hypothesis unless its evidence and scope establish otherwise.
- `implements`: Artifact → Artifact or Claim; requires source-level evidence, not a matching filename.
- `tests`: Test → Claim/subject; a test's existence does not mean it ran or passed.
- `uses_fixture`: Test/Scenario → Fixture; must be established from the actual test or runner.
- `executes_under`: Test/Scenario → Tool/Environment/CI job; requires the invocation definition or execution record.
- `produces`: Execution → Evidence; evidence must identify its exact output and subject.
- `supports` / `refutes`: Evidence → Claim; scope, assumptions, and outcome are mandatory.
- `scheduled_in`: ResearchArea/Scenario → PlanStage; scheduling is not validation.
- `supersedes`: newer Claim/section/artifact → older Claim/section/artifact; scope must be stated.
- `contradicts`: Claim ↔ Claim; both statements and their assumptions must be identified.
- `unresolved`: candidate relationship with an explicit reason and missing proof obligation.

Every edge should carry:
- source and target stable identifiers;
- edge kind and direction;
- source citation (path plus section/line/anchor or code symbol);
- evidence class: explicit declaration, source-derived, execution-derived, bounded semantic review, or unresolved;
- status and confidence;
- baseline/revision where source content is revision-sensitive;
- scope/assumptions and any conditions;
- reviewer/method where the edge comes from semantic triage.

A link in Markdown establishes a navigational edge. It does not, by itself, establish `implements`, `tests`, `supports`, or `supersedes`.

## 3. Reconciled graph layers

### 3.1 Research-area and dependency layer

The taxonomy declares 26 RT areas. The dependency map contains 108 unique DEP rows and describes direction, relationship kind, rationale, and confidence. Its own preamble explicitly defines the map as an initial research hypothesis, not normative architecture; mentioning two documents does not establish a dependency.

The structural RT/DEP layer is present and internally enumerable. The current graph must nevertheless preserve the confidence labels and evidence scope of each DEP edge. In particular:
- DEP-005 has scoped experimental support from the typed SPG operand-order observation; it is not a universal semantic proof.
- DEP-009/010 are established only within the current research model and Scenario 25–34 scope, not across every future language feature.
- DEP-011/012 have scoped evidence and still require production dependency/action closure.
- DEP-088, DEP-091, and DEP-093 now have bounded source-inventory/merge evidence from the merged RT-24 study; this does not validate the complete semantic merge or all dispatch mechanisms.
- DEP-100–108 are the RT-26 dependency family. Their presence records research relationships, not a validated resource-accounting design.

**Finding B5-01 — the RT/DEP graph is a complete register, not a completed proof graph.** The 26 nodes and 108 edges are structurally enumerable. Their semantic validity remains edge-specific and conditional on recorded evidence. Do not convert all 108 edges to “established” because they are registered.

### 3.2 Artifact-to-research-area layer

The main inventory manifest still has 488 records, while current main contains 493 tracked research artifacts. The two RT-24 source-completeness paths, two RT-23 exact-tree recovery paths, and merged B4 audit report are absent from that manifest; five existing blob metadata records are stale. PR #149 proposes their registration and refreshes stale blob metadata. Each existing record includes a path, Git blob SHA, size, coarse category, traceability metadata, semantic-review metadata, and plan-stage metadata where applicable. The recorded traceability method distinguishes first-pass content/heading/reference review from weaker path-based classification.

This provides broad file-level navigation, but the inventory itself states that its mappings are not claim-level validation. A primary RT label does not imply that every claim in the file belongs exclusively to that RT. Secondary mappings are not a substitute for a claim-level crosswalk.

**Finding B5-02 — artifact classification is substantially populated, but its semantic resolution varies.** Use the per-record method/confidence/review basis. Do not present a medium-confidence first-pass mapping as a verified semantic edge.

### 3.3 Scenario-to-RT layer

The taxonomy explicitly links scenario reports to research areas. The inventory records 136 scenario-named documents. The known numbering/identity exceptions must remain explicit:
- Scenario 16 has no report; do not fabricate or renumber it.
- Scenario 95 has a main study and a supplemental execution report; they are companion artifacts, not duplicate studies.
- Scenario 96A and 96B are distinct evidence layers under the broader Scenario 96 subject.
- Scenario 134 is prior-art/reference comparison and does not automatically create a current implementation requirement.
- Scenarios 25 and 30 do not have dedicated same-numbered prototype directories/results; their implementation/research paths are represented elsewhere.
- Scenario 31/32/33/34 contain a progression of query representation, parser-state binding, and source-semantics proof. These are related but non-equivalent claims.

The B4 duplicate/supersession audit report is merged in PR [#152](https://github.com/aivibeflow/LLMLang/pull/152). Its bounded findings are now part of the corpus-audit baseline, but the semantic supersession relationships have not yet been materialized as a complete machine-readable claim-level graph; retain their scope and evidence basis.

**Finding B5-03 — scenario registration is not a one-to-one scenario/prototype mapping.** Any graph generator that assumes matching numbers, filenames, or directories will create false edges.

### 3.4 Prototype, test, fixture, and CI layer

The corpus has 250 prototype-tree files, but a count of files is not a count of independently validated claims. Existing reviews provide detailed slices:

| Evidence slice | Reviewed structure | Boundary |
|---|---|---|
| DEPENDENCY-GRAPH-01 | 103 files role-triaged; 32 Python source modules and 32 test modules; 21 Lean source modules and a separate parser bridge | Family review distinguishes source, tests, Lean proof chain, fake solver, and real solver boundaries; it is not a corpus-wide graph |
| RT-04-01 | Dedicated prototype/evidence review and 364-test Required CI selection | A passed suite supports only the imported/discovered test set and declared inputs |
| LLVM preservation | Scenarios 96A/96B link the generator/runner and reference rules; pinned LLVM 19.1.7, O0/O3 comparisons and negative controls are recorded | The experiments cover finite integer and byte-view corpora on Linux x86-64, not general lowering or all targets |
| RT-24 source completeness | Merged PR #125 adds `test_rt24_merge_tree_gate.py` and a seven-test source-inventory/merge fixture | The bounded fixture validates exact source inventory and reverse-edge completeness under its closed schema; not a production repository reader |

The Dependency Graph review reports 32 Python test modules and 376 `test_*` methods in its audited snapshot; Required CI selected 12 modules (177 such methods) and compiled all Python source/test modules. The remaining modules had local/isolated evidence of varying strength. It separately records fake-executable tests and the absence of real cvc5/Logos proof generation. This is precisely why a single boolean `tested=true` edge would be misleading.

For the LLVM studies, the report-level edge from Scenario 96A/96B to its probe is explicit. The result-level edges must retain:
- exact LLVM version and target;
- O0 and O3 pipelines;
- comparison counts and outcome classes;
- the negative-control mutations and their observed mismatches;
- the exact reproduction workflow/artifact, where available.

A verifier-accepted LLVM module is not itself evidence of source-level semantic preservation.

**Finding B5-04 — prototype/test links exist in reviewed families, but evidence strength is heterogeneous.** The graph must encode test discovery, actual execution, result, environment, and claim coverage separately. Workflow presence or a green unrelated CI run is not execution evidence for a given claim.

### 3.5 Evidence and exact-revision layer

Evidence must bind to the object actually evaluated. The corpus already contains examples of the required discipline:
- the inventory records blob SHA and byte size for each artifact;
- the Lean proof audit records the toolchain/dependency pin and exact-head Required CI;
- the LLVM reports pin LLVM/toolchain/target and record generated inputs and comparison counts;
- RT-24 merged-tree source completeness binds its source inventory and reverse evidence to the exact Git tree and inventory digest.

The merged RT-24 study: [RT-24 source completeness](../RT-24/RT-24-MERGED-TREE-SOURCE-COMPLETENESS.md) maps to PLAN §4.5, DEP-088/091/093, and the RT-20/RT-23 validation boundary. Its seven focused tests are part of the merged study's reported validation. It demonstrates that a clean Git merge or warm object store can conceal a missing exact declaration, and that a source-inventory comparison detects an omitted caller even when two graph views share the same omission. The conclusion is bounded to the closed fixture and its declared schema. B4's current-main exact-content revalidation was merged as PR #152: it grouped the 492-artifact pre-report b52ba2f tree and found only the expected OCI/REAPI Apache-2.0 licence pair. The B4 audit report itself is now one additional artifact in current main b0142c2; it is a corpus-audit artifact, not a new language-semantic claim. The merged RT-23 study: [exact-tree commit recovery](../RT-23/RT-23-EXACT-TREE-COMMIT-RECOVERY.md) maps to PLAN §4.5 and the RT-22/RT-23 synchronization protocol; its eight tests exercise frozen-tree publication, operation receipts, retry, stale refs, and branch movement. This is evidence for the local Git publication/retry boundary, not crash durability, remote pushes, or complete worktree-generation synchronization.

**Finding B5-05 — evidence identity is not yet normalized across all corpus families.** There is no corpus-wide common record that guarantees every result is bound to exact source revision, test selection, command, environment, output artifact, and claim. Where any field is absent, the evidence edge must remain partial or unresolved.

### 3.6 PLAN-stage layer

PLAN §0.1 explicitly separates inventory/role triage from claim validation and reproducibility. It also leaves claim-level prototype validation, exact per-experiment versions/revisions, current full link/anchor scan, and external snapshot completeness open. The inventory's `plan_stages` metadata is a useful candidate crosswalk, but some mappings are derived from first-pass review and cannot be treated as proof that the PLAN task's exit criteria passed.

PLAN stages are scheduling/acceptance structures, not evidence nodes. A checkmark in PLAN records task disposition; the underlying claim still needs its own evidence path.

**Finding B5-06 — PLAN linkage is available but not a validated acceptance graph.** Do not infer that an artifact completes a stage item solely because its inventory record names that stage or a report is linked from the plan.

## 4. Representative end-to-end traces

These examples demonstrate what a valid trace looks like and where it stops.

### 4.1 Scenario 34 — restricted source-to-query proof chain

`RT-03 / RT-06 / RT-07` → Scenario 34 → Lean source/query declarations and parser-state integration → kernel-checked declarations/examples → Required CI.

Supported within the declared deterministic Int/Bool fragment: the report and B-02b proof audit connect SC-1–SC-7 to checked declarations and 125 Lean examples. The family review separately distinguishes the Python JSON encoder, version-2 envelope, CPC assumptions, Logos adapter, parser-state bridge, and source-derived formula.

**Stops unresolved:** exact correspondence from Python-generated JSON/CPC assumptions to the proved source-derived formula; external Logos proof generation; SCW-34–41 trusted-boundary/adversarial/automation/acceptance obligations. The existence of a Lean proof and parser bridge does not prove the Python encoder.

### 4.2 Scenarios 96A/96B — LLVM semantic-preservation evidence

`RT-03 / RT-07 / RT-09 / RT-13` → Scenario 96 specification → Scenario 96A integer and 96B byte-view studies → Python reference/generator/runner → LLVM 19.1.7 O0/O3 comparisons and negative controls → reproduction artifacts/workflow.

Supported within the finite x86-64 corpora: 96A checks the integer fragment and ordered effects; 96B checks logical view bounds/origin and records verifier-accepted negative controls that violate the source contract.

**Stops unresolved:** general source-to-LLVM preservation, wider target/compiler coverage, allocation provenance beyond the tested views, and end-to-end source/runtime proof.

### 4.3 RT-24 — source inventory and merged-tree completeness

`RT-05 / RT-06 / RT-15 / RT-20 / RT-22 / RT-23 / RT-24` → DEP-088/091/093 → RT-24 merged-tree source completeness → `test_rt24_merge_tree_gate.py` → seven focused tests and pinned fixture environment → PLAN §4.5.

Supported within the closed acyclic fixture: exact callee retention, caller omission, stale evidence, source-slot coverage, and exact-tree binding.

**Stops unresolved:** general parser-to-source completeness, authenticated/authorized evidence producers, external dependency locks, all dispatch mechanisms, production semantic merge, mapping revisions, and full commit recovery integration.

### 4.4 RT-23 — exact-tree commit recovery

`RT-22 / RT-23 / RT-24` → PLAN §4.5 → [RT-23 exact-tree commit recovery](../RT-23/RT-23-EXACT-TREE-COMMIT-RECOVERY.md) → `test_rt23_commit_recovery.py` → eight focused tests → merged PR #126 at baseline commit `b52ba2f`.

The fixture prepares a commit object from a frozen candidate tree, binds an operation-specific receipt to its exact OID, and uses one Git ref transaction for branch publication and receipt creation. Tests cover retry after a lost reply, compare-and-swap rejection after a stale ref, conflicting receipts, same-tree/same-parent lookalike commits, receipt validation, branch advancement after publication, and movement away and back to the same OID.

**Stops unresolved:** the experiment does not establish crash/power-loss durability, receipt retention across garbage collection, remote push semantics, production receipt authorization, or a monotonic worktree-generation check. OID compare-and-swap alone cannot detect movement away and back.

### 4.5 RT-26 — resource accounting and enforcement

`RT-03 / RT-04 / RT-10 / RT-13 / RT-16 / RT-18 / RT-19 / RT-20 / RT-25` → DEP-100–108 → RT-26 research brief → PLAN research programme.

The taxonomy and dependency map register the work and its dependencies. The current RT-26 document says **Not started**. A separate open PR [#129](https://github.com/aivibeflow/LLMLang/pull/129) reports a bounded hierarchical budget-reservation experiment, but it is not part of this main baseline and cannot be treated as merged corpus evidence.

**Stops unresolved:** no merged scenario/prototype/test/evidence chain yet for all mandatory dimensions (memory, CPU, disk/network I/O, coroutine switches, performance counters), attribution, throttling, overshoot, platform enforcement, and handlers. The RT-26 node and DEP edges are planning relationships, not proof of the capability.

## 5. Cross-cutting gaps and unresolved relationships

| ID | Gap | Required graph treatment |
|---|---|---|
| B5-U01 | No stable corpus-wide Claim ID scheme across reports, scenarios, prototypes, and PLAN | Keep claim nodes local to report/section until stable IDs are introduced; do not synthesize global IDs from headings |
| B5-U02 | Many links are navigational or file-level, not semantic implementation/test/support edges | Preserve edge class and evidence basis; do not upgrade links by proximity |
| B5-U03 | Scenario 16 absent; numbering exceptions and companion reports exist | Keep explicit absent/companion/continuation relationships; never fabricate matching artifacts |
| B5-U04 | Prototype-to-test/fixture/CI closure is only deeply reviewed for selected families | Mark unreviewed family edges unresolved; reuse existing family audits rather than re-auditing them by filename |
| B5-U05 | Test source and test execution are frequently conflated in older evidence | Separate `declared_test`, `discovered_test`, `executed_test`, `passed_test`, and `supports_claim` |
| B5-U06 | Exact tool versions, environment, output artifact, and source revision are not uniformly preserved | Evidence without exact subject/environment remains partial; do not claim reproduction |
| B5-U07 | PLAN stage mapping is not equivalent to stage acceptance | Keep `scheduled_in` separate from `satisfies_exit_criterion` |
| B5-U08 | B4 PR #152 merged the duplicate/supersession audit report, but the corpus-wide semantic overlay is not yet represented as a validated claim-level graph | Preserve the scoped B4 findings as audit evidence; do not infer complete supersession edges from report links |
| B5-U09 | Open PR branches may contain useful research but are not part of main | Keep branch-only artifacts out of the main-baseline graph until merged |
| B5-U10 | External snapshots may be incomplete or lack full provenance/import closure | Retain source-snapshot edges with completeness and provenance status; do not treat a URL or local partial copy as full source closure |
| B5-U11 | Historical report status/CI references can become stale | Bind status claims to the report's pinned revision and add dated current-state evidence instead of rewriting history |
| B5-U12 | No complete claim-to-contradiction register exists yet | Preserve conflicting/conditional claims as unresolved until B6 reconciles assumptions and scope |

## 6. Required machine-readable graph contract

A future graph artifact should use explicit node/edge records rather than a flat list of links. Minimum node fields:

```json
{
  "id": "artifact:research/RT-24-MERGED-TREE-SOURCE-COMPLETENESS.md",
  "type": "Artifact",
  "path": "research/RT-24-MERGED-TREE-SOURCE-COMPLETENESS.md",
  "revision": "b0142c27f5632a859c379b78a10cb22f500ebfd8",
  "blob_sha": "…",
  "status": "present"
}
```

Minimum edge fields:

```json
{
  "id": "edge:<stable-id>",
  "from": "scenario:RT-24-source-completeness",
  "to": "test:DEPENDENCY-GRAPH-01/test_rt24_merge_tree_gate.py",
  "kind": "tests",
  "basis": "source-derived",
  "status": "supported_within_scope",
  "confidence": "high",
  "source": {
    "path": "research/RT-24-MERGED-TREE-SOURCE-COMPLETENESS.md",
    "section": "§7 Reproduction"
  },
  "scope": "seven tests for the closed fixture and declared source inventory",
  "limitations": ["does not establish production semantic-merge completeness"]
}
```

The examples are schema sketches, not a selected canonical graph format. A machine-readable graph must additionally provide:
- stable IDs for claims, tests, executions, artifacts, and evidence;
- explicit relation vocabulary and cardinality rules;
- duplicate-edge detection and dangling-reference validation;
- revision-aware identity and source citations;
- confidence/status enums that cannot collapse UNKNOWN into success;
- provenance and tool/environment records;
- scoped supersession and contradiction records;
- validation that every positive `supports` edge reaches a named claim and exact evidence object.

Do not generate or publish a supposedly complete JSON graph until these source records have been extracted and validated. A hand-authored partial graph mislabeled complete would be worse than the current explicit unresolved register.

## 7. Next actions

1. **B6 — unified contradictions and unresolved register:** reconcile the unresolved items in this report with B3 cross-cutting boundaries, merged B4 findings from PR #152, existing B-02b reports, and PLAN's open gates.
2. Build a canonical claim/evidence identifier proposal only after B6 inventories existing local claim labels and the costs of retroactive IDs.
3. Extend the graph in bounded passes: (a) remaining prototype families, (b) scenario claim-to-test/evidence mapping, (c) exact reproduction provenance, (d) external source closure, (e) PLAN exit criteria.
4. PR #126 and B4 PR #152 are merged into the baseline. B5 PR #151 remains branch-only; RT-17 #128 and RT-26 #129 remain separate branch-only experiments. PR #149 proposes the current inventory manifest and is not merged.
5. Do not mark PLAN §0.1 complete while claim-level validation, current links/anchors, reproduction closure, and external snapshot completeness remain open.

## 8. Conclusion

**Disposition: RT-00 B5 is complete as a graph-model and corpus-wide gap-consolidation pass, not as proof that every claim has a complete traceability path.** The RT/DEP register and file-level inventory are structurally available; selected families have detailed test/evidence subgraphs; representative end-to-end traces demonstrate both supported paths and their boundaries. The remaining corpus-wide claim/evidence edges are explicitly unresolved and must be closed in subsequent work.

No historical artifact, implementation, test, fixture, or external snapshot was modified. No architecture decision was made.


## 9. B5-07 — bounded claim-level traceability pilot

The [Scenario 130 claim-level traceability pilot](RT-00-B-05-01-SCENARIO-130-CLAIM-TRACEABILITY-PILOT-2026-11-21.md) demonstrates a local, non-global claim identifier scheme for one RT-04 scenario. It traces four falsifiable claims through report sections, model/probe symbols, test methods, exact source blobs, Required CI execution, native reproduction, and retained artifacts. A fifth broader design implication is deliberately left conditional because no independent-provider experiment supports it.

This pilot does not resolve B5-U01's corpus-wide stable Claim ID gap. It demonstrates a bounded extraction method that can be repeated after an identifier policy is explicitly reviewed. The local IDs `S130-C01`–`S130-C05` must not be promoted to a global namespace by inference.


## 10. B5-08 — RT-26 bounded claim-level traceability pilot

A second claim-level pilot is recorded in [RT-00 B-05-02](RT-00-B-05-02-RT26-CLAIM-TRACEABILITY-PILOT-2026-11-21.md), based on the current-main cooperative reservation fixture. It maps four local claims to the report and exact test methods, and distinguishes the historical PR #129 validation statement from an exact retained execution-to-blob provenance chain.

This updates the historical statement in §4.5 that RT-26 had no merged scenario/prototype/test/evidence chain: current main now contains one bounded cooperative cumulative-budget model and its four-test module. The broader RT-26 requirements remain open; no evidence is added here for instantaneous resource dimensions, runtime/OS enforcement, throttling, handlers, attribution, fairness, or production atomicity. PR #174 remains branch-only and is excluded.

The local identifiers `R26-C01`–`R26-C04` are pilot-scoped and do not resolve B5-U01's missing corpus-wide Claim ID namespace. Exact CI execution-to-source-blob binding also remains unresolved.

## 11. Current-main refresh — additional bounded claim/evidence edges (2026-11-21)

This addendum refreshes the graph against current `main` at `535d5dc9c9eca9bb6ecfaea31a85de666c9e4091`. It does not rewrite the historical baseline counts in §§1–10. The inventory manifest records a prior source snapshot at `9dfc01bd8acf7da602f1c927e519256bd4c810b1` and 526 research artifacts; subsequent main commits have added further research material. A current recursive tree count must come from a fresh exact-tree audit, not from extrapolating earlier snapshots. PR #189's exact-main audit and manifest reconciliation are merged, but its snapshot is no longer current.

### 11.1 RT-06 — negative dependencies in scoped binding resolution

Current main contains `research/RT-06-SCOPED-BINDING-READ-DEPENDENCIES.md` and the test module `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt06_negative_binding_reads.py`. The report declares 432 views across six states in three scopes and two policies, and 3,240 single-scope transitions. Its recorded result distinguishes three key strategies: all-layer revision keys (zero outcome-preserving reuse), exact per-key projection (216 preserving reuse, zero false reuse), and highest-priority-present-row-only (516 false reuses). It also records a duplicate-unrelated-key counterexample where the per-key projection remains equal while the resolver rejects the malformed layer. Thus the claim is explicitly conditional on complete validated immutable layers; the projection is not a replacement for a revision-bound consultation record. The report states 13 focused tests passed under CPython 3.12.14. This report-to-test and report-to-command relation is source-declared; exact CI execution-to-blob provenance is not independently asserted by this addendum.

### 11.2 RT-09 — ordered lowering from typed SPG

Current main contains `research/RT-09-ORDERED-SPG-LOWERING.md`, `src/spg_ordered_lowering.py`, and `tests/test_spg_ordered_lowering.py` in the Dependency Graph prototype family. The report declares 140 differential cases, binding-sensitive artifact identity, reachability-sensitive determinism, recursion/fuel behavior, and a trace mutation detected despite preserving the numeric result. It states that 16 focused tests passed under CPython 3.12.14. The supported scope is the experiment's scalar/effect profile and its two Python execution paths; this is not evidence of machine-code generation, general target preservation, independent IR admission, or full RT-05 conformance.

### 11.3 RT-26 claim pilot

The RT-26 cooperative reservation experiment and its [RT-00 B-05-02 claim-level traceability pilot](RT-00-B-05-02-RT26-CLAIM-TRACEABILITY-PILOT-2026-11-21.md) are now on current main, together with the four-method test module. The pilot uses report-local identifiers R26-C01–R26-C04 and records an independent execution of the exact current test source blob under CPython 3.13.5: 4/4 methods passed with zero failures or errors. The historical PR #129 run still lacks a retained execution-to-blob digest; the independent run verifies the current test blob under CPython 3.13.5, not the declared CPython 3.12.14 environment. The evidence remains limited to a fixed acyclic task hierarchy and cooperative cumulative budgets. It does not validate instantaneous resource limits, CPU/disk/network accounting, OS enforcement, throttling, handlers, fairness, or production atomicity. The local IDs remain pilot-scoped and do not establish a global Claim ID namespace.

### 11.4 Updated graph interpretation

These additions improve the concrete chain for three bounded studies:

- RT-06: research question → report result → exact test methods/fixture → declared command/environment;
- RT-09: research question → report result → lowering implementation/test methods → declared differential oracle/command/environment;
- RT-26: local falsifiable claims → report sections → exact test methods/source blob → independent bounded execution, with an explicit runtime-version discrepancy.

They do not close the corpus-wide gaps listed in §1. In particular, the corpus still lacks a global stable Claim ID namespace; exact execution-to-blob provenance is not uniform; tests discovered/declared/executed/passed/supporting claims remain distinct; and PLAN scheduling links are not exit-criterion evidence. No claim is inferred solely from file proximity or shared RT labels. No architecture decision is made.

## 10. Current-main traceability refresh — RT-06, RT-09, RT-13, RT-24 and RT-26 (2026-11-21)

This section extends the original graph baseline with later bounded studies present on current main. It does not claim a corpus-wide graph closure.

### RT-06 — negative lookup dependencies

`research/RT-06-SCOPED-BINDING-READ-DEPENDENCIES.md` maps to `tests/test_rt06_negative_binding_reads.py` and `tests/test_scoped_binding.py` in the Dependency Graph prototype. The declared suite was independently rerun on exact checkout `8d2c085f31685457a66669a6d4db604ab7b1c80a` under CPython 3.12.14: 13/13 passed in [run #44948779526](https://github.com/aivibeflow/LLMLang/actions/runs/44948779526), artifact [14724810775](https://github.com/aivibeflow/LLMLang/actions/runs/44948779526/artifacts/14724810775). The result supports a bounded per-key projection over complete validated layers, not a complete Action Key or general dependency closure.

### RT-09 — ordered SPG lowering

`research/RT-09-ORDERED-SPG-LOWERING.md` maps to `src/spg_ordered_lowering.py` and `tests/test_spg_ordered_lowering.py` plus the representation tests. The exact declared suite passed 16/16 under CPython 3.12.14 in the same [run #44948779526](https://github.com/aivibeflow/LLMLang/actions/runs/44948779526). It is Python-level intermediate lowering evidence; it does not establish LLVM, machine-code, or general source-to-runtime preservation.

### RT-13 — WebAssembly memory32 logical byte views

`research/RT-13-WASM-MEMORY32-VIEWS.md` maps to `research/PROTOTYPES/WASM-VIEWS-01/compare.mjs`. The report declares 12,800 differential observations against a JavaScript BigInt oracle and two negative controls: narrowing before the logical bound and relying only on linear-memory bounds. It records Node v24.22.1 and WABT 1.0.36, plus exact WAT/archive hashes. This is report-declared bounded engine evidence; no retained workflow run is cited here. Arbitrary descriptors, capability forgery, memory growth, allocation lifetime, instrumentation, compiler generation and cross-engine comparison remain open.

### RT-24 — exact call-target merge

`research/RT-24-CALL-TARGET-MERGE.md` maps to `tests/test_rt24_call_target_merge.py` and the existing semantic merge/tree gate fixtures. The declared test command was independently rerun on exact checkout `fa98a20c8ab5d3f28980b609c04aaec135dddde5`: 18/18 passed under CPython 3.12.14 and Git 2.56.1 in [run #44950912463](https://github.com/aivibeflow/LLMLang/actions/runs/44950912463), artifact [14725820800](https://github.com/aivibeflow/LLMLang/actions/runs/44950912463/artifacts/14725820800). The run captures exact source hashes and log digest `e8896e6e060b87235e1c9ef7f74dae922d302c2823216c6f4ec2f3000f834b80`. The report declares Git 2.52.0, while the retained run used Git 2.56.1; exact reproduction under the declared Git version remains open. The result demonstrates a narrow structural merge law for exact retargets in an unchanged caller declaration, with conflict on competing edits to the same selector and fail-closed behavior for unresolved upstream pins. It does not prove arbitrary source occurrence continuity, compatibility, mapping publication, or general merge completeness.

### RT-26 — cooperative reservation and cancellation settlement

`research/RT-26-COOPERATIVE-BUDGET-RESERVATION.md` and `research/RT-26-CANCELLATION-ACCOUNTING.md` map to the two budget prototype suites. Both were rerun under CPython 3.12.14 from exact checkout `00857e7dee48d0026e6d47c776c8792f6f1f245d`: cancellation 3/3 and reservation 4/4 passed in [run #44949563913](https://github.com/aivibeflow/LLMLang/actions/runs/44949563913), artifact [14724622101](https://github.com/aivibeflow/LLMLang/actions/runs/44949563913/artifacts/14724622101). This supports two cooperative cumulative-budget models only; instantaneous dimensions and production enforcement remain unresolved.

### Graph status

These additions provide more explicit report-to-test-to-run edges for RT-06, RT-09 and RT-26, and report-to-test declarations for RT-24. RT-13 has a report-declared comparison and source but no retained exact workflow run. The global Claim ID namespace, per-claim evidence edges across all scenarios, full test discovery/execution/support distinction, and PLAN exit-criterion closure remain unresolved. No file-level classification is promoted to claim-level evidence.

## 11. RT-07 source-bound CPC refutation — direct-path evidence (2026-11-21)

Current main adds `research/RT-07-SOURCE-BOUND-CPC-REFUTATION.md` and the Lean implementation/test files `SourceCpcRefutation.lean` and `SourceCpcRefutationTests.lean` under the Dependency Graph Logos-binding prototype.

The direct path reconstructs the relational query from typed source, observation contract, scope and factor; binds expected declarations against retained CPC parser state; structurally compares the complete ordered assumption list; and accepts only a complete Logos `.correct` verdict. The controls include a valid refutation of the wrong query, replay against an input-dependent source, reordered assumptions, undeclared factor, missing derivation, and solver-emitted aliases outside the admitted declaration shape.

This establishes an executable source-bound CPC check for the tested fragment and directly addresses one portion of Scenario 34's source-derived CPC assumption gap. It does not close the JSON/wire path, general alias admission, universal denotation preservation through every renderer/parser state, or a new Logos soundness theorem. The report declares Lean 4.36.0 and the pinned Logos revision; this addendum does not claim an independently retained exact workflow run for the new test driver. The result is bounded evidence, not full Scenario 34 closure.

## 12. RT-24 exact call-target merge reproduction (2026-11-21)

The RT-24 exact call-target merge suite was independently rerun using the report's declared unittest command on exact checkout `fa98a20c8ab5d3f28980b609c04aaec135dddde5` under CPython 3.12.14. All 18 tests passed in [workflow run #44950912463](https://github.com/aivibeflow/LLMLang/actions/runs/44950912463); retained artifact [14725820800](https://github.com/aivibeflow/LLMLang/actions/runs/44950912463/artifacts/14725820800), digest `sha256:d5085926c0fe1dfe0a81b4ba1619df422bbecc9b3e9590668e4381ecab78ecf1`. The artifact records SHA-256 for the report, three test modules and two imported implementation modules, plus the complete log and digest `e8896e6e060b87235e1c9ef7f74dae922d302c2823216c6f4ec2f3000f834b80`.

The actual runner Git version was 2.56.1, not the report's declared 2.52.0. The exact Git 2.52.0 environment is therefore not yet reproduced. The 18/18 result is bounded evidence for the tested fixture only.
