# Research Corpus Semantic Relationship Review — Scenario Studies — 2026-11-20

**Status:** first-pass semantic relationship triage; not a complete corpus-wide duplicate/orphan/contradiction audit  
**Baseline:** `main` at `422f77d5340ffbfeb1f00d301f8ba1bc86760070`  
**Scope:** 136 scenario-named report files under `research/`, including supplemental reports, plus current research-tree exact-blob identity groups  
**Normative status:** evidence classification only; no LLMLang architecture, language, type-system, or runtime decision is made

## 1. Purpose

This review distinguishes semantic duplication from related research, follow-up experiments, partial supersession, and historical material. Similar titles, shared fixtures, a common RT area, or adjacent scenario numbers are not sufficient evidence that two documents are duplicates.

The review preserves historical reports and their results. It records relationships between artifacts; it does not rewrite old conclusions to make them appear consistent with later work.

## 2. Method and limits

The first pass:

1. Enumerated all 136 scenario-named Markdown report files in the reviewed Git tree.
2. Compared each report's title, status, research-area declaration, question, stated scope, and explicit predecessor/follow-up references.
3. Read the full content of selected high-overlap candidates, including Scenarios 31–32, 35, 39–40, 94–95 and its execution report, 97–98, 102, 112, and the relevant cross-cutting research documents.
4. Compared every tracked blob under `research/` by Git blob SHA to identify exact byte duplicates.
5. Cross-checked the existing Semantic Traceability Report, Corpus Audit, taxonomy, research index, and PLAN.md §0.1.

This is a **first-pass relationship review**, not a claim that every paragraph of all 136 reports has received a line-by-line semantic comparison. The candidate clusters below require deeper review where noted. No absence-of-duplicate claim should be interpreted as proof that no semantic duplication exists.

## 3. Classification rules

| Relationship | Meaning in this review |
|---|---|
| Exact duplicate | Same content identity; for files, identical Git blob SHA |
| Semantic duplicate | Different bytes, but materially the same question, inputs, checked properties, evidence, and conclusion, with no meaningful independent role |
| Partial overlap | Documents share a sub-question, fixture, or evidence dimension, while retaining distinct scope or results |
| Related follow-up | A later document extends, operationalizes, or tests a clearly identified earlier question |
| Superseded section | A bounded section or proposal is replaced; the rest of the source document remains relevant |
| Historical background | A proposal or result is no longer current, but remains useful to explain alternatives, provenance, or prior reasoning |
| Unresolved | Available evidence does not justify choosing among the above relationships |

These labels describe document relationships, not the correctness or acceptance of the underlying research conclusions.

## 4. Exact-identity result

The recursive Git tree contains one repeated blob group under `research/`:

| Files | Result |
|---|---|
| `references/snapshots/OCI/LICENSE-APACHE-2.0.txt` and `references/snapshots/REAPI/LICENSE-APACHE-2.0.txt` | Identical Apache-2.0 licence text, same blob SHA and size; expected colocated licence copies for separate snapshots |

This is an exact byte duplicate, but **not duplicated research**. Both copies are retained for snapshot attribution. No other exact duplicate blob group was found in the reviewed research tree.

Exact-blob comparison cannot detect semantic duplicates or partial overlaps.

## 5. Confirmed scoped supersession

Three section-level cases are already evidenced in the inventory and the Semantic Traceability Report. The present review confirms their limited scope:

| Source | Superseded portion | Successor | Retained value |
|---|---|---|---|
| Scenario 31 | First text-based query representation | Scenario 32 typed canonical query IR v2 | Scenario 31's strict QF_LIA profile, incompatibility analysis, and prior-art comparison remain relevant |
| Scenario 32 | §9 parser-state bridge sketch | Compiled implementation under `PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/` | Typed query IR, versioned envelope, renderer boundary, and remaining source-to-query correspondence obligations remain relevant |
| `GIT-SEMANTIC-REPOSITORY.md` | Embedded ADR-0001 proposal making external KV the authoritative semantic store | Proposed ADR-014 and `GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md` | The broader historical research, alternatives, and Git integration analysis remain useful |

No entire scenario or research document is classified as superseded by these cases. Proposed ADR-014 remains proposed; this review does not promote it to an accepted architecture decision.

## 6. Companion and follow-up reports

