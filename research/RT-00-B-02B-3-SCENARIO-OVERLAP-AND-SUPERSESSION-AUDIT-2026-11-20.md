# RT-00 B-02b.3 — Scenario overlap, progression, and supersession audit

**Audit snapshot:** `dcbb3085bfc6fb45eaaf520ca27aef4e93a628ae`  
**Date:** 2026-11-20  
**Scope:** Research Scenarios 15 and 17–34, Prototype result records 16–24 and 26–29, and the `DEPENDENCY-GRAPH-01` family README.  
**Method:** cross-reference and status inspection of the current main tree. This is a semantic relationship audit; directory placement or numbering alone is not treated as evidence of a relationship.

## 1. Executive result

The research line is a sequence of related but distinct layers, not a set of duplicate implementations. Its main progression is:

- Scenarios 15 and 17–24: requirements, semantic dependency evidence, and experiment planning;
- Scenario 25: formal semantic dependency analysis as the proposed primary basis for dependency facts;
- Scenarios 26–29: finite semantics, symbolic relational analysis, typed IR/evidence, and external proof-process handling;
- Scenario 30: CPC assumption-binding source audit and design;
- Scenarios 31–32: strict QF_LIA query profile and canonical typed query/wire IR;
- Scenario 33: Lean parser-state/declaration binding and version-2 decoder;
- Scenario 34: Lean source semantics and proof of correspondence through the canonical relational query.

These layers overlap in subject matter but have different inputs, guarantees, and trust boundaries. The formal chain is intentionally narrower than the experimental Python prototypes.

## 2. Numbering and corpus registration

| Artifact | Current relationship | Disposition |
|---|---|---|
| `PROTOTYPE-16-RESULTS.md` | Explicitly links to Research Scenario 15 | Valid cross-number reference; do not infer a missing Scenario 16 solely from the prototype number |
| `RESEARCH-SCENARIO-16` | No such scenario document in the audited tree | No artifact to classify; retain the explicit Prototype 16 → Scenario 15 mapping |
| Scenarios 17–24 | Each has a corresponding prototype/result link for its own scenario number, with Scenario 15/Prototype 16 as the preceding exception | Direct scenario/prototype relationships |
| Scenario 25 | Research result/proposal; no `PROTOTYPE-25-RESULTS.md` or dedicated Scenario 25 Python module in this family | Research foundation, not an orphaned implementation |
| Scenario 30 | Source-level CPC assumption-binding analysis; no standalone Prototype 30 result/module | Design/audit artifact; later parser bridge is implemented under Scenario 33 |
| Scenario 31 | Design document later records the strict QF_LIA Python implementation and a follow-up typed IR | Preserve design history; top-level status needs a current-state note |
| Scenario 32 | Canonical typed query IR and version-2 wire format; parser bridge implementation is linked to Scenario 33 | Distinct data/serialization layer |
| Scenario 33 | Compiled Lean parser-state bridge and version-2 decoder | Parser-state/AST binding layer; explicitly not a source-to-query proof |
| Scenario 34 | Lean source semantics and SC-1–SC-7 correspondence | Current formal proof layer; remains in progress |

Scenario 25 was added to the plan and research indexes by PR #110. It does not need a matching prototype directory to be a valid research artifact.

## 3. Scenarios 15 and 17–24: requirements and experimental evidence

