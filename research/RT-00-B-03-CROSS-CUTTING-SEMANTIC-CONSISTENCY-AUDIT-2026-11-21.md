# RT-00-B3 — Cross-cutting Semantic Consistency Audit — 2026-11-21

**Status:** bounded semantic audit; findings and unresolved boundaries recorded  
**Baseline:** main at bd6daf5fb2ebfdc384eb00c46a81df3b84be11dc  
**Inventory:** research/RESEARCH-CORPUS-INVENTORY-2026-11-20.json at the same baseline  
**Scope:** identity, SPG, contracts/evidence, dependency completeness, cache/action identity, package identity, compiler/backend preservation, runtime/resource accounting, and security/authority boundaries  
**Decision boundary:** audit only. No candidate identity scheme, semantic profile, backend, allocator, runtime policy, or resource-enforcement model is accepted.

## 1. Executive result

The reviewed documents are broadly consistent about one central separation: semantic identity, action/cache identity, artifact-byte identity, provenance, and evidence are different concerns. They are not yet integrated into one complete, normative model.

This review found:
- No demonstrated direct contradiction requiring an immediate architectural choice in the reviewed core documents.
- Seven material unresolved cross-document boundaries where independently coherent proposals still lack a binding definition or end-to-end validation.
- Two known terminology/status issues that remain active and must not be silently normalized.
- One important evidence limitation: the RT-05 SPG experiment does not validate ownership, resource accounting, concurrency, FFI, or compiler lowering; RT-26 remains Not started. The SPG model's inclusion of resource-related graph concepts must therefore not be read as validation of resource semantics.

This is a semantic consistency pass over the documents listed in §8, not a claim that all 487 baseline inventory records or every claim in all 26 RT areas have been content-validated.

## 2. Consistency matrix

| Cross-cutting domain | Documents compared | Finding | Status |
|---|---|---|---|
| Semantic identity and managed continuity | LLMLang Concept §§3–4; RT-05 Typed SPG §§3–5; RT-24 identity reconciliation and decision matrix; PLAN §1.2 | Concept proposes Stable ID plus immutable Content Hash; RT-05 keeps stable IDs, scoped slots, and lineage as compatible alternatives. These can coexist as a value/managed-occurrence distinction, but the mapping, lifecycle, import, and hash envelope are not selected. | Unresolved design boundary; not a contradiction |
| Contract / operation / implementation identity | Draft Glossary; RT-20 Contract Identity and Compatibility §§2–7; RT-05 Typed SPG | The typed identities are intentionally distinct. RT-20's call-site required/provided Contract pair is not equivalent to CCHash membership. The explicit bridge from call-site refinement to operation conformance remains open. | Consistent separation; bridge unresolved |
| Dependency completeness and impact | Semantic Dependency Index; RT-05 §§3–4, 9; RT-06/RT-20; DEP-009–012 and DEP-052–054 | Exact references and binding-resolved selections can produce different invalidation behavior. SPG-03 is a concrete counterexample to caller-value-only execution reuse. Incomplete dependency evidence must block safe reuse or force conservative validation. | Strong scoped evidence; production closure unresolved |
| Cache and artifact identity | Semantic Compilation Cache §§2, 5–6; PLAN §§3.2–3.3; Package Identity prototype README; RT-05 SPG-03/07 | Semantic Hash, Action Key, and Artifact Hash are explicitly separated. LanguageVersion, component registry digest, and ToolchainIdentity are also distinct inputs. Full Action Key schema, closure, evidence freshness, cache trust, and compatibility remain open. | Consistent candidate model; implementation incomplete |
| Compiler and backend preservation | LLVM Backend Architecture §§1–9; RT-05 §4 and §8; Scenario 96/96A; PLAN Stage 6 | LLVM is explicitly a replaceable backend, not the canonical SPG or source of LLMLang semantics. RT-05 does not test compiler lowering. LLVM IR verification and code generation are not source-contract proof. | Consistent responsibility boundary; end-to-end preservation unvalidated |
| Package identity and trust | Package Identity prototype README; Semantic Compilation Cache §6; DEP-040–043; Draft Glossary | Content identity, package/root identity, archive/index identity, provenance, and publisher trust are separate. The prototype explicitly does not implement signatures, trust policy, full dependency closure, or production archive extraction. | Consistent separation; provider closure and trust integration unresolved |
| Runtime resources and resource accounting | RT-03/04 shared semantics; RT-05 §§3–4, 8; RT-26 §§2–11; PLAN Stages 5 and 7 | RT-05 includes resource ownership among graph concepts but explicitly excludes ownership and runtime validation. RT-26 separately requires task hierarchy, attribution uncertainty, limits, overshoot, handlers, and platform enforcement. No evidence currently closes that gap. | Not contradictory; major validation gap |
| Security, authority, and enforcement | RT-26 §5/§7/§9; RT-16 authorization research; DEP-030–032, DEP-043, DEP-048, DEP-057 | The documents consistently distinguish policy authority from runtime/OS hard boundaries and state that hashes alone do not establish trust. The exact composition of task budget delegation, agent/tool authorization, and resource-enforcement authority is not yet defined. | Open cross-aspect integration |