| Relationship | Classification | Evidence and boundary |
|---|---|---|
| Scenario 95 and `RESEARCH-SCENARIO-95-EXECUTION-2026-11-20.md` | Same research item with a supplemental execution report | The execution report explicitly names Scenario 95 as its research item. The original is a comparative study; the supplement checks current external references and LLMLang boundaries. Neither reports a human-subject or coding-agent experiment, and the two files are not duplicate independent scenarios. |
| Scenario 94 → Scenario 112 | Related follow-up | Scenario 94 is a broad prior-art comparison and experiment design. Scenario 112 is a finite two-task cycle model distinguishing weak, strong, and bounded fairness. It does not validate a real runtime or general liveness. |
| Scenario 53 → Scenario 89 | Related extension | Scenario 89 adds ECMAScript's grammar-driven ASI and restricted productions to the earlier statement-termination comparison. It does not repeat the full comparison or select a language policy. |
| Scenario 86 → Scenario 87 | Related follow-up | Scenario 86 compares async/await syntax and context boundaries. Scenario 87 turns selected syntax/context distinctions into a proposed parser/diagnostic corpus; the fixtures have not been run against an LLMLang parser. |
| Scenario 96 → Scenarios 96A and 96B | Parent study plus bounded experiments | Scenario 96 defines LLVM poison/UB and semantic-preservation obligations. 96A tests integer preservation; 96B tests byte-view bounds and origin. The bounded target-specific results do not supersede the broader study. |
| Scenario 62 → Scenario 109 | Related follow-up | Scenario 62 compares optional/nullability semantics. Scenario 109 tests omitted, null, and present values at one JSON boundary; it is not a general optional-type or ABI implementation. |
| Scenarios 109–111 → Scenario 134 | Related comparative follow-up | Scenarios 109–111 provide bounded JSON presence, schema-evolution, and unknown-variant fixtures. Scenario 134 compares real interchange-format standards. Its accepted applicability note classifies it as prior-art/reference material, not an active runtime requirement under the current same-build compatibility decision. |
| Scenario 119 → Scenarios 120–133 | Related experiment sequence | Scenario 119 models owned-result matching. Later scenarios progressively examine SQLite close/dependency behavior, freshness, call boundaries, synchronization, reentry, backup roles, cancellation evidence, durable results, caller recovery, and generated Rust. Their shared workload and references are intentional traceability, not duplicate experiments. |
| Scenario 131 → Scenario 132 → Scenario 133 | Related implementation/evidence sequence | Scenario 131 compares transfer rules on a shared workload; 132 examines typed caller recovery; 133 checks a bounded generated-Rust path. The reports test different boundaries and must not be collapsed into one result. |

## 7. Partial overlaps that remain distinct

The following clusters share research questions or evidence inputs. The reviewed questions and stated boundaries do not justify merging them or marking one whole report superseded.

| Cluster | Distinct responsibilities observed |
|---|---|
| Scenarios 5–8 | Name-free identity, content-addressed identity, stress tests for content-only identity, and context-derived occurrence addressing are different candidate identity models and discriminators. |
| Scenarios 20–24 | Dependency candidate discovery, counterfactual testing, candidate scheduling, multi-factor attribution, and adaptive experiment selection are separate stages of a research pipeline. |
| Scenarios 25–34 | Formal dependency foundations, symbolic queries, IR/proof boundaries, CPC/Logos integration, parser-state binding, and source-to-query correspondence are distinct obligations. Scenario 31/32 section-level supersession is recorded separately above. |
| Scenarios 35, 39, 40, 65, 75, and 97 | Resource-return cleanup, cross-language cleanup mechanisms, asynchronous cancellation/cleanup completion, fatal failure/unwinding, automatic disposal triggers, and primary-outcome/secondary-cleanup-error composition are adjacent but distinct. |
| Scenarios 42 and 71 | Broad generic abstraction/dispatch comparison versus ownership and coherence of interface implementations. |
| Scenarios 43, 81, and 82 | Module/package boundaries and initialization, import binding syntax, and source-file structure/top-level code are different language-design questions. |
| Scenarios 45, 73, 78, and 83 | Numeric representation/overflow, literal typing/conversions, floating-point reproducibility, and numeric token grammar are separate semantic layers. |
| Scenarios 46, 76, and 79 | Runtime string encoding/indexing, regular-expression API/resource bounds, and source string-literal/interpolation syntax are separate contracts. |
| Scenarios 49, 59, 77, 84, and 88 | General operators/conversions, Boolean short-circuiting, call-argument evaluation order, function signature surface, and default-argument evaluation are distinct. |
| Scenarios 47, 54, 72, and 74 | Public record/variant evolution, pattern matching/exhaustiveness, sum-type layout/ABI, and refutable pattern failure/binding are separate source, type, and representation concerns. |
| Scenarios 57, 58, 86, and 87 | Task hierarchy/lifetime, async function types and scheduling, async syntax/context, and parser/diagnostic fixtures cover different layers. Scenario 40 separately covers cancellation and cleanup. |
| Scenarios 61 and 113–118 | Scenario 61 is broad prior-art on shared mutable state and memory models. Scenarios 113–118 isolate store buffering, release sequences, fences, backend lowering, coherence, and combined execution relations. |
| Scenarios 63 and 90–92 | Equality/identity/hash laws, runtime versus persistent hashing, versioned digest migration, and operation/implementation identity are distinct identity boundaries. |
| Scenarios 97–108 | Cleanup-error composition (97) is separate from the path-analysis sequence (98–108). Within 98–108, path coverage, repeated predicate identity, finite feasibility, solver comparison, UNKNOWN/UNSAT policy, real timeout isolation, mutable state, call mutation, alias sets, source-derived aliases, and path-sensitive precision are successive discriminators. |
| Scenarios 109–111 and 134 | Optional presence, record evolution/defaults, unknown variants, and cross-format standards comparison are related serialization topics, not the same property or evidence. |
| Scenarios 113–118 | The reports isolate different memory-order premises and then combine them. A common atomic fixture or repeated prior-art reference does not make the results interchangeable. |