| Scenario / prototype | Primary question | Distinct contribution | Boundary that must remain explicit |
|---|---|---|---|
| 15 / Prototype 16 | Business intent to formal contract | Caller-scoped business rules, explicit clarification, provenance, human acceptance | No natural-language parser, authority system, or source implementation proof |
| 17 | Typed Requirement IR | Typed predicates, ownership/scope, provenance, finite-domain contradiction and underdetermination checks | No temporal logic engine, natural-language parsing, or implementation conformance |
| 18 | Requirement evolution | Immutable revisions, semantic dependencies, lineage, impact, split/merge, concurrent merge | Not a complete impact planner or proof of dependency completeness |
| 19 | Impact planning | Evidence-bound completeness states and conservative action planning | Does not discover dependencies, execute actions, or prove supplied non-interference certificates |
| 20 | Dependency discovery/classification | Evidence candidates from explicit/static/dynamic/proof observations with explicit classification | Consumes normalized observations; does not implement the discovery tools |
| 21 | Counterfactual dependency detection | Controlled paired-run evidence and scoped behavioral influence | Consumes run records; no executor, tracer, or universal non-dependence proof |
| 22 | Coverage-guided discovery | Deterministic finite-domain candidate generation, set-cover scheduling, coverage ledger | Planner only; no program execution or dependency-completeness proof |
| 23 | Multi-factor analysis | Joint interventions and repeated 2×2 interaction analysis | Consumes normalized runs; no executor or higher-order estimator |
| 24 | Adaptive interaction discovery | Single-factor-first, pairwise blocks, evidence-triggered higher-order scheduling | Planner only; no executor, constraint solver, or statistical nondeterminism model |

These are complementary stages. Scenario 20 classifies observations; Scenario 21 analyzes controlled run pairs; Scenario 22 schedules interventions; Scenario 23 analyzes multi-factor effects; Scenario 24 adapts future schedules using feedback. None subsumes the others.

Scenario 19 consumes completeness evidence and plans conservative actions; it is not the dependency-discovery mechanism. Scenario 18 models requirement-state evolution and lineage; it is not the action planner. These distinctions should be retained in the corpus taxonomy.

## 4. Scenario 25 and the formal semantic direction

Scenario 25 is a conceptual bridge from experimental dependency evidence to formal semantic dependency analysis. It distinguishes syntactic/read, data-flow, control, semantic may-dependency, proven independence, proven influence, proof dependency, observed dependence, and provenance.

Its architectural recommendation is to make formal semantic analysis the primary source of dependency facts, while retaining experimental discovery as a secondary channel for opaque or not-yet-modeled behavior. This does not invalidate Scenarios 20–24: those scenarios provide evidence and exploration mechanisms for behavior outside a proven model.

Scenario 25 is not itself a source implementation or proof result. Scenarios 26–34 are a restricted research path toward one formal realization of its relational-verification direction.

## 5. Scenarios 26–34: formalization and proof-checker progression

| Scenario | Input / artifact layer | What it contributes | What it does not establish |
|---|---|---|---|
| 26 | Python finite semantic core | Exact exhaustive results within declared finite domains; reference oracle | Unbounded proof, machine-checked evaluator correctness, source/compiler correspondence |
| 27 | Python symbolic relational encoder | Product-program-style SMT-LIB query; selected factor split, other inputs shared | Real Z3 integration in recorded environment, proof certificate checking, source correspondence |
| 28 | Python typed AST and evidence envelope | Validated Python fragment, query/tool identity, counterexample replay | Authenticated checker receipt, encoder soundness, independent proof checking |
| 29 | cvc5/Logos process adapter | Pinning, timeouts, proof-byte preservation, fail-closed process/status handling | Real cvc5/Logos proof integration or binding of checker assumptions to the intended query |
| 30 | Logos source audit and binding design | Identifies that the checker proves unsatisfiability of parsed CPC assumptions, which must be bound to the intended query | Implementation; its original “no Lean wrapper” status is superseded by Scenario 33 |
| 31 | Strict QF_LIA profile | Separate conservative Bool/Int query-building path; avoids silently narrowing Scenario 27 | Formal validation of Python encoder or source-to-query correctness; its original “no code changes” status is stale |
| 32 | Typed relational-query IR and JSON `/2` | Canonical typed query shared by separate SMT-LIB and Lean/Logos paths | Proof that the Python source encoder or JSON payload corresponds to source semantics |
| 33 | Lean parser-state bridge | Retains Logos parser state, resolves exact UConst identities, decodes version-2 query, structurally checks full assumption list on fixtures | Source-derived formula correctness; Scenario 33 explicitly says this is not source-to-query proof |
| 34 | Lean source semantics and relational query | Kernel-checked SC-1–SC-7 for the restricted deterministic Int/Bool fragment | Complete solver-facing declaration closure, wire-to-source formula theorem, source-derived CPC binding, full acceptance gate |

