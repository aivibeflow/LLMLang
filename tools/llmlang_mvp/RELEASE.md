# Scalar MVP release record

Starting revision [b89f832](https://github.com/aivibeflow/LLMLang/commit/b89f83225bc74517274eb168d54d6642740fce8b). The release adds the Rust Stage 0 compiler, portable scalar Contract IR, solver counterexample replay, exact-revision review and a bounded trace evidence profile.

## Acceptance evidence

| Acceptance item | Observed result and reproduction |
| --- | --- |
| Clean native build and repeated SPG | The offline Stage 0 build from the lockfile and a signed test approval produced a native Calculator. Two separate frontend runs reproduced the canonical SPG with SHA-256 `fdb0aab702b602775e544a1ad71993948c8658d0a6cb287525ade63395a76c76`. The Rust and Python frontends agreed. [Clean-checkout commands](README.md#reproduce-from-a-checkout) |
| RT-01 reference workloads | All 34 cases passed in both execution paths, including closed stdout. The comparison checks exact stdout and stderr bytes and exit status. Reported exclusions are multi-record Calculator input and trailing records. Hello and Echo use the host adapters. [Corpus](../../research/language-design/PROTOTYPES/CLI-WORKLOADS-01/run.py) · [Report generator](conformance.py) |
| Exact controlled review | Each scalar Contract round-trips through the controlled parser. The review packet shows semantic revision, exact source input digests, clause JSON Pointers, and scenario comparisons. A previous Contract IR revision can supply the semantic diff. [Review implementation](review.py) · [Review commands](README.md#review-and-build-calculator) |
| Independent admission gates | Boogie and Z3 verified the conforming Calculator provider. The stronger-precondition and invalid-body controls failed different obligations. A conforming replacement kept the old caller snapshot intact. Stale pins and stale or forged signed approval were rejected. Verification reports classify replayed, abstract and unconfirmed counterexamples. [Controls](controls.py) · [Replay tests](test_counterexamples.py) |
| Independent scalar theorem | Lean checked the scalar addition model and its error outcome. [Lean model](ScalarChecks.lean) |
| Retained run evidence | The workflow publishes the review packet, solver report, finite trace check and exact RT-01 process observations. CI provisions a disposable signing identity for its tests. [Workflow](../../.github/workflows/llmlang-mvp.yml) |

Pinned toolchain profile is Linux x86-64, Python 3.12, Rust 1.85.1, Boogie 3.5.5, Z3 4.13.3, OpenSSL 3 and Lean 4.36.0. `check` records verifier versions, executable and obligation digests, input identities and exact binding references. `conformance --report PATH` records the process observations and local tool versions from the actual run.

## Contract IR coverage for PLAN §1.3

The [scalar wire and CNL specification](CONTRACT-IR.md) defines the executable function semantics, typed exchange and exact identities. The [trace profile](TRACE-PROFILE.md) defines typed finite observations and a separate checked CNL grammar. Every covered clause below has a reference evaluator and a reproducible check. A checked finite observation covers only the supplied trace or trace pair. General guarantees require the applicable proof and evidence policy.

| Contract family | Expressible and checked CNL | Verification or evidence boundary |
| --- | --- | --- |
| Preconditions and admissibility | Scalar typed predicates over ordered `Bool` and `I64` parameters | Reference evaluation and Boogie/Z3 domain and call obligations. Aggregate validity and quantifier semantics are future profiles. |
| Functional postconditions | Scalar success predicates over inputs and result. Explicit error guards. | Reference outcome evaluation and Boogie/Z3 conformance. Collections and quantified properties are outside the scalar profile. |
| Invariants and algebraic laws | Trace invariant over a nonnegative `I64` field at the endpoints | Endpoint checks. Lean checks the separate scalar addition theorem. Inductive invariants and algebraic laws over arbitrary structures require other profiles. |
| Machine arithmetic and representation | Scalar signed `I64`, mathematical predicate integers and checked arithmetic outcomes | Boogie/Z3, reference interpreter, Lean addition and RT-01 arithmetic boundaries. Floating point, layout and codecs require other profiles. |
| Frames, effects and order | Trace endpoint frames, permitted events and protocol event ordering | One closed finite observation. Aliasing and intermediate reads or writes require instrumented observations. |
| Ownership, aliasing and lifetimes | Trace acquire and release with a resource identifier | Exactly-once cleanup on completion within the declared event vocabulary. Borrowing, shared aliases and allocator correspondence require separate models. |
| Errors, cancellation, cleanup and failure atomicity | Scalar error guards. Trace error, cancellation and partial outcomes with preserved fields and permitted events. | Scalar obligation checks plus bounded failure and cleanup observations. Native rollback and unrecorded effects are outside this trace claim. |
| Termination of loops and recursion | Scalar acyclic SPG. Trace nonnegative rank with strict decrease at observed steps. | Scalar structural termination and finite rank checks. General loop coverage, recursion and correspondence of rank events to source require separate evidence. |
| Protocols and state transitions | Trace initial and terminal states with deterministic event transitions | Finite protocol checking, including disallowed transitions and unfinished execution. |
| Time, concurrency and progress | Trace trigger/response deadline in logical ticks | Finite inclusive deadline checking with explicit completion. Scheduling, fairness and memory-model guarantees require other profiles. |
| Authority and information flow | Trace principal allowlist per event and comparison of selected observations | The trace provides the principal and observations. General noninterference and authentication of event producers require separate models. |
| Cost and resource budgets | Trace upper bound on event occurrences | Counts on a finite log. Worst-case and physical resource guarantees require a modeled cost and separate proof. |
| Refinement, equivalence and preservation | Scalar input inclusion and allowed outcomes. Trace equality for specified observations on a paired input. | Boogie/Z3 checks scalar refinement independently of body conformance. The trace route checks one explicit pair. |
| Modular and foreign contracts | Scalar exact direct calls with public and provided references. Trace checks required, public and provided hashes against a call event. | Proof closure for exact scalar states and callees. Foreign ABI or provider premises stay open in the trace profile. |
| Evidence applicability and assumption closure | Exact scalar binding and approval records. Trace assumption clauses and evidence identities. | Fresh proof and signature checks gate Calculator. Trace assumptions yield conditional evidence and cannot authorize a scalar binding. |

The full Contract IR roadmap continues under [PLAN §1.3](../../PLAN.md#13-contracts-and-compatible-implementations). The human-review study, general source-to-backend proof correspondence and production trust decisions retain their separate acceptance gates.