### 7.1 Resource-lifecycle cluster: explicit boundary

The highest-risk overlap candidate is Scenarios 35, 39, and 97:

- **Scenario 35** compares when ownership of a pending return value moves to the caller relative to fallible cleanup of another local resource. Its key discriminators are staged return versus transfer-first, pending-result cleanup, and whether an error can carry an owned value.
- **Scenario 39** compares Zig, Rust, Swift, and Go cleanup mechanisms on the owned-return/fallible-cleanup boundary. It is primarily a language-mechanism comparison and does not settle LLMLang's cleanup-error policy.
- **Scenario 97** studies the algebra that combines a primary outcome with one or more ordered cleanup failures, including cancellation, fuel exhaustion, panic, and ownership/debt projection. Its bounded model covers multiple cleanup policies and outcomes.

These reports partially overlap on ownership and cleanup failure, but differ in the principal question, comparison method, and checked dimensions. Preserve all three and retain explicit cross-links. A future review may identify a duplicated subsection or fixture; the present evidence does not justify document-level supersession.

Scenarios 40, 65, and 75 are adjacent rather than duplicates: cancellation completion, fatal unwind behavior, and the trigger/determinism of automatic disposal are not implied by the owned-return or cleanup-error models.

## 8. Orphan and unresolved findings

1. **Scenario 16 is absent.** The corpus contains 136 scenario-named report files representing 135 unique scenario IDs: Scenario 95 has a main report and a supplemental execution report; Scenario 16 has no report. Whether 16 was reserved or a report is missing remains `unresolved`. Do not renumber the corpus or invent a missing report.
2. **No orphan scenario report is confirmed by this first pass.** The report-to-RT crosswalk and explicit predecessor/follow-up references provide navigation evidence, but this is not a complete inbound-link or semantic-dependency scan.
3. **Stage 0-only records are not automatically orphans.** The existing traceability review intentionally classifies seven reference/provenance files and one prototype-family README as corpus-navigation/provenance artifacts rather than substantive RT research.
4. **No semantic duplicate is confirmed in the reviewed scenario clusters.** The first-pass relationships are partial overlaps, related follow-ups, or scoped supersession. Full-content comparisons and evidence-graph checks remain necessary before closing this question.
5. **No contradiction is confirmed by this scenario-level triage.** Similar terminology across reports is not enough to establish a contradiction. Cross-cutting definitions and claim-level premises require the separate review in the next passes.

## 9. Required next work

- Inspect full contents and claim/evidence boundaries for every candidate cluster in §7, prioritizing Scenarios 35/39/97, 57/58/86/87, 61/113–118, 97–108, and 119–133.
- Compare scenario inputs, observations, assumptions, result tables, and reproduction commands—not just questions and titles.
- Record any confirmed semantic duplicate or partial duplicate at the smallest meaningful section/fixture level; preserve all source documents.
- Build the source/test/fixture/report graph in the prototype-family review before classifying implementation artifacts as orphaned.
- Repeat link and anchor checks independently; this document does not claim to validate all relative links, external links, or Markdown anchors.

