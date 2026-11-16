# Research Scenario 20 — Dependency Discovery and Semantic Classification

**Status:** Research result and prototype proposal; not a normative LLMLang decision  
**Date:** 2026-11-16  
**Depends on:** Scenarios 18–19 and Dependency Graph Prototype 01

## 1. Research question

Scenario 19 established that safe incremental planning needs evidence about dependency completeness. It did not define how LLMLang discovers dependency candidates or decides which observations belong in the semantic dependency graph.

This scenario investigates how to combine static analysis, dynamic observations, sandbox traces, explicit declarations, and proof-dependency information without confusing a possible dependency with a confirmed semantic input, an observed access with a behaviorally relevant input, a provenance link with a dependency, or absence of an observed edge with proof that no edge exists.

## 2. Executive conclusion

Use a two-stage process:

1. **Discovery:** collect typed dependency candidates from multiple independent methods, preserving source, scope, tool identity, and exact evidence.
2. **Classification:** decide whether each candidate is a semantic input, control input, configuration/toolchain/environment input, an external-effect dependency, provenance-only, incidental access, or unresolved.

Only reviewed hash-relevant classes enter the semantic dependency closure. Provenance-only and incidental-access facts remain available for audit but do not automatically invalidate semantic values. Unresolved candidates block a claim of dependency completeness.

The union of static and dynamic findings is a candidate inventory, not a proof of completeness. Static analysis can over-approximate; dynamic traces can under-approximate. Combining them improves coverage but does not remove either limitation.

## 3. Research findings

### 3.1 Static and dynamic analysis have complementary failure modes

Static analysis can identify potential dependencies without executing a path, but conservative approximations may include dependencies that do not affect a particular execution or output. Dynamic analysis identifies dependencies that occurred in observed executions, but cannot establish that unobserved paths have no additional dependencies.

Therefore:
- static-only candidates should not automatically be treated as proven semantic dependencies;
- dynamic-only candidates should not automatically be treated as semantically relevant;
- an observed dependency absent from declarations is a discrepancy requiring classification;
- no observation is not evidence of non-dependence.

### 3.2 Build systems demonstrate the value of runtime dependency capture

Pluto records dynamic reads and builder relationships and enforces graph invariants to support sound incremental rebuilding. Build fuzzing detects missing build dependencies by perturbing inputs and comparing incremental behavior with a clean-build reference. Recent work on mkcheck2 uses eBPF tracing and incremental analysis to reduce the cost of checking build dependencies.

These methods are useful for build and execution dependencies. They do not by themselves decide whether a filesystem or process access is part of program business semantics.

### 3.3 Hermeticity reduces the discovery problem

A sandbox that exposes only declared inputs can turn undeclared access into a detectable failure. This is stronger than merely observing a successful execution on a developer machine. However, a filesystem sandbox alone does not necessarily isolate host environment, network, clock, kernel, or all ambient state.

A hermetic execution boundary should make available inputs explicit and deny or virtualize ambient inputs wherever practical. Any permitted external input must be represented by a pinned identity, protected version reference, or explicit nondeterministic input record.

### 3.4 Proof dependencies reveal logical assumptions

A proof result depends on premises, specifications, statements, and assumptions. Extracting these dependencies supports audits of what a proof actually establishes and which assumptions remain unverified. A successful verifier exit code is not enough to describe the proof's dependency boundary.

LLMLang should treat proof assumptions as first-class dependency candidates, with exact identities and status. An unverified assumption is not silently promoted to a verified fact.

## 4. Dependency candidate taxonomy

| Classification | Hash-relevant by default? | Meaning |
|---|---:|---|
| SEMANTIC_INPUT | Yes | Value contributes to defined behavior or content |
| CONTROL_INPUT | Yes | Input controls which semantic path or result is selected |
| CONFIGURATION | Usually yes | Configuration changes behavior or generated result |
| TOOLCHAIN | Yes for build artifacts | Compiler, generator, verifier, or tool identity affects output/evidence |
| ENVIRONMENT | Depends on boundary; default yes when observable | Locale, clock, environment variables, OS/runtime behavior |
| EXTERNAL_EFFECT | Yes for execution snapshots | Network/service/database or other external state/effects |
| PROVENANCE_ONLY | No | Origin, authorship, derivation, or rationale without semantic change |
| INCIDENTAL_ACCESS | No | Access established not to affect defined behavior |
| UNKNOWN | Not safe to exclude | Relevance has not been established |

The classification is boundary-specific. A compiler version is a build dependency, but may not be a semantic input to a source-level requirement value.

## 5. Discovery sources and guarantees

| Source | Strong evidence for | Main limitation |
|---|---|---|
| Explicit typed declaration | Intended semantic and policy inputs | Can omit a dependency |
| Static data/control-flow analysis | Potential source dependencies and unexecuted paths | May over-approximate; reflection and external state complicate analysis |
| Dynamic instrumentation | Actual calls, reads, writes, and effects on observed paths | Unexecuted paths are absent |
| OS/eBPF/system-call tracing | Actual filesystem/process/network interactions within tracing scope | Access does not establish semantic relevance |
| Hermetic sandbox | Undeclared access can be denied or exposed | Only as complete as the sandbox boundary |
| Mutation/build fuzzing | Missing dependencies that cause incremental/clean-result divergence | Coverage depends on mutations and scenarios |
| Proof dependency extraction | Premises and assumptions used by proof obligations | Depends on verifier model and sound extraction |
| Human business review | Meaning, policy ownership, intended scope | Does not mechanically establish source/runtime dependency completeness |

