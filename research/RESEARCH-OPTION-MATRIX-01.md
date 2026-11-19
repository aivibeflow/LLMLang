# Research Option Matrix 01 — Language and Execution Foundations

**Status:** Initial evidence-linked comparison; no vector selected
**Updated:** 2026-11-19
**Scope:** First synthesis slice across core semantics, type/effect/resource model, semantic representation, verification, runtime, backends, and security. This matrix does not choose a language architecture or replace the source studies.

## 1. Purpose

The research corpus contains multiple candidate profiles, prototypes, and recommendations, but the alternatives are not yet normalized into a single comparison that shows which combinations are coherent and what evidence supports them. This document records a first set of integrated vectors, compatibility conditions, evidence strength, and the experiments that would distinguish them. It feeds the whole-specification synthesis in `PLAN.md`.

The vectors are candidate bundles, not claims that all combinations within a column have already been implemented or proved. A missing incompatibility is not evidence of compatibility. Recommendations in source documents remain recommendations until an explicit decision is accepted.

## 2. Evidence and confidence scale

Evidence levels used here:

- **Implemented:** executable prototype or production behavior exists and is linked.
- **Mechanically checked:** a test suite or kernel-checked theorem passed for a named bounded scope.
- **Analytical:** comparative reasoning or a written architecture proposal exists without validating experiment.
- **Assumed:** required to make the vector coherent but not established by current evidence.

Confidence describes how strongly the current evidence supports the stated comparison, not how attractive the vector is.

## 3. Normalized decisions

