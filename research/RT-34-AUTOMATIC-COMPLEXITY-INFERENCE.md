# RT-34 — Automatic Complexity Inference, Resource Contracts, and Algorithm Optimality Verification

**Status:** Research brief; proposed, non-normative; no analyzer or language rule selected  
**Priority:** P0 for foundations and pilot evaluation; P1 for advanced domains  
**Updated:** 2026-11-24  
**Tracking:** [Issue #412](https://github.com/aivibeflow/LLMLang/issues/412)  
**Related:** [Scenario 14](RESEARCH-SCENARIO-14-FORMAL-BEHAVIORAL-CONTRACTS-AND-REFINEMENT.md), [Scenario 36](RESEARCH-SCENARIO-36-RECURSION-TERMINATION-AND-FUEL.md), [RT-32](RT-32-VERIFIED-SPG-TO-LEAN-PIPELINE.md), [RT-33](RT-33-PROOF-BACKEND-SELECTION-AND-ORCHESTRATION.md), [RT-26](RESEARCH-DEPENDENCY-MAP.md#14-hierarchical-resource-accounting-and-real-time-enforcement-rt-26).

## 1. Research goal and hypotheses

Investigate whether LLMLang can derive and independently verify asymptotic resource guarantees from typed contracts, a versioned computational model, and SPG implementations, and derive conditional lower bounds on the underlying problem from functional specifications. Aim toward proof-carrying complexity for components, without requiring a particular algorithm in a functional specification.

Distinguish three claims:
- Problem lower bound: every admissible algorithm satisfying a contract must incur at least a stated asymptotic cost in a specified computational model (with explicit uniformity, input domain and quantifiers).
- Achievable upper bound: there exists a conforming implementation with a proved bound. An identified algorithm and correctness proof are witnesses.
- Implementation bound: a particular implementation revision satisfies a cost bound. A matching problem lower bound and implementation upper bound can establish optimality for that metric and model.

Hypotheses: typed SPG control flow and call bindings permit reusable cost summaries; size relations and resource invariants can be discharged with existing proof machinery; theorem-library matching and reductions can establish some task lower bounds; an independently checked symbolic bound is more useful than an unqualified LLM guess. Compare against manual annotations, finite observations and an analysis without SPG composition.

Non-goals: a complete exact analyzer for arbitrary programs (undecidable in general, even totality alone does not imply inferable tight bounds); hardware-independent wall-clock guarantees; automatic optimality for all specifications; selecting syntax or a universal prover.

## 2. Existing foundation and limitation

The glossary permits termination, liveness and resource bounds as observable contract properties, but a declaration is not evidence of conformance. Scenario 14 treats resource/time guarantees as explicit observations. Scenario 36 distinguishes source fuel, VM gas, external interruption, and divergence. Its [countdown prototype](PROTOTYPES/RT-04-01/rt03_recursion_fuel.py) counts abstract transitions for a limited model, not general asymptotics. RT-32 proposes source-derived obligations and a checked proof dependency graph (PDG); RT-33 provides backend capability profiles and abstention. [DOMAIN-05](PROOF-OBLIGATION-BENCHMARK.md) already includes asymptotic operation counts.

[CF-005](CONTRACT-FORMALIZATION-CORPUS/cases/CF-005-sort-array.md) specifies sortedness, multiplicity and unchanged input, explicitly without a complexity requirement. A copying insertion sort and a copying merge sort can both conform while having different worst-case work. Arbitrary terminating extra work can preserve those functional observations. Thus a functional contract alone cannot imply a uniform upper bound for every conforming implementation.

Examples (unbounded input families; stated model only):

| Problem | Assumptions | Bound |
|---|---|---|
| Indexed lookup | random access, constant-cost word operations | tight worst-case Theta(1) |
| Sum or maximum | arbitrary unindexed contents, exact result, constant-cost arithmetic/comparison | tight worst-case Theta(n) |
| Unsorted membership | comparison/query model, no preprocessed index | tight worst-case Theta(n) |
| Sorted membership | random access, comparisons, no auxiliary index | tight worst-case Theta(log n) |
| Sorting | arbitrary distinct keys, comparison decision tree | tight optimal worst-case Theta(n log n) |
| Integer sorting | keys in range of size k, counting-sort storage and word costs | achievable O(n+k), not universal optimality |
| All ordered pairs | explicit output entries | tight Theta(n^2) output work |
| All subsets | explicitly materialize each subset's elements | tight Theta(n*2^n) output work |

For comparison sorting, at least n! distinguishable permutations imply a decision-tree depth >= ceil(log2(n!)); a proved merge sort upper bound closes the gap. For sum, changing an unread element changes the required result. Both lower bounds depend on the model and admissible inputs; cached sums, indexed structures, bounded domains or different observations may invalidate them. Output representation matters: lazy generation, sharing or compression changes materialization bounds.

## 3. Candidate Resource Contract IR and cost semantics

Keep requirements, derived claims, and checked evidence distinct. A versioned resource contract describes:
- size vector and its domain (length, bits, vertices/edges, output size, structure depth, history length, initial capacity, callback cost);
- admission predicate, representation, termination/outcome scope, arithmetic semantics and cost-model ID;
- metric (source steps, comparisons, allocations, cumulative allocation, peak live bytes, stack bytes/depth, I/O calls/bytes, communication, work/span, gas);
- aggregation (worst/best over nonempty admissible inputs, expected cost with distribution and random source, amortized over operation histories and initial potential);
- asymptotic relation and expression (O, Omega, Theta), growth domain, constants and threshold witnesses or proof of their existence;
- required guarantee vs inferred fact, trust and dependencies.

For nonnegative cost C(x), size s(x)=n, worst-case O(g(n)) means there exist constants c>0 and N such that every admitted execution on every admitted input of size n>=N terminates within c*g(n) for the specified metric and successful outcome scope. Model alternative outcome obligations separately; do not count fuel exhaustion as successful completion. Lower bounds on worst-case cost require existence of costly inputs/executions at the stated sizes, or explicitly scoped subsequences; a single costly execution is not an asymptotic counterexample. Define multi-parameter growth domain and uniformity explicitly; avoid vacuous proofs over empty or bounded size domains. Expected and amortized claims are not interchangeable with worst-case bounds.

Illustrative notation only (not LLMLang grammar):

    contract sort(input: Array<T>) -> Array<T> {
      ensures sorted(result) && permutation(input, result)
      ensures unchanged(input)
      ensures terminates
      size n = length(input)
      complexity {
        model: comparison_ram_v1
        work.worst <= O(n * log(n))
        memory.auxiliary <= O(n)
      }
    }

An infer request is a query, not a promised contract. Example: infer work.worst, peak_live_bytes, stack and optimality. Define whether resource cost is public observable semantics or implementation metadata; a public bound change can affect substitutability. Stronger upper guarantees can refine weaker ones under aligned models; do not compare incomparable profiles silently.

Cost semantics must charge data-dependent primitive costs (big integers, Unicode traversal, hashing, comparator callbacks), initialization, allocation/cleanup, exceptions and external calls. Distinguish mathematical source cost, runtime gas and measured wall time; functional preservation by a backend does not imply preservation of complexity. Use resource-aware simulation or a separately checked target cost model. Cost models, instrumentation and semantics must be versioned.

## 4. Analysis architecture and vectors

Proposed pipeline: specification + computational model -> task-bound theorem matching/reduction; implementation SPG + cost semantics + callee summaries -> symbolic cost obligations -> RT-33 backend routing -> independently checked evidence linked into PDG -> comparison with required resource guarantees and task bounds. A synthesis agent can propose better algorithms but may not certify its own claim.

| Construct | Candidate analysis |
|---|---|
| Sequence | Sum costs with intermediate size/state relations |
| Branch | Maximum over feasible paths for worst-case; distribution for expectation |
| Loop | Derive iteration bound by ranking/size change; sum variable iteration costs |
| Nested loop | Nested sums, dependent bounds and feasible paths; do not blindly multiply |
| Recursion / mutual recursion | SCC summaries, well-founded size descent and recurrences |
| Calls / higher order | Instantiate size/effect/cost summaries at call sites; unknown callback cost remains symbolic or unknown |
| Parallelism | Work sum; span dependency critical path under a specified task model |
| Memory | Track live sizes and lifetimes, aliasing, sharing, allocator assumptions, peak not sum |
| Stateful structures | Potential method over admissible histories; initial potential and cleanup |
| FFI and external providers | Versioned proved/assumed summaries; no silent constant-cost default |

Illustrative recurrences: binary search T(n)<=T(floor(n/2))+c gives O(log n) with a valid base case and a comparison model; matching worst-case witnesses give Theta(log n). Merge sort T(n)<=T(floor(n/2))+T(ceil(n/2))+c*n gives O(n log n). A pair of lower/upper proofs is needed for a tight claim. Naive Fibonacci has Theta(phi^n) calls; memoized Fibonacci takes O(n) arithmetic operations, not necessarily O(n) bit operations. Ranking functions prove descent, not automatically a useful quantitative bound.

Compare vectors:
- A: manual cost contracts + generated verification conditions.
- B: abstract interpretation, size change, ranking functions, recurrence extraction and symbolic solving.
- C: automatic amortized resource analysis (AARA), potential/type annotations and inference.
- D: proof-producing theorem matching, induction and source-correspondence verification in Lean or another eligible engine.
- E: hybrid orchestrator with LLM candidate invariants/proofs, deterministic checks and independent evidence validation.
- F: empirical scaling inference, only heuristic evidence and never proof promotion.

Compare applicability, expressiveness, proof-checking TCB, unsupported features, false-success rate, coverage, abstention, precision, time and cost, incremental invalidation, annotations and diagnostics. No vector is selected.

## 5. Evidence model, optimality, and incremental composition

Keep claim kind (upper/lower/tight/problem optimality), outcome (proved/refuted/unknown/unsupported/error/timeout), assurance (independently checked/conditional/assumed/empirical), and scope (finite/unbounded/source/target) orthogonal. Preserve assumptions and unclosed proof dependencies. A candidate bound that cannot be proved is UNKNOWN, not violated; a proven asymptotic violation needs a family or theorem, not an isolated sample. Finite exact budget violations can have single concrete witnesses.

Bind evidence to exact contract and implementation hashes, size/domain and cost-profile hashes, semantics, binding/dispatch targets, callee proof closure, solver/translator/checker versions and configurations, assumptions and target/runtime versions where applicable. Changing implementation invalidates its proof; caller reuse may be allowed only through an unchanged resource contract with a newly valid provider obligation and complete dependency audit. Public bound, cost model, size domain or assumption changes invalidate affected dependent claims. Source evidence cannot silently discharge target guarantees.

Example: sort O(n log n), deduplicate O(n), calculate O(n) compose into O(n log n) if intermediate sizes are <=n, costs share a model, and calls terminate as assumed. A provider that returns an expanded result requires re-analysis. If an implementation bound matches a problem lower bound for the same metric, domain, model and outcome, prove asymptotic optimality. Other metrics and constant factors may still differ. Use checked evidence for implementation selection and resource-regression gates; do not trade functional correctness or approval authority for performance.

## 6. Prior-art comparison plan

Primary-source starting points (comparative reading/reproduction pending; not a claim of integration):
- Hoffmann and Jost, *Two Decades of Automatic Amortized Resource Analysis*, [research survey](https://doi.org/10.1017/S0960129521000487) — potential-based type/resource inference; confirm supported fragments and polynomial/exponential/logarithmic extensions.
- [KoAT](https://koat.verify.rwth-aachen.de/) — symbolic complexity/termination analysis for integer programs; investigate translation coverage and certificates.
- Zhan and Haslbeck, *Verifying Asymptotic Time Complexity of Imperative Programs in Isabelle*, [arXiv:1802.01336](https://arxiv.org/abs/1802.01336) — time credits and formal asymptotic verification.
- [Lean recursion reference](https://lean-lang.org/doc/reference/latest/Definitions/Recursive-Definitions/) — termination evidence and kernel checking; investigate cost-aware embeddings rather than assuming native execution cost.
- [Wasmtime fuel](https://docs.wasmtime.dev/examples-interrupting-wasm.html) — dynamic resource enforcement, not source complexity inference.

Pin exact versions and primary references before experiments. Verify applicability and licensing, whether outputs are independently checkable and whether source translation is sound.

## 7. Research work packages

| ID | Work package / required output | Priority |
|---|---|---|
| CX-01 | Versioned abstract cost semantics and growth definitions | P0 |
| CX-02 | Size-domain and intermediate-size inference, nonvacuity checks | P0 |
| CX-03 | Resource Contract IR and refinement/assumption schema | P0 |
| CX-04 | Loop bounds, variable costs, path-sensitive sums | P0 |
| CX-05 | Recurrences, mutual recursion, termination and symbolic solvers | P0 |
| CX-06 | Interprocedural composition, higher-order functions and SPG bindings | P0 |
| CX-07 | Source correspondence, checked resource proofs and PDG | P0 |
| CX-08 | Problem lower bounds via theorem library, adversary and reductions | P1 |
| CX-09 | Model-scoped optimality proofs, proof of existence and lower-bound matching | P1 |
| CX-10 | Amortized analysis and potential-based inference | P1 |
| CX-11 | Peak live memory, stack, allocation and lifetime analysis | P1 |
| CX-12 | Work/span, I/O, communication and parallel/distributed profiles | P1 |
| CX-13 | Probabilistic and expected costs, adversary/distribution assumptions | P1 |
| CX-14 | Multivariate, bit and output-sensitive complexity | P1 |
| CX-15 | Resource-preserving lowering, target cost translation and instrumentation | P1 |
| CX-16 | Verified algorithm synthesis and selection with resource constraints | P1 |
| CX-17 | Resource-proof caching and invalidation, exact binding closure | P1 |
| CX-18 | Complexity regression diagnostics and policy gates | P1 |
| CX-19 | Independent benchmark, comparison and evidence audit | P0 |
| CX-20 | External calls, FFI, libraries and assumed/checked summaries | P1 |

## 8. Experiment and exit criteria

Use the [complexity benchmark plan](RT-34-COMPLEXITY-BENCHMARK.md) across CF and POB without conflating formalization, inference and checking. Start with pure deterministic unbounded mathematical input sizes, a small costed typed IR, constant-cost primitives and explicit positive size domain. Build a reference evaluator and independent symbolic cost proof checker, then implement loop/recursion/call inference. Test changed size measures, missing call bindings, overflow, hidden primitive costs, incorrect recurrences, impossible branches, stale proofs and finite-only extrapolations. Extend to memory, callbacks, amortization, probability, parallel work/span and target preservation only with explicit semantics.

Record immutable baseline, source/model/profile, benchmark case versions, tool versions, raw results, proof terms and trusted assumptions. Independently adjudicate expected outcomes and separate observed finite data from unbounded proofs. Measure soundness (no known false proven claims in evaluated scope, not a universal soundness guarantee), completeness/abstention, bound tightness, proof size, runtime, memory, incremental reuse and manual effort. Require a formal soundness theorem for the modeled analyzer fragment or independently checked per-claim certificates plus translation evidence. Include negative controls and reproducible commands before any implementation status is advanced.

Current evidence class: analytical research brief and existing bounded prototype references. No new experiment, source correspondence theorem, analyzer, accepted cost model or normative resource contract is claimed. Report alternatives and open gaps to the specification synthesis process.

## Public-interface integration (2026-11-24; proposed)

A public interface may expose a resource guarantee independently of the selected algorithm. Verify the implementation's inferred/proved bound and its refinement of the public bound under the same size/cost/model, quantification and environment. Worst-case, expected and amortized bounds are not interchangeable; O upper bounds do not establish lower bounds, exact costs or optimality. Substitution can change observed cost within the public allowance; performance-sensitive callers must state stronger requirements explicitly. Rebinding invalidates exact implementation resource evidence, not the public requirement itself.

Related: [Public interfaces and verified contract refinement](PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This is a candidate follow-up; it does not change accepted rules or previously reported evidence.

## Explicit assumptions and conditional verification (RT-36; proposed)

External cost summaries and environmental cost/fairness premises are typed, model-scoped assumptions. A checked complexity theorem conditional on an unproved foreign cost summary is not an unconditional executable resource bound. See [RT-36 — Formal Verification Assumptions, Trust Boundaries and Conditional Proof Management](RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md). This is a candidate follow-up, not an adopted rule or new experimental result.