A robust implementation layers these sources and records their limitations. No single source should be described as globally complete without a soundness argument for its scope.

## 6. Discovery and classification pipeline

1. Pin exact artifact, source snapshot, build/runtime/proof context, and analysis policy.
2. Collect dependency candidates from configured discovery sources.
3. Normalize candidates to exact input identities and typed relation proposals.
4. Preserve each source observation; do not collapse evidence into a bare boolean.
5. Compare candidates with declared dependencies.
6. Classify each candidate as semantic, control, configuration, toolchain, environment, external effect, provenance-only, incidental, or unknown.
7. Add only accepted hash-relevant classes to the candidate semantic dependency set.
8. Keep provenance/incidental observations in an audit relation store.
9. Treat unknown candidates and unclassified discrepancies as unresolved completeness gaps.
10. Recompute dependency closure and Scenario 19 impact plan against the new candidate graph.
11. Pin discovery evidence and classification decisions to the candidate snapshot.
12. Re-run audit whenever artifact, dependency set, tool identity, scope, or relevant environment changes.

A classification decision is itself evidence. Promoting an incidental access to a semantic input must create a new candidate graph/snapshot and trigger impact analysis.

## 7. Rules for combining evidence

- **Preserve source provenance.** If static analysis and dynamic tracing identify the same input, retain both evidence references.
- **Do not infer semantic relevance from access alone.** A file may be read for logging; a configuration may affect behavior through dynamic loading.
- **Do not infer non-dependence from non-observation.** A trace only describes its execution scope.
- **Unresolved means fail closed.** If a candidate may affect behavior and relevance is unresolved, do not exclude it and claim completeness.
- **Separate semantic graph from audit graph.** Semantic graph contains accepted hash-relevant dependencies. Audit graph retains observations, candidate edges, evidence, and review decisions.

## 8. Prototype 20

Files:
- `PROTOTYPES/DEPENDENCY-GRAPH-01/src/dependency_discovery.py`
- `PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_dependency_discovery.py`
- `PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-20-RESULTS.md`

The prototype models normalized observations and explicit classification decisions. It merges evidence from multiple sources, requires classification before a candidate enters the semantic dependency set, identifies classified missing dependencies, keeps provenance/incidental observations out of semantic closure, blocks completeness claims for unknown candidates, and computes a deterministic evidence digest.

## 9. Prototype statuses

- **GAP_FOUND:** a classified hash-relevant candidate is absent from declared dependencies.
- **REVIEW_REQUIRED:** one or more candidates have unknown classification.
- **SUPPORTED_WITHIN_SCOPE:** no classified missing dependency or unresolved candidate was found in supplied evidence.
- **NOT_CHECKED:** no discovery evidence was supplied.

SUPPORTED_WITHIN_SCOPE is not a universal completeness theorem. It is conditional on the supplied scope and evidence.

## 10. Limitations

- No source parser, compiler IR, static analyzer, dynamic instrumentation, eBPF collector, or sandbox is implemented.
- The prototype trusts normalized observations supplied by its caller.
- Semantic classification is explicit input, not inferred from code.
- It does not prove discovery tools sound or complete.
- It does not prove that an incidental access is behaviorally irrelevant.
- It does not yet integrate its evidence digest into Scenario 19's planner identity.
- It does not execute actions, persist evidence, or implement distributed review/approval.
- It does not solve dynamic dispatch, reflection, concurrency, nondeterminism, or external-service replay.

## 11. Acceptance criteria

- Multiple sources for one input are preserved in one candidate record.
- Static or dynamic observation alone does not automatically create a semantic edge.
- A reviewed hash-relevant candidate missing from declarations yields GAP_FOUND.
- Provenance-only and incidental observations do not enter semantic dependencies.
- Unknown classification yields REVIEW_REQUIRED.
- Empty evidence yields NOT_CHECKED, not SUPPORTED_WITHIN_SCOPE.
- Evidence digest changes when source, tool, scope, input, or classification changes.
- Every audit result is tied to an exact artifact and scope.

## 12. Preliminary recommendation

Use **multi-source dependency discovery with explicit semantic classification**. Discovery tools produce evidence-bearing candidates, not authoritative semantic edges. Typed classification determines hash relevance. Unresolved candidates block completeness claims. Semantic and audit graphs remain separate. Scenario 19 planning consumes scoped completeness evidence. No observation-based method may claim universal completeness outside its proven scope.

This is a research conclusion, not a normative LLMLang language rule.

## 13. References

- Erdweg, Lichter, Weiel, *A Sound and Optimal Incremental Build System with Dynamic Dependencies* (OOPSLA 2015). https://www.mathematik.uni-marburg.de/~seba/publications/pluto-incremental-build.pdf
- Licker and Rice, *Detecting Incorrect Build Rules*. https://www.cl.cam.ac.uk/~acr31/pubs/licker-buildrules.pdf
- Saito, Sakamoto, Washizaki, *Efficient Build Dependency Verification Using eBPF and Incremental Analysis* (ICSE 2026). https://conf.researchr.org/details/icse-2026/icse-2026-research-track/162/Efficient-Build-Dependency-Verification-Using-eBPF-and-Incremental-Analysis
- Brugger, Keusch, Pereira, Müller, *Using Proof Dependencies to Manage Verification Projects* (2026). https://arxiv.org/abs/2611.13250
- *A Practice-Driven Systematic Review of Dependency Analysis Solutions*. https://link.springer.com/article/10.1007/s10664-011-9158-8
- Bazel, *Sandboxing*. https://github.com/bazelbuild/bazel/blob/master/docs/docs/sandboxing.mdx