The transitions are intentional:
- Scenario 26's finite enumeration is a reference oracle, not a duplicate of Scenario 27's symbolic query.
- Scenario 27's broader symbolic API (including String) is deliberately kept separate from Scenario 31's narrower QF_LIA API.
- Scenario 31's initial direct/text-oriented query generation is superseded by Scenario 32's typed canonical IR, but the strict profile itself remains relevant.
- Scenario 29's process runner and Scenario 33's parser-state wrapper are different layers: one launches external binaries, the other binds parser identities and assumptions.
- Scenario 30's analysis is partly implemented by Scenario 33, but its proof-binding goal is not complete until the expected terms are source-derived.
- Scenario 34 formalizes source semantics independently; it does not retroactively verify the Python encoder.

## 6. Important non-contradictions at the Python/Lean/CPC boundary

Several documents may appear inconsistent unless their exact claim is preserved:

1. Scenario 32/33 report a Lean version-2 decoder, parser-state binding, and exact structural comparison of CPC assumptions. This is compatible with Scenario 34 leaving SCW-31–33 open: the bridge can validate a decoded query and compare assumptions against a Lean-generated expected term without proving that the decoded query is the formula derived from the source program's semantics.
2. Scenario 34 contains an adapter-preservation theorem, but SCW-32 remains open because the full proof obligation is not merely that one IR adapter preserves evaluation; it is to connect the proved source-derived formula to the Logos terms and parser-state identity boundary.
3. Scenario 29's lack of real cvc5/Logos integration is not contradicted by Scenario 33's parser-wrapper CI. The latter builds and exercises the parser bridge; it does not run a real cvc5-generated CPC proof through Logos.
4. Scenario 27's real-Z3 integration gap is not closed by Scenario 31's Python tests or by Lean CI. Those are separate test and proof layers.

The correct end-to-end statement remains: source-to-canonical-query semantics is proved for the Scenario 34 fragment; wire/source formula correspondence and source-derived CPC assumption binding remain open.

## 7. Documentation freshness and supersession

The following are historical claims or stale status lines and should be reconciled without deleting historical findings:

| Document | Stale or superseded text | Current evidence / recommended treatment |
|---|---|---|
| Scenario 30 | Top status says no Lean wrapper has been built | Scenario 33 subsequently implements the parser-state bridge; mark Scenario 30 as historical source audit/design and link the implementation |
| Scenario 31 | Top status says no code changes yet | §10 records the QF_LIA implementation and Scenario 32 follow-up; update top status to historical design with implementation cross-reference |
| Scenario 31 | Original focused run says 26 tests | Scenario 32 later records 27; current test module has 30 methods and runs in Required CI |
| Scenario 32 | Top status says pinned Lean CI is running | Scenario 33 records completed parser bridge CI; current Required CI run #44801357527 passed on the audited repository line |
| Scenario 33 | Mentions Lean 4.34.0 and old CI runs | Current `lean-toolchain` and workflow pin Lean 4.36.0; update the current-state evidence while preserving historical run links |
| Scenario 34 | §7.2 still says Lean 4.34.0 and old CI run IDs | Current pin is Lean 4.36.0; Required CI run #44801357527 passed on the current main lineage |
| Family README | Says Lean 4.34.0 and cites run #44766546452 as latest relevant | Update to Lean 4.36.0 and cite current exact-HEAD Required CI evidence |

The SCW-04 audit is explicitly labeled historical and has a current-source addendum. The SCW-05 breakdown is now marked Complete within its deliberately narrow declaration-context data-model scope. Those two records do not need to be rewritten as if their original findings were current.

## 8. Conclusion and disposition

**Disposition: B-02b.3 scenario relationship and supersession classification complete at the document level.**

No direct duplicate implementation was found among Scenarios 15 and 17–34. The main risks are stale status/version/CI references and ambiguous number-based assumptions, not duplicate research artifacts.

Recommended follow-up is a separate documentation-reconciliation change: preserve historical content, update current status headers and links, and keep the open Scenario 34 obligations visible. Do not merge or erase the research-only status of Scenarios 25 and 30.
