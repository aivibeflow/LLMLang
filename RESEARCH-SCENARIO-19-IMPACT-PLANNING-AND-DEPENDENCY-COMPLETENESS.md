# Research Scenario 19 — Semantic Impact Planning and Dependency Completeness

**Status:** Research result and prototype proposal; not a normative LLMLang decision  
**Date:** 2026-11-16  
**Depends on:** Scenarios 17–18 and Dependency Graph Prototype 01

## 1. Research question

Scenario 18 showed that immutable content-addressed values and explicit hash-relevant dependency edges can propagate a requirement change through a selected semantic graph. That result is conditional: graph traversal finds only dependencies represented in the graph.

Scenario 19 asks two connected questions:

1. How should LLMLang decide what work a change requires for each impacted artifact?
2. What evidence supports the claim that the dependency graph contains all dependencies relevant to that decision?

The second question is logically prior to safe incremental planning. A perfect traversal over an incomplete graph can silently omit necessary work.

## 2. Executive conclusion

The recommended design separates four concerns:

1. **Dependency declaration:** the semantic artifact records exact inputs that affect its meaning or validity.
2. **Dependency completeness assessment:** independent evidence audits whether the declared inputs cover the relevant dependency scope.
3. **Impact closure:** graph traversal computes the candidate affected artifacts from a pinned snapshot.
4. **Action planning:** typed artifact policies translate impact into re-derivation, test generation, test execution, proof re-execution, human review, or conservative full validation.

Do not collapse these into a single boolean such as `impact_analysis_passed`.

A graph can be internally consistent and still omit an edge. Observed dependency agreement is evidence only for the executions and environments observed; it is not a universal proof of completeness. A no-action decision requires stronger, artifact-specific evidence of non-interference, not merely absence of a graph path.

## 3. Findings from related work

### 3.1 Requirements traceability is a correctness concern