## 3. Findings

### B3-01 — Stable identity and content identity are not yet mapped to managed occurrence identity

**Evidence**
- research/LLMLang-CONCEPT.md §3.4 proposes a Stable ID for a logical entity and a Content Hash for an immutable state.
- research/RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md §§3–5 models immutable typed values separately from snapshot selections and scoped relations. It explicitly leaves stable entity IDs, scoped lifetime slots, and lineage as compatible candidate policies.
- RT-05 §7 reports fixture evidence that copied selections may share one value address, while a replacement with equal contents and a fresh selection is not treated as continuation without lineage.
- PLAN §1.2 leaves stable-ID lifecycle, canonical envelopes, and exact identity payloads undecided.

**Assessment**
These statements are compatible if the project distinguishes (a) immutable semantic value identity, (b) a managed occurrence/slot in a scope, and (c) continuity/lineage across revisions. The documents do not yet define one normative mapping among those three concepts. The Concept's two-ID formulation should not be interpreted as having already selected the occurrence/lineage model explored in RT-05.

**Required follow-up**
Define identity layers and mapping rules for creation, copy, move, delete/recreate, split/merge, import, and recursive groups. Keep all current policies as alternatives until a decision record selects one.

**Confidence:** high for the documented distinction; medium for the proposed reconciliation.

### B3-02 — Contract identity and implementation conformance are correctly separated, but the bridge is missing

**Evidence**
- draft/GLOSSARY.md defines generic ContractHash, OpHash, ImplHash, CCHash, optional CandidateSetHash, and claim-specific conformance evidence as different identities.
- research/RT-20-CONTRACT-IDENTITY-AND-COMPATIBILITY.md §§2–5 distinguishes exact Contract equality from behavioral refinement and distinguishes a call-site required/provided Contract pair from conformance-class membership.
- RT-20 §§6–8 states that current PROVEN fields are untrusted recorded inputs; the prototype does not prove refinement or implementation membership in a CCHash.

**Assessment**
No contradiction is present. A call-site refinement judgment and a global operation conformance-class judgment answer different questions. A future integration must state how an exact callee/implementation and its evidence map to the operation and constraints governing a dispatch call. Treating equality of Contract hashes as proof of implementation conformance would violate the reviewed documents' own boundaries.

**Required follow-up**
Specify a typed mapping among call-site required/provided Contracts, exact OpHash, applicable CCHash, exact ImplHash, and evidence records. Preserve UNKNOWN/unverified states and fail closed where compatibility is safety-critical.

**Confidence:** high.

### B3-03 — Execution-sensitive cache keys must include resolved bindings and the action's actual dependency closure

**Evidence**
- research/RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md §7 SPG-03: changing a binding changes execution behavior while the operation caller hash remains unchanged; the concrete pinned caller does not change in the same way.
- RT-05 §9 explicitly says execution-sensitive actions need relevant binding and selected implementation closure.
- research/SEMANTIC-COMPILATION-CACHE.md §§2, 5–6 separates Semantic Hash, Action Key, Artifact Hash and requires all result-determining inputs, tool identity, target, and relevant environment.
- PLAN §§3.2–3.3 still marks complete dependency closure and exact cache action binding as open.
- DEP-011, DEP-012, and DEP-052–054 connect dependency completeness, binding changes, and verified caller migration.

**Assessment**
The model is internally consistent, but a consumer must not infer that a stable caller semantic hash alone makes an execution or verification result reusable. The exact key depends on the action: a compile action at a stable external call boundary may not depend on the selected implementation, while link, execution, or behavior-verification actions may. Unknown closure must prevent a safe-reuse claim.

**Required follow-up**
Define per-action input schemas and dependency-closure evidence. Add tests for binding-only changes across compile, link, execute, test, and proof actions, including incomplete/unknown dependencies and stale evidence.

**Confidence:** high; the binding-only counterexample is directly documented, while general production closure remains unvalidated.

