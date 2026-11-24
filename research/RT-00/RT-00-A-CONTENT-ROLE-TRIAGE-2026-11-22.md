# RT-00 A — Content-role triage of newly inventoried artifacts

**Date:** 2026-11-22  
**Baseline:** current-main research tree audited at `fc717d9c5a69085d7a524fd6dfc27145f0c35a1c`; PR branch additionally contains the RT-00 A freshness report.  
**Scope:** the 24 research paths absent from the prior 554-record inventory manifest.  
**Disposition:** first-pass individual role triage completed for all 24 paths, including 11 prototype artifacts. This is not claim-level validation, test execution, or independent reproduction.

## 1. Method and boundaries

Each file was read sufficiently to identify its declared purpose, structure, imports/paired tests, explicit research-area declarations, and direct cross-references. The primary semantic owner and candidate PLAN stage are recorded only where supported by the file's own content and the corresponding research/PLAN context. Related areas are included only when the artifact explicitly connects to them.

The review distinguishes implementation/proof source from paired tests or host harnesses, research reports/proposals from executable artifacts, and content-role triage from execution evidence and independent reproduction. No test is marked as passing solely because a test file exists or a reproduction command is documented. No candidate design is promoted to a normative rule.

## 2. Individual role mapping

| Path | Category | Primary role / research area | PLAN stage | Review basis and boundary |
|---|---|---|---:|---|
| `research/CHANGESET-VERIFICATION-AND-ACCEPTANCE-GATE.md` | Design analysis | Candidate Change Set verification/acceptance lifecycle; RT-19, related RT-05/06/07/08/20/24 | 7 | User-confirmed discussion synthesis and candidate Toolchain behavior; not final MCP schema or normative contract |
| `research/RT-00-B-05-02-RT26-CLAIM-TRACEABILITY-PILOT-2026-11-21.md` | Audit report | RT-26 claim-level traceability pilot | 0, 7 | Four local claim IDs, source/test links and explicit incomplete execution-to-blob binding; scoped to cooperative reservation only |
| `research/RT-07-CPC-NULLARY-ALIAS-BINDING.md` | Research experiment report | RT-07 CPC declaration versus nullary proof-alias binding | 2 | Explicit Plan §2.3 link, alternatives, controls and reproduction instructions; bounded parser profile |
| `research/RT-07-SOURCE-WIRE-LOGOS-ACCEPTANCE.md` | Research experiment report | RT-07 source-owned wire to CPC/Logos acceptance | 2 | Explicit SCW-31–34 scope and staged source/wire, assumptions, and complete-verdict checks; not a general proof-trust result |
| `research/RT-07-WIRE-SYMBOL-RENAMING.md` | Research experiment report | RT-07 typed wire-symbol renaming preservation | 2 | Defines typed rename/evaluation-preservation boundary and reproduction; limited to typed query grammar |
| `research/RT-09-STRUCTURAL-TYPE-IDENTITY-LAYOUT-AND-C-ABI-PROPOSAL.md` | Design proposal | Structural identity, type requirements, target layout, and function ABI; RT-03/04/05/09 | 1, 5, 6 | Explicit research-area and related-document declarations; architecture proposal, not accepted ABI implementation |
| `research/RT-13-LLVM-WASM-BYTE-VIEW-LOWERING.md` | Research experiment report | RT-13 LLVM lowering of checked byte-view IR to Wasm memory32 | 6 | Explicit Plan §6.3 link, workload/results and reproduction; bounded view fragment, not general Wasm preservation |
| `research/RT-23-COORDINATED-REF-GENERATION.md` | Research experiment report | RT-23 monotonic generation alongside Git ref publication | 4 | Explicit Plan §4.5 link; tests ABA-style branch movement under coordinated writer assumptions |
| `research/RT-23-MAPPING-TREE-PUBLICATION.md` | Research experiment report | RT-23 publication of exact interface mapping with semantic/Git tree | 4 | Explicit Plan §4.5 link; binds mapping bytes/catalog to prepared tree in a local fixture |
| `research/RT-24-SEMANTIC-PATCH-RECONCILIATION.md` | Research experiment report | RT-24 independent semantic patch composition versus Git replay | 4 | Explicit Plan §4.5 link; bounded replay correspondence, not a general merge guarantee |
| `research/RT-25-RUST-SYSTEM-ALLOCATOR-COMPATIBILITY.md` | Research experiment report | RT-25 Rust System allocator compatibility with Linux providers | 7 | Explicit RT-25 and Plan §7.1 link; one bounded native compatibility probe, not allocator selection or benchmark completion |
| `research/STRUCTURE-CONTRACTS-AND-ATOMIC-COMMIT-VERIFICATION.md` | Design synthesis | RT-03 structure contracts/invariant composition/atomic commit; related RT-04/06/07/08/19/20/22/23 | 1, 2, 4, 5 | Explicit primary and related areas; user-confirmed discussion synthesis, candidate semantics only |
| `research/STRUCTURE-INHERITANCE-COMPOSITION-AND-TEMPLATE-SPECIALIZATION.md` | Design synthesis | RT-03 inheritance/composition/template specialization; related RT-04/06/07/08/20 | 1, 5 | Explicit primary and related areas; user-confirmed candidate model, unresolved points retained |
| `research/PROTOTYPES/ALLOCATOR-COMPAT-01/probe.rs` | Prototype implementation | RT-25 process allocator/provider compatibility probe | 7 | Rust System and C allocation APIs; checks provider identity, zeroing, alignment, resize ownership and failure preservation; source presence is not run evidence |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/CpcNullaryAliases.lean` | Prototype implementation/proof | RT-07 raw CPC declaration/alias classification and parser-state binding | 2 | Lean module classifies declarations versus nullary aliases and checks consistency with parsed state |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/CpcNullaryAliasesTests.lean` | Prototype test evidence | RT-07 alias-binding positive and negative controls | 2 | Paired Lean test entry point covers aliases, shadowing, extra declarations, wrong sorts and alternate declaration forms; no pass claim from file presence |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/QuerySymbolRenaming.lean` | Prototype implementation/proof | RT-07 typed query symbol renaming and evaluation preservation | 2 | Defines typed renaming and pullback environment with evaluator preservation theorem |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SourceWireRefutation.lean` | Prototype implementation | RT-07 source-owned wire, CPC assumptions and Logos verdict gate | 2 | Composes source-envelope decoding, canonical assumption check and complete Logos verdict |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SourceWireRefutationTests.lean` | Prototype test evidence | RT-07 source-to-wire-to-Logos acceptance controls | 2 | Paired Lean controls cover altered envelope, wrong assumptions, changed source and invalid derivation |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt23_mapping_tree_publication.py` | Prototype test evidence | RT-23 exact interface-mapping publication | 4 | Python test fixture binds catalog/mapping bytes to closed semantic snapshot and Git tree publication |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt23_ref_generation.py` | Prototype test evidence | RT-23 coordinated ref-generation/ABA rejection | 4 | Python tests exercise generation token changes across branch move-away-and-back histories |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_replay_patch_correspondence.py` | Prototype test evidence | RT-24 replay-to-semantic-patch correspondence | 4 | Python tests compare native replay trees with independent semantic patch composition and negative controls |
| `research/PROTOTYPES/LLVM-PRESERVATION-01/llvm_wasm_view_probe.py` | Prototype implementation | RT-13 LLVM-to-Wasm memory32 lowering probe | 6 | Reuses checked LLVM view IR/reference evaluator, compiles O0/O3 and invokes Wasm host; exact runtime result still requires a retained run |
| `research/PROTOTYPES/LLVM-PRESERVATION-01/wasm_view_host.mjs` | Prototype test harness | RT-13 Wasm execution/observation harness | 6 | Node host compares statuses/values and sentinel/memory preservation over the supplied finite corpus; harness is not itself a reproduction record |