NASA guidance calls for bidirectional traceability and independent evaluation of whether a trace is correct and fully addresses its parent requirement. It also asks whether all higher-level requirements have been allocated to lower-level requirements. This is stronger than checking that every existing edge points to a valid node: it audits missing relationships and coverage in both directions. See [NASA Requirements Management](https://www.nasa.gov/reference/6-2-requirements-management/) and [NASA SWE-051](https://swehb.nasa.gov/pages/viewpage.action?pageId=112656703).

Implication for LLMLang: traceability completeness needs explicit coverage obligations. A valid graph schema and zero dangling references do not establish completeness.

### 3.2 Incremental build soundness depends on dependency capture

Pluto models dynamic dependencies and interleaves dependency discovery with builder execution. Its soundness argument depends on enforcing invariants over the dependency graph, not merely traversing a graph supplied without validation. [Erdweg, Lichter, Weiel, “A Sound and Optimal Incremental Build System with Dynamic Dependencies”](https://www.mathematik.uni-marburg.de/~seba/publications/pluto-incremental-build.pdf).

Research on build-rule fuzzing found missing dependencies by comparing dependency information inferred from clean-build system-call traces with declared build rules; it reported real faulty build rules in open-source projects. This is a useful audit technique, but trace-based observations are bounded by exercised executions. [Licker and Rice, “Detecting Incorrect Build Rules”](https://www.repository.cam.ac.uk/items/42efcbfa-a3c6-4bb4-bc98-6d46ddc222c7).

Implication: LLMLang should combine static dependency extraction, dynamic observations, mutation/fuzz testing, and explicit input declarations. No single technique should be presented as universally complete.

### 3.3 Regression-test selection exposes a safety/precision trade-off

An empirical comparison of Java regression-test-selection techniques measured both safety (missing tests that should run) and precision (unnecessary tests selected). It found meaningful differences between techniques; one selected-test strategy showed lower fault-detection ability than the full suite in the reported comparison. [Journal of Systems and Software, 2022](https://www.sciencedirect.com/science/article/pii/S0164121221002582).

Implication: minimizing work is not the only objective. LLMLang should make missed-impact risk visible and provide a conservative full-validation fallback. A smaller plan is not automatically a better plan.

### 3.4 Proof dependencies can support audits, not just invalidation

Recent work on proof-dependency analysis uses dependencies of proof obligations on specifications, statements, and assumptions to audit what has actually been established and what remains unconstrained. [Brugger et al., “Using Proof Dependencies to Manage Verification Projects” (2026)](https://arxiv.org/abs/2611.13250).

Implication: proof records should expose their exact assumptions and dependency closure. A proof result is meaningful only relative to those exact inputs; hidden assumptions are themselves dependency-completeness risks.

## 4. Dependency completeness: what can and cannot be claimed

### 4.1 Four distinct states

For an artifact and a declared scope, distinguish:

- **GAP_FOUND:** an independent observation or analysis found a relevant input not represented in the declared dependency set.
- **SUPPORTED_WITHIN_SCOPE:** available evidence found no gap within its explicitly stated scope, tool identity, assumptions, and environment.
- **UNKNOWN:** evidence is absent, stale, out of scope, or too weak to support a conclusion.
- **NOT_CHECKED:** the completeness audit has not been run.

Do not call SUPPORTED_WITHIN_SCOPE “globally complete”. It is a bounded assurance statement.

### 4.2 Dependency sources

Candidate dependency sources include:

- explicit semantic inputs and typed references;
- interface and contract constraints;
- transitive dependencies of called components;
- configuration, feature flags, policy and binding snapshots;
- compiler, verifier, generator, toolchain and plugin identities;
- schema, protocol, ABI and externally observable interface versions;
- environment variables, locale, time zone, clock, filesystem, network and process state;
- secrets represented by protected version references, never plaintext;
- runtime data and external effects, where the artifact's semantics depend on them;
- assumptions and axioms used by proofs;
- generated inputs and dynamic dispatch/binding decisions.

A dependency inventory must state which classes are in scope. “No dependencies found” is not meaningful if the audit did not inspect configuration, environment, dynamic calls, or external effects.

### 4.3 Completeness evidence record

A completeness evidence record should be pinned to:

- exact artifact hash and exact declared dependency-set digest;
- scope identifier and dependency classes covered;
- analysis method and tool/version identity;
- exact source/build/runtime environment where relevant;
- observed dependencies or extracted dependency facts;
- assumptions, exclusions, bounds, and known blind spots;
- audit timestamp/epoch and evidence artifact digest;
- result status and reviewer/authority where required.

Changing the artifact, declared edges, tool version, scope, or relevant environment invalidates reuse unless an explicit compatibility rule justifies it.

### 4.4 Evidence methods and limits

| Method | Useful for | Does not establish by itself |
|---|---|---|
| Static extraction | Explicit references, imports, calls, type-level dependencies | All dynamic behavior, reflection, external state |
| Dynamic tracing | Actual reads/calls/effects on exercised paths | Unexecuted paths and unobserved environments |
| Build/runtime sandboxing | Capturing filesystem, process, network and environment access | Semantic relevance of every observed access |
| Mutation/fuzz audit | Detecting omitted dependencies by perturbing inputs | Exhaustive coverage unless the state space is finite and fully explored |
| Human declaration/review | Business meaning, external assumptions, policy ownership | Mechanical completeness of implementation dependencies |
| Formal proof/dependency analysis | Exact assumptions and proof-obligation dependencies within a formal model | Correctness of the model-to-source extraction unless separately established |

The strongest practical approach is layered evidence. Dynamic observations should be treated as candidate missing dependencies; static and semantic analysis classify them. An unexplained observation is a gap to resolve, not an edge to silently ignore.

## 5. Impact planning

### 5.1 Separate action classes

A single generic “rebuild” action loses important distinctions. Use explicit actions:

- **RE_DERIVE:** regenerate a derived semantic artifact, such as a formal clause or caller contract.
- **REGENERATE_TESTS:** regenerate test specifications/cases because their source contract changed.
- **RUN_TESTS:** execute the selected tests against the exact candidate implementation/build.
- **REBUILD:** regenerate compiled/generated artifacts when their build inputs changed.
- **REPROVE:** rerun or reconstruct proof obligations against exact changed inputs.
- **HUMAN_REVIEW:** request a decision for business meaning, ambiguity, policy, assumptions, or unresolved dependency evidence.
- **FULL_REVALIDATION:** conservative fallback when dependency completeness is unknown or a gap remains unresolved.

Actions should carry exact subject hashes, reason codes, prerequisite actions, and evidence references. A plan is itself immutable and pinned to the baseline, candidate snapshot, dependency-audit roots, policy version, and planner version.

### 5.2 Example policy mapping

| Impacted artifact | Default action |
|---|---|
| Requirement / business rule | HUMAN_REVIEW when intent, applicability, authority, or ambiguity is affected; then RE_DERIVE downstream artifacts |
| Formal clause | RE_DERIVE |
| Caller contract | RE_DERIVE |
| Generated test suite | REGENERATE_TESTS, then RUN_TESTS |
| Implementation/build output | REBUILD as applicable, then RUN_TESTS |
| Proof/verification record | REPROVE |
| Unknown artifact kind | HUMAN_REVIEW + FULL_REVALIDATION |

This mapping is a starting policy, not a universal law. A project may refine it only through explicit, versioned policy. A test suite can be regenerated without proving it is adequate; test execution is not a substitute for proof. Likewise, a proof should not be silently reused for a changed artifact.

### 5.3 Action dependencies

Actions form their own DAG. For example:

`Requirement change → Re-derive clause → Re-derive contract → Regenerate tests → Run tests`

and independently:

`Contract/implementation change → Re-prove obligations`

A plan must respect prerequisites and exact input hashes. If a prerequisite action produces a new artifact hash, downstream actions must bind to that new hash rather than the stale pre-plan hash.

### 5.4 When is NO_ACTION allowed?

Absence of a dependency path is not evidence of non-impact if graph completeness is UNKNOWN.

A no-action decision is allowed only when a trusted, independently checked non-interference certificate is bound to:

- the exact changed input hash;
- the exact artifact hash;
- the observable boundary and property being preserved;
- the exact analysis/checker identity and assumptions;
- the exact candidate snapshot.

The certificate must establish that the changed input cannot affect the artifact's declared observable behavior within the stated model. A human's assertion, an empty graph query, or a test that happened not to fail is insufficient.

If such a certificate is unavailable, the planner must not emit NO_ACTION for an otherwise plausible dependency. It should schedule validation or escalate to review.

## 6. Proposed completeness audit pipeline

1. Pin baseline and candidate snapshots.
2. Compute declared dependency closure for each impacted artifact.
3. Collect independent dependency facts from static analysis, dynamic traces, build/runtime sandboxing, proof assumptions, and human declarations.
4. Normalize facts to typed dependency candidates and exact input identities.
5. Compare observed/extracted candidates with declared edges.
6. Classify each discrepancy: semantic dependency, incidental access, unsupported dynamic dependency, stale declaration, or unresolved.
7. If a relevant dependency is missing, create a proposal to add the edge and rederive the affected artifact; do not mutate accepted state automatically.
8. Re-run impact closure and planning against the revised candidate.
9. Produce an immutable plan with evidence and conservative fallback where completeness remains unknown.
10. Execute actions in dependency order; record outputs and evidence against exact action inputs.

## 7. Prototype scope

The Scenario 19 prototype should remain deliberately small:

- represent declared and independently observed dependency identities;
- audit exact artifact/scope/dependency-set evidence;
- distinguish GAP_FOUND, SUPPORTED_WITHIN_SCOPE, UNKNOWN, and NOT_CHECKED;
- produce typed actions for common artifact kinds;
- refuse to optimize away work when completeness is unknown or a gap is unresolved;
- allow NO_ACTION only with a matching PROVEN non-interference certificate record;
- bind plans to immutable snapshot and policy identifiers.

The prototype does not implement static analysis, tracing, sandboxing, proof checking, distributed execution, or a trusted certificate verifier. It validates planning policy and evidence binding only.

## 8. Prototype design

### 8.1 Completeness audit

Let (D(a)) be the declared dependency identities for artifact (a), and (O(a,s)) be dependency identities observed by an independent method within scope (s).

A basic discrepancy set is:

`Missing(a,s) = O(a,s) - D(a)`

If Missing is non-empty, report GAP_FOUND. If it is empty, the result is at most SUPPORTED_WITHIN_SCOPE, and only if the evidence is current and matches the exact artifact, dependency digest, and scope. Without matching evidence, report UNKNOWN or NOT_CHECKED.

This check is intentionally asymmetric: an unused declared dependency may be conservative over-approximation, while an observed relevant input absent from declarations may make incremental reuse unsound. Whether an observation is semantically relevant must be classified, not guessed by the prototype.

### 8.2 Planner safety rule

If any impacted artifact has GAP_FOUND, UNKNOWN, or NOT_CHECKED completeness, the plan must include HUMAN_REVIEW and FULL_REVALIDATION. It may still list targeted actions as useful work, but they do not replace the fallback.

If all relevant artifacts are SUPPORTED_WITHIN_SCOPE, the planner emits targeted artifact-policy actions. This remains a scoped claim, not a proof of global completeness.

### 8.3 Non-interference gate

The prototype accepts a non-interference certificate only when its subject artifact hash, changed input hash, boundary, checker identity, and status match the requested skip. This is a record-integrity gate; it does not validate the proof artifact itself. Production LLMLang needs a trusted checker/verifier pipeline.

## 9. Acceptance criteria for this research prototype

- A missing observed dependency is reported as GAP_FOUND.
- A matching bounded audit with no observed gaps is SUPPORTED_WITHIN_SCOPE, not globally complete.
- Stale or mismatched evidence yields UNKNOWN.
- No evidence yields NOT_CHECKED.
- Unknown/gap/not-checked completeness forces HUMAN_REVIEW and FULL_REVALIDATION.
- Formal clauses and contracts produce RE_DERIVE actions.
- Test suites produce REGENERATE_TESTS and RUN_TESTS.
- Verification records produce REPROVE.
- Unknown artifact kinds force conservative fallback.
- NO_ACTION is rejected without a matching PROVEN non-interference certificate.
- A certificate for a different artifact, changed input, boundary, or checker is rejected.
- Plan identity changes when baseline/candidate/policy/action inputs change.

## 10. Open questions

1. Which dependency classes belong in the mandatory semantic core versus pluggable analyzers?
2. How should LLMLang distinguish semantic reads from incidental filesystem/network accesses?
3. How are dynamic dispatch and runtime binding observations represented without making every execution context a semantic dependency?
4. What proof format and trust model should certify non-interference?
5. Can dependency extraction itself be expressed as a verified compiler obligation?
6. How should completeness evidence expire when toolchains, environments, or external services change?
7. What is the acceptable policy when external dependencies cannot be pinned or replayed?
8. How should probabilistic, nondeterministic, and concurrent behavior affect dependency closure?
9. Should a project choose a risk profile that permits scoped incremental validation, or require full validation for particular artifact classes?
10. How can we measure false negatives in impact planning, not merely planner speed or number of skipped actions?

## 11. Preliminary recommendation

Adopt a **fail-closed incremental planning model** as the research direction:

- explicit typed dependencies are necessary but not sufficient;
- completeness evidence is separate, scoped, and independently produced;
- observed missing dependencies block optimized plans until resolved;
- action planning is typed and policy-versioned;
- NO_ACTION requires positive non-interference evidence;
- UNKNOWN and NOT_CHECKED never mean “unaffected”;
- full validation remains the safe fallback.

This recommendation is a research conclusion, not yet a normative LLMLang language rule.