### B3-04 — LLVM backend boundary is aligned with SPG, but source-to-backend preservation remains a separate proof obligation

**Evidence**
- research/LLVM-BACKEND-ARCHITECTURE.md §§1–8 assigns source semantics, SPG, contracts, and semantic validation to LLMLang; LLVM IR is backend-facing and replaceable.
- The same document states that LLVM verification/optimization/compilation does not prove conformance to an LLMLang source contract and lists lowering, optimizer, target, runtime, and end-to-end obligations separately.
- RT-05 §8 explicitly excludes compiler lowering from the typed SPG experiment.
- PLAN Stage 6 requires at least two backends agreeing with reference semantics for the selected subset; this remains an exit gate.

**Assessment**
No semantic conflict is found between using LLVM and maintaining an independent semantic representation. However, the existence of an LLVM backend or passing LLVM verifier cannot be used as evidence that SPG semantics are preserved. The source-to-IR correspondence and target/runtime obligations remain distinct and unclosed.

**Required follow-up**
Maintain a source-semantics → LLMLang lowering → LLVM IR → target/runtime evidence chain, with exact versions/configuration and differential or formal checks. Do not promote backend success to source-level conformance.

**Confidence:** high.

### B3-05 — RT-05's resource-related graph vocabulary does not validate RT-26 semantics

**Evidence**
- RT-05 §3 says access, nominal types, capabilities, and runtime resource ownership enter typed semantics when they affect admission or observations.
- RT-05 §8 explicitly excludes resource ownership, mutable aliasing, concurrency, FFI, and compiler lowering from its experiment.
- research/RT-26-HIERARCHICAL-RESOURCE-ACCOUNTING-AND-ENFORCEMENT.md §§2–9 requires independent resource dimensions, task ancestry, delegation, attribution uncertainty, overshoot bounds, handlers, authorization, and platform enforcement. It remains Not started.
- PLAN places RT-26 within later runtime/scale research and does not record an accepted resource policy.

**Assessment**
This is a scope boundary, not a contradiction. A typed graph can represent resource-related nodes or relations without establishing that the runtime can attribute or enforce them. In particular, no per-coroutine exactness, hierarchical accounting, or portable hard-limit guarantee follows from the current SPG evidence.

**Required follow-up**
Treat RT-26 as an independent research gate. Cross-check its eventual task/resource model against RT-03 cancellation/cleanup, RT-04 ownership/capabilities, RT-16 authorization, RT-10 runtime, RT-13 target backends, and RT-25 allocator compatibility. Preserve UNKNOWN/approximate attribution and platform-specific enforcement classes.

**Confidence:** high.

### B3-06 — Package identity and supply-chain trust remain orthogonal

**Evidence**
- research/PROTOTYPES/PACKAGE-IDENTITY-01/README.md states that the prototype uses exploratory SHA-256 typed encoding, does not implement signatures/provenance verification, and does not yet establish provider-side transitive dependency closure.
- research/SEMANTIC-COMPILATION-CACHE.md separates semantic/action/artifact identities and requires relevant toolchain/environment inputs.
- DEP-040–043 distinguish stable package object identity, package/cache infrastructure, and trust/provenance constraints; DEP-043 explicitly says content hashes alone do not establish publisher trust.

**Assessment**
No contradiction is found. A matching digest can establish content identity under the chosen encoding; it does not establish publisher authority, provenance authenticity, or completeness of a package dependency closure. Cache reuse, package resolution, and trust decisions must therefore remain separate gates.

**Required follow-up**
Integrate package closure verification, provenance/signature policy, and cache admission as distinct checks. Do not use a content hash as a trust verdict.

**Confidence:** high.

### B3-07 — ImpHash / ImplHash remains an active unresolved naming discrepancy

**Evidence**
- PLAN §1.2 still uses ImpHash in identity tasks.
- The draft glossary and RT-20 use ImplHash.
- The 2026-11-20 cross-cutting alignment review explicitly records this mismatch as unresolved and intentionally does not normalize it.

**Assessment**
The discrepancy is known, not newly discovered, and no source in the reviewed baseline records a decision resolving it. It remains a terminology blocker for normative schemas and should be tracked as unresolved rather than silently rewritten in this audit.

**Required follow-up**
Reconcile the token in a dedicated terminology/identity decision after the identity model is selected; update dependent references atomically and preserve historical snapshots.

**Confidence:** high.

### B3-08 — RT-26's authority boundary needs an explicit composition with authorization and runtime isolation