| Decision | Candidate vectors | Current evidence and scope | Open discriminator |
|---|---|---|---|
| Source execution semantics | **S-A Pure strict core** with immutable values and explicit error data. **S-B Imperative state core** with ordered commands and explicit store. **S-C Isolated concurrent processes** with local state and message traces. **S-D Effectful functional core** with explicit effect operations and handlers. | [COR-09–11](RT-03-04-SHARED-SEMANTICS-CORPUS.md) compare all four on one bounded scalar workload and record counterexamples for mutation order, handler behavior, and actor delivery. Lean proves preservation for a narrow Int/Bool expression subset. | Compare a typed resource and message protocol that can block, fail, or transfer a reference. Determine where divergence, cleanup, and scheduling affect observations. |
| Recursion, termination, and execution budgets | **T Total-by-default** with structural/well-founded recursion; **P general recursion** with divergence; **D typed divergence effect**; **F source-semantic fuel**; **M VM operator gas**; **E external runtime limits**; combinations remain possible. | [Scenario 36](RESEARCH-SCENARIO-36-RECURSION-TERMINATION-AND-FUEL.md) compares Lean, Koka/F*, Rust, WebAssembly, and Wasmtime. The abstract source-cost model derives `4*n+2` for one countdown and shows finite fuel cannot identify divergence alone. Bounded effect/scope and fuel/owned-return probes distinguish cleanup allowance, abortive trap, pending-return disposal, and caller-owned value across fuel exhaustion. | Check divergence-effect propagation; add recursive source programs and a common outcome model; compare source-fuel and VM-gas layers. Cross-check primary exhaustion, cleanup failure, pending values, and owner debts against an independent obligation projection. Bind runtime engine/version, operator-cost schedule, imports, and interruption policy to evidence inputs. |
| Type/effect/resource model | **T-A Explicit effects and capabilities over pure core;** **T-B Ownership/borrowing with imperative state;** **T-C Message/protocol types with isolated processes** | The RT-04 study compares profiles and a limited declaration-level checker covers selected effect bounds, call-site checks, and scoped capabilities. The cross-profile fixture exposed that effect summaries omit ordering/payload and an open-row marker does not implement row unification or handler coverage. COR-13 shows that transfer-first cleanup failure needs an error-with-value result that current typed calls cannot represent; RT-04's checker accepts primitive `Result` but rejects nested `Owned` and `ErrorWithValue` descriptors as unknown. Only shared cleanup traces are cross-checked against RT-03. No profile is validated as a complete type system. | Preserve ordered effect traces and payloads in summaries; test handler coverage, aliasing/borrowing, resource transfer, cancellation, and inter-process protocols against the same RT-03 observations. Extend COR-13 through a typed owned-value call boundary and source correspondence. |
| Program representation and identity | **R-A Stable entity IDs with immutable values.** **R-B Content addresses with explicit lineage.** **R-C Optional occurrence and scoped slot identity.** | The [lifecycle experiment](RT-05-IDENTITY-LIFECYCLE-EXPERIMENT.md) compares continuity across moves. The [inline counterexample](RT-05-RT-20-CALL-SITE-REFACTOR-EXPERIMENT.md) separates Contract conformance from equivalent behavior. The [recursive identity experiment](RT-05-RECURSIVE-IDENTITY-EXPERIMENT.md) measures when explicit keys keep symmetric members distinct and when an SCC change propagates to callers. | Check authenticated lineage, real import, and scalable canonical labeling. Compare exact implementation dependencies with calls through typed `OpHash` and `ImplHash` envelopes. |
| Verification and evidence | **V-A One executable reference semantics with verified projections;** **V-B Formal semantics plus untrusted executable checker;** **V-C Test/model-checking evidence with conservative unknowns** | Scenarios 25–34 and pinned Lean/Logos experiments establish a narrow CPC parser binding and expression/query correspondence scope. RT-20/CIP adds plan and obligation structure, not execution evidence or behavioral correctness. No complete source-program proof architecture exists. | Specify proposition, input manifest, assumptions, tool/environment identity, soundness claim, and trusted computing base for each evidence class. Test stale evidence and unknown dependency cases. |
| Runtime and backend | **B-A Interpreter/reference runtime first, with later native lowering;** **B-B Bytecode VM as primary execution contract;** **B-C Direct native/LLVM lowering with runtime services** | Backend and POSIX architecture studies are analytical. No target profile or backend is selected. Lean and Logos are currently used for a proof/checking toolchain, not a LLMLang execution backend. | Run the same vertical slice through two independently implemented backends against the reference semantics; compare behavior, diagnostics, performance, ABI/runtime boundary, and unsupported cases. |
| Compilation and binding | **Exact implementation linkage.** **Separately linked stable ABI with pinned implementation selection.** | In the [RT-11 C benchmark](RT-11-BINDING-INVALIDATION-BENCHMARK.md), changing one implementation reduces caller recompilations from 12 to 4 under separate linkage. Both strategies still link and verify twelve changed executables. Body-visible consumers recompile in both. | Evaluate actual LLMLang code generation and prove which conditions and bindings affect each action before relying on projected keys. Measure runtime, artifact size, and link cost. |
| Security and authority | **Q-A Small trusted core with capability-mediated effects and untrusted LLM proposals;** **Q-B Sandboxed toolchain/runtime with signed evidence and explicit human authorization;** **Q-C Process isolation and declarative policy around execution** | The concept excludes LLM output from the trusted execution chain. [RT-16 Threat Model 01](RT-16-THREAT-MODEL-01.md) now identifies lifecycle boundaries and tests 24 authorization/evidence decisions for principal, repository, action, base, target, expiry, verifier identity, result, and replay. The evidence digest is unkeyed, so it does not authenticate a producer. Issuer, revocation, artifact trust, sandbox boundaries, and signed evidence remain unresolved. | Test the authorization rules in a persistent concurrent service, then validate authenticated evidence, package provenance, sandbox boundaries, and recovery. |

## 4. Integrated candidate vectors

These bundles show plausible cross-area combinations for later whole-specification comparison. They are not selections or rankings.