**Conclusion:** this pass establishes a conservative relationship map and confirms three existing section-level supersession cases. It finds one expected exact duplicate licence blob pair and no confirmed semantic duplicate among the inspected scenario relationships. The scenario corpus is connected by deliberate follow-ups and layered evidence; those connections must not be mistaken for duplicated research or for proof that the related claims are equivalent. The corpus-wide semantic audit remains open.


## 10. Selected source reports

The full 136-file scenario inventory and candidate RT crosswalk are in the [Semantic Traceability Report](RESEARCH-CORPUS-SEMANTIC-TRACEABILITY-2026-11-20.md). The following primary reports were opened for the detailed relationship checks above:

- **Scoped supersession:** [Scenario 31](../formal-verification/RT-07/RESEARCH-SCENARIO-31-STRICT-QF-LIA-PROFILE.md), [Scenario 32](../formal-verification/RT-07/RESEARCH-SCENARIO-32-CANONICAL-TYPED-RELATIONAL-QUERY-IR.md), [Git Semantic Repository](../toolchain-and-collaboration/RT-15/GIT-SEMANTIC-REPOSITORY.md), and [Git Representation and Semantic Merge](../toolchain-and-collaboration/RT-15/GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md).
- **Companion/follow-up reports:** [Scenario 95](../toolchain-and-collaboration/RT-17/RESEARCH-SCENARIO-95-DIAGNOSTICS-FOR-HUMANS-AND-AGENTS.md), [Scenario 95 Execution](../toolchain-and-collaboration/RT-17/RESEARCH-SCENARIO-95-EXECUTION-2026-11-20.md), [Scenario 94](../runtime-and-systems/RT-10/RESEARCH-SCENARIO-94-SCHEDULER-FAIRNESS-AND-LIVENESS.md), [Scenario 112](../runtime-and-systems/RT-10/RESEARCH-SCENARIO-112-WEAK-STRONG-AND-BOUNDED-FAIRNESS.md), [Scenario 53](../language-design/RT-03/RESEARCH-SCENARIO-53-STATEMENT-TERMINATION-AND-NEWLINES.md), [Scenario 89](../language-design/RT-31/RESEARCH-SCENARIO-89-ECMASCRIPT-AUTOMATIC-SEMICOLON-INSERTION.md), [Scenario 86](../language-design/RT-31/RESEARCH-SCENARIO-86-ASYNC-AWAIT-SYNTAX-AND-CONTEXTS.md), and [Scenario 87](../language-design/RT-31/RESEARCH-SCENARIO-87-ASYNC-AWAIT-PARSER-DIAGNOSTIC-CORPUS.md).
- **Resource lifecycle:** [Scenario 35](../language-design/RT-04/RESEARCH-SCENARIO-35-RESOURCE-RETURN-AND-CLEANUP.md), [Scenario 39](../language-design/RT-04/RESEARCH-SCENARIO-39-CLEANUP-FAILURE-AND-OWNERSHIP-TRANSFER.md), [Scenario 40](../language-design/RT-04/RESEARCH-SCENARIO-40-ASYNC-CANCELLATION-AND-CLEANUP.md), [Scenario 65](../language-design/RT-03/RESEARCH-SCENARIO-65-FATAL-FAILURE-AND-UNWINDING.md), [Scenario 75](../language-design/RT-04/RESEARCH-SCENARIO-75-AUTOMATIC-DISPOSAL-AND-LIFETIME.md), and [Scenario 97](../language-design/RT-04/RESEARCH-SCENARIO-97-CLEANUP-ERROR-COMPOSITION-AND-OWNERSHIP.md).
- **Evidence layering:** [Scenario 96](../compiler-and-translation/RT-13/RESEARCH-SCENARIO-96-LLVM-UB-POISON-AND-SEMANTIC-PRESERVATION.md), [Scenario 96A](../compiler-and-translation/RT-13/RESEARCH-SCENARIO-96A-LLVM-INTEGER-PRESERVATION.md), [Scenario 96B](../compiler-and-translation/RT-13/RESEARCH-SCENARIO-96B-LLVM-BYTE-VIEW-PRESERVATION.md), [Scenario 62](../language-design/RT-04/RESEARCH-SCENARIO-62-OPTIONAL-VALUES-AND-NULLABILITY.md), [Scenario 109](../packages-and-ecosystem/RT-18/RESEARCH-SCENARIO-109-OPTIONAL-PRESENCE-ROUND-TRIP.md), [Scenario 110](../packages-and-ecosystem/RT-18/RESEARCH-SCENARIO-110-WIRE-SCHEMA-EVOLUTION-AND-DEFAULTS.md), [Scenario 111](../packages-and-ecosystem/RT-18/RESEARCH-SCENARIO-111-UNKNOWN-WIRE-VARIANT-PRESERVATION.md), and [Scenario 134](../packages-and-ecosystem/RT-18/RESEARCH-SCENARIO-134-WIRE-SCHEMA-EVOLUTION-INTEROPERABILITY.md).
- **Memory-model sequence:** [Scenario 61](../language-design/RT-04/RESEARCH-SCENARIO-61-CONCURRENT-MUTABLE-STATE-AND-MEMORY-MODEL.md), [Scenario 113](../language-design/RT-04/RESEARCH-SCENARIO-113-STORE-BUFFERING-MEMORY-ORDERS.md), [Scenario 114](../language-design/RT-04/RESEARCH-SCENARIO-114-RELEASE-SEQUENCES-AND-ACQUIRE-RELAY.md), [Scenario 115](../language-design/RT-04/RESEARCH-SCENARIO-115-FENCES-AND-SEQUENTIAL-CONSISTENCY.md), [Scenario 116](../compiler-and-translation/RT-13/RESEARCH-SCENARIO-116-ATOMIC-BACKEND-LOWERING-OBLIGATIONS.md), [Scenario 117](../language-design/RT-04/RESEARCH-SCENARIO-117-ATOMIC-WRITE-READ-COHERENCE.md), and [Scenario 118](../language-design/RT-04/RESEARCH-SCENARIO-118-ATOMIC-EXECUTION-RELATIONS.md).
- **Native lifecycle sequence:** [Scenario 119](../language-design/RT-04/RESEARCH-SCENARIO-119-OWNED-RESULT-MATCHING.md), [Scenario 120](../language-design/RT-04/RESEARCH-SCENARIO-120-SQLITE-CLEANUP-DEPENDENCIES.md), [Scenario 121](../language-design/RT-04/RESEARCH-SCENARIO-121-SQLITE-LOCAL-CLOSE-RECOVERY.md), [Scenario 122](../language-design/RT-04/RESEARCH-SCENARIO-122-CLOSE-EVIDENCE-FRESHNESS.md), [Scenario 123](../language-design/RT-04/RESEARCH-SCENARIO-123-CLOSE-CALL-BOUNDARY.md), [Scenario 124](../language-design/RT-04/RESEARCH-SCENARIO-124-CLOSE-SYNCHRONIZATION.md), [Scenario 125](../language-design/RT-04/RESEARCH-SCENARIO-125-CLOSE-REENTRY-AND-COVERAGE.md), [Scenario 126](../compiler-and-translation/RT-13/RESEARCH-SCENARIO-126-MULTI-RESOURCE-FFI-ROLES.md), [Scenario 127](../language-design/RT-04/RESEARCH-SCENARIO-127-SOURCE-ROLE-CORRELATION.md), [Scenario 128](../compiler-and-translation/RT-13/RESEARCH-SCENARIO-128-FOREIGN-RESERVATION-OUTCOMES.md), [Scenario 129](../runtime-and-systems/RT-10/RESEARCH-SCENARIO-129-CANCELLATION-AND-INVOCATION-EVIDENCE.md), [Scenario 130](../runtime-and-systems/RT-10/RESEARCH-SCENARIO-130-DURABLE-INVOCATION-RESULTS.md), [Scenario 131](../language-design/RT-04/RESEARCH-SCENARIO-131-SHARED-OWNED-RESULT-WORKLOAD.md), [Scenario 132](../language-design/RT-04/RESEARCH-SCENARIO-132-TYPED-CALLER-RECOVERY.md), and [Scenario 133](../compiler-and-translation/RT-13/RESEARCH-SCENARIO-133-GENERATED-RUST-OWNED-RESULTS.md).

These links provide evidence navigation for the detailed cases; they do not imply that every claim in the linked reports has been independently revalidated by this first pass.