**Evidence**
- RT-26 §5 says a handler cannot bypass a hard isolation boundary by returning a permissive action.
- RT-26 §§7 and 9 distinguish cooperative runtime checks from OS/container enforcement and require explicit behavior where attribution/control is unavailable.
- DEP-030–032, DEP-043, DEP-048, and DEP-057 record security constraints on runtime, packages, toolchain operations, and commit/push authority.

**Assessment**
The direction is consistent, but the documents do not yet specify how a resource-limit handler's authority composes with task capability grants, parent/supervisor budget delegation, and process/container policy. This is a real integration question; it is not evidence of a conflict among the current proposals.

**Required follow-up**
Model resource-budget delegation as a constrained authority relation. Separate (1) a task's requested budget, (2) parent/supervisor grant, (3) runtime-enforced ceiling, and (4) non-overridable OS/container boundary. Define denial, handler failure, cancellation, and cleanup behavior.

**Confidence:** medium-high.

## 4. Known unresolved items carried forward

| Item | Current status | B3 treatment |
|---|---|---|
| ImpHash vs ImplHash | Explicitly unresolved in prior alignment review and PLAN | Carried forward; no normalization |
| Canonical hash envelope, algorithm/domain separation, wire bytes | Decision pending | Not selected |
| Stable ID / slot / lineage policy | Multiple compatible candidates | Not selected |
| Contract refinement and conformance evidence | Research/prototype only | No unverified PROVEN accepted |
| Dependency closure and Action Key schema | Partially researched | Unknown closure blocks safe reuse |
| Package/provider closure and trust policy | Incomplete prototype boundary | Hash is not trust |
| LLVM lowering/source correspondence | Not established by current SPG experiment | Separate validation gate |
| RT-26 accounting/enforcement semantics | Not started | No portable exactness claim |
| Cross-layer authorization/resource budget model | Not specified | Unresolved |

## 5. What this audit does not establish

- It does not prove that all RT/DEP edges are technically correct.
- It does not validate every claim or test across all 487 inventory entries.
- It does not establish a canonical SPG schema, identity scheme, hash algorithm, semantic profile, or cache format.
- It does not establish full dependency closure, sound global impact analysis, or cache correctness in a production compiler.
- It does not establish source-to-LLVM preservation or multi-backend equivalence.
- It does not validate RT-26 resource attribution, throttling, enforcement, or handler behavior.
- It does not accept an architectural decision or promote research proposals into normative language rules.

## 6. Recommended next steps

1. B-04 — corpus-wide duplicate and supersession audit: use the refreshed 488-record inventory and distinguish exact duplicates, semantic overlap, section-level supersession, and historical evidence.
2. B-05 — complete traceability graph: reconcile artifact → claim → RT/DEP → scenario/prototype/test/evidence → plan stage links, preserving unresolved edges.
3. B-06 — contradictions and unresolved register: consolidate B3 and prior known issues with exact scope, evidence, confidence, and owner/decision boundary.
4. Later targeted research should close the B3 gaps in dependency closure/action identity, contract conformance mapping, and RT-26 authority/resource semantics; this audit does not prescribe their architectural outcome.

## 7. Reproduction and review method

This is a source-document consistency review. It is reproducible by reading the pinned baseline files and checking the cited sections. No prototype execution or benchmark was performed as part of B3. Existing experiment outcomes are quoted only within their recorded scopes; they were not rerun here.

Primary baseline files:
- PLAN.md
- research/RESEARCH-TAXONOMY.md
- research/RESEARCH-DEPENDENCY-MAP.md
- research/LLMLang-CONCEPT.md
- research/RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md
- research/RT-20-CONTRACT-IDENTITY-AND-COMPATIBILITY.md
- research/RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md
- research/RT-24-IDENTITY-AND-SPG-RECONCILIATION.md
- research/SEMANTIC-DEPENDENCY-INDEX.md
- research/SEMANTIC-COMPILATION-CACHE.md
- research/LLVM-BACKEND-ARCHITECTURE.md
- research/RT-26-HIERARCHICAL-RESOURCE-ACCOUNTING-AND-ENFORCEMENT.md
- research/PROTOTYPES/PACKAGE-IDENTITY-01/README.md
- draft/GLOSSARY.md
- research/RESEARCH-CORPUS-CROSS-CUTTING-ALIGNMENT-REVIEW-2026-11-20.md

**Conclusion:** the reviewed documents are more consistent in their separation of concerns than a superficial terminology scan might suggest. The remaining work is chiefly to define the interfaces between those concerns and to validate them with source-derived, reproducible evidence. B3 does not close RT-00; B-04 through B-06 and the remaining reproducibility/provenance/link checks are still required.