| Candidate | Core bundle | Main benefit to evaluate | Main cost or failure mode | Compatibility conditions | Evidence maturity |
|---|---|---|---|---|---|
| **C1 — Verifiable pure-first language** | S-A + T-A + R-A or R-C + V-A + B-A then B-C + Q-A | Small semantic core, compositional reasoning, explicit environmental effects, potential for strong incremental reuse | Pure-first style may complicate conventional resource-heavy code; moving from interpreter to native lowering raises proof obligations; identity model remains unsettled | Effect/capability semantics must define observations and hash boundaries; runtime effects need explicit handlers; entity identity choice must preserve change and reuse requirements | Analytical architecture; bounded A/D expression, effect, Result, cancellation, branch, and resource prototypes exist, but no integrated vertical slice |
| **C2 — Systems language with explicit ownership** | S-B + T-B + R-A + V-A/V-C + B-A or B-B then native + Q-A/Q-B | Direct control over memory/resources and conventional systems APIs | Alias/state semantics enlarge proof, impact-analysis, cache, and merge surfaces; unsafe boundary must be explicit and auditable | Ownership rules, observable store semantics, effect order, and concurrency memory model must agree; proof scope must state unsafe/FFI assumptions | Partial resource/effect prototypes; no complete ownership checker, execution semantics, or backend |
| **C3 — Isolated concurrent language** | S-C + T-C + R-A/R-C + V-A plus trace/model checking + B-B/B-C + Q-B/Q-C | Concurrency and distributed work become explicit; isolation can limit shared-memory races | Nondeterministic traces, protocol evolution, cancellation, scheduling, and runtime complexity challenge deterministic evidence reuse | A scheduled trace is a witness for one run. A stable scalar needs evidence across allowed schedules. Explicit order needs protocol keys preserved by rename | [COR-11](RT-03-04-SHARED-SEMANTICS-CORPUS.md#9-cor-11--actor-traces-and-failure-policies) enumerates closed finite traces and compares ordering and failure policies; [COR-12](RT-03-04-SHARED-SEMANTICS-CORPUS.md#cor-12--blocking-protocol-progress) distinguishes buffered progress from rendezvous blocking on two finite protocols. Cancellation, fairness, broader protocols, and runtime correspondence remain open |
| **C4 — Effectful functional language** | S-D + T-A with handlers + R-A/R-C + V-A or V-C + B-A with explicit runtime handlers + Q-A | Pure regions remain compositional while effectful code can describe state and I/O explicitly | Handler ordering and composition add proof and lowering obligations | The language must define which handlers observe operations, how effect rows are checked, and which activity belongs in external observations and dependency keys | [COR-10](RT-03-04-SHARED-SEMANTICS-CORPUS.md#8-cor-10--what-a-state-handler-exposes) exercises one scoped state effect across typed calls. The same state interface admits different traces and terminal outcomes. General handlers, row unification, and handler-aware summaries remain open |

No candidate is currently shown to satisfy all product goals, including easy small utilities, human readability, model neutrality, platform support, and independently checkable correctness. Those goals need explicit operational criteria before scoring candidates.

## 5. Compatibility constraints and dependencies

| Constraint | Consequence | Evidence status |
|---|---|---|
| A selected type/effect profile must refine the chosen core semantics and preserve its observation model. | RT-03 and RT-04 cannot be selected independently. | Strong dependency hypothesis, DEP-004; incomplete cross-profile fixtures identify concrete gaps. |
| Canonical identity must commit to exactly the semantic distinctions that affect behavior, while action/evidence keys also include their own inputs. | RT-05 decisions constrain dependency extraction, cache invalidation, verification reuse, and merge. | Broadly supported by prototype work; canonical SPG and hash envelopes remain undecided. |
| A backend or runtime may reject unsupported programs, but may not silently alter source semantics. | Every backend candidate needs an explicit supported subset and preservation evidence. | Design invariant in `PLAN.md`; no selected backend has passed the required cross-backend gate. |
| Any effect observable outside a local computation must appear in semantics, evidence inputs, and relevant dependency/identity relations. | Hidden I/O, scheduler state, ambient capabilities, or resource behavior can invalidate equivalence and reuse. | Analytically established requirement; concrete effect and environment inventory remains incomplete. |
| Security authority and evidence provenance are separate from content identity. | Hash equality cannot establish publisher trust, authorization, or proof authenticity. | Repeated in package/security research; operational trust design remains open. |
| Unknown or incomplete semantic/dependency information cannot be promoted to success or safe reuse. | Incomplete source extraction and unsupported constructs require conservative behavior. | Several prototypes implement fail-closed unknown handling within their stated scope; end-to-end completeness is unproved. |

See dependency edges DEP-004–010, DEP-012–019, DEP-023–024, and DEP-030–039 in [Research Dependency Map](RESEARCH-DEPENDENCY-MAP.md). Validate or revise these edges as the discriminating experiments run.

## 6. Shared evaluation criteria

Score each integrated candidate only after common definitions and workload weights are agreed. Use ordinal 1–5 scores with a written rationale and confidence for each score, then report sensitivity to workload weights rather than hiding trade-offs in one aggregate number.

| Criterion | Operational question | Minimum evidence for scoring beyond analytical |
|---|---|---|
| Semantic clarity | Can independent implementers predict the same observable result? | Shared corpus run by two independent semantics/implementations |
| Correctness assurance | Which claims can be checked independently, and what remains trusted? | Explicit proof/evidence boundaries and adversarial fixtures |
| Expressiveness | Can representative workloads be expressed without escape hatches? | Common task corpus with rejected/awkward cases recorded |
| Simplicity | How many rules, exceptions, and interactions must authors and tools learn? | Counted rules/interactions plus blind review by implementers |
| AI-agent usability | Can an agent make localized changes with bounded context and recover from diagnostics? | Controlled tasks measuring success, repair count, tokens, and unauthorized scope changes |
| Incremental behavior | Which changes invalidate which results, and is reuse sound? | Change benchmark with complete dependency audits and cold/warm runs |
| Runtime feasibility | Can the profile meet declared performance and resource bounds? | Same fixtures on selected target and reference runtime, with reproducible environment |
| Interoperability | Can it call existing system APIs with explicit, reviewable semantics? | Working FFI/OS vertical slice plus target-specific contract tests |
| Security and trust | Are authority boundaries and evidence inputs explicit and enforceable? | Threat model with adversarial tests for boundary violations and replay |
| Evolution | Can incompatible changes be detected, migrated, and versioned predictably? | Migration and compatibility fixtures across multiple language versions |

Do not score an unmeasured criterion as a numeric zero. Mark it **unknown**, report its effect on the candidate ranking, and prioritize an experiment if it could change the decision.

## 7. Discriminating research programme

1. **RT-03 shared semantics corpus:** define common programs and observations for values, control flow, divergence, recursion, errors, state, I/O, resources, cancellation, concurrency, and modules; implement at least two independent reference semantics for candidate profiles.
2. **RT-04 cross-profile type/resource corpus:** extend prototypes to ordered effects, payloads, row/handler coverage, borrowing/transfer, path-sensitive cleanup, and concurrency constraints; record rejected and UNKNOWN cases.
3. **RT-05 lifecycle and identity corpus:** turn Studies 05–08 into executable rename, duplicate, move, split/merge, recursive reference, and branch-merge cases evaluated under R-A/R-B/R-C.
4. **RT-07 evidence matrix:** state each evidence class's proposition, assumptions, exact inputs, trusted computing base, soundness claim, and reuse rule; include stale-proof and malformed-checker cases.
5. **RT-09/10/13 two-backend vertical slice:** select a bounded workload only after profiles are stated; execute through a reference interpreter and a second backend, compare observable traces, diagnostics, and resource behavior.
6. **RT-16 threat-model exercise:** extend [Threat Model 01](RT-16-THREAT-MODEL-01.md) from its bounded authorization fixtures to concurrent service operations, cache/evidence replay, package provenance, runtime capabilities, solver/checker boundary, and workspace recovery.
7. **RT-01 workload and weighting study:** use the [reference workloads](RT-01-REFERENCE-WORKLOADS.md) and common acceptance observations. The CLI pilot is executable with two host references. Run it against candidate toolchains, measure authoring tasks with the stated controls, and agree on workload weights before candidate scoring.

For every experiment, record source commit, tool versions, fixtures, command, raw results, limitations, and criteria that would falsify the favored vector. Keep unsupported claims marked unknown.

## 8. Readiness assessment for comparative selection

The [shared semantics corpus](RT-03-04-SHARED-SEMANTICS-CORPUS.md) contains bounded evidence for A/B/D typed calls and private scalar state, A/D resource outcomes, and C actor scripts. The RT-04 call projection covers the typed trees. Source correspondence, cross-profile type and resource validation, the identity envelope, program proofs, the two-backend slice, the threat model, and workload weights remain open.

All four variants agree on the scalar increment workload. Logging and terminal rejection distinguish handlers with the same state interface. In C, cross-sender delivery choices distinguish logs even when the scalar agrees, and can also change the scalar for noncommuting operations. Use these witnesses when assessing handler and protocol dependencies. COR-12 adds a bounded blocking/progress contrast for two actors, but failure, cancellation, competing receivers, and runtime correspondence remain untested.