## 3. Prototype-family role-review reconciliation

The manifest's prior `semantic_traceability_review.prototype_family_review.individually_mapped_files` value was 242. The 11 prototype files above were individually content-role-triaged in this pass:

| Family | Previous individually mapped | Newly reviewed | Updated individually mapped |
|---|---:|---:|---:|
| DEPENDENCY-GRAPH-01 | 103 | 8 | 111 |
| LLVM-PRESERVATION-01 | 3 | 2 | 5 |
| ALLOCATOR-COMPAT-01 | 0 | 1 | 1 |
| **Total** | **242** | **11** | **253** |

The exact current tree contains 289 prototype paths. The updated individual role-triage total is 253, leaving 36 paths outside that recorded total. The remaining 36 are not assigned individual roles in this pass. The 11 newly reviewed files do not change the execution/reproduction status of any experiment.

## 4. Evidence and decision boundaries

- RT-07 Lean sources and tests are classified by their typed parser/query/proof roles. This report does not claim a fresh Lean build or Logos run.
- RT-23/24 Python files are test modules. This report does not claim that each new test module passed on the audited main commit.
- RT-13 Python/Node files are a compiler probe and host harness. Their documented result counts are report claims, not a new execution in this triage.
- RT-25 Rust source is a native compatibility probe. It does not establish a comparative allocator benchmark, safe process-wide production policy, or target portability.
- The Change Set, structural type/ABI, structure contract, and inheritance documents remain candidate design/discussion synthesis.
- The RT-26 pilot is limited to one cooperative cumulative-budget model and explicitly leaves broader resource enforcement open.

**Conclusion:** the 24 previously absent paths now have individual content-role triage. Eleven prototype paths increase the historical individually role-triaged prototype total from 242 to 253. The corpus still has 36 prototype paths outside that total, and corpus-wide claim validation, reproducibility, duplicate/supersession/orphan/contradiction review, and RT-00 closure remain open.
