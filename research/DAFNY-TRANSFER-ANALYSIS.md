# Dafny transfer analysis for LLMLang

**Status:** research plan and preliminary transfer hypotheses  
**Date:** 2026-11-25  
**Relationship:** expands [Dafny–LLMLang comparison](COMPARISON-DAFNY-LLMLANG.md); not a language decision.

## 1. Purpose

Identify Dafny ideas that LLMLang can reuse, adapt, or should avoid copying. The study covers contract constructs, proof workflow, source syntax, and possible tool integration. A similar name or surface form does not imply semantic compatibility. All LLMLang items below are proposals until the language semantics and a representative implementation establish them.

Dafny is a verification-aware language with a verifier and compiler. Its documented workflow translates programs to verification conditions checked through Boogie and an SMT solver, typically Z3 ([reference manual](https://dafny.org/latest/DafnyRef/DafnyRef)). LLMLang currently has a project concept and selected Lean/Logos/SMT prototypes, not a complete Dafny-equivalent language verifier.

## 2. Transfer matrix

| Dafny mechanism | Problem it solves | LLMLang candidate | Initial disposition | Required experiment / caution |
|---|---|---|---|---|
| `requires` and `ensures` | Caller obligations and callee guarantees; modular reasoning | First-class precondition and postcondition clauses linked to a contract object | **Adopt the concept; design LLMLang semantics and syntax independently** | Test implication/refinement direction, exceptional outcomes, state, and whether calls can be verified from contract alone |
| Loop `invariant` | Summarizes the property preserved across iterations and used at loop exit | Explicit loop invariant nodes and proof obligations | **Adopt** | Measure how users/LLMs discover useful invariants; diagnose missing, weak, and inconsistent invariants |
| `reads` / `modifies` and dynamic frames | Bound heap observations and mutations | Explicit frame/effect clauses, possibly mapped to capability/effect types | **Adapt** | Distinguish heap footprint from I/O, network, resource ownership, and authority; specify aliasing and frame soundness |
| `decreases` | Prove recursion/loop termination using a well-founded measure | Termination contract with metric and explicit `must_terminate` / `may_diverge` policy | **Adopt the obligation; avoid assuming identical syntax** | Define metric domains, lexicographic order, inference, and divergence propagation; see [Dafny termination guide](https://dafny.org/dafny/OnlineTutorial/guide) |
| Ghost variables/methods and lemmas | Add proof-only state and proof steps without runtime behavior | Specification/proof graph objects that erase before execution | **Adapt** | Define erasure, noninterference with executable semantics, source mapping, and whether proof objects are trusted or checked |
| `assert`, `assume`, `reveal`/opacity and proof blocks | Shape solver context and proof decomposition | Explicit proof hints/obligations; assumptions are separately classified and pinned | **Use cautiously** | Never allow unchecked assumptions to be mistaken for proved facts; keep assumptions visible in evidence and fail closed when unsupported |
| SMT-generated verification conditions | Automate routine proof obligations | Keep Lean/Logos for selected kernel-checked paths; compare solver backends for scalable arithmetic/logic | **Reuse as backend option, not as semantic authority** | Bind query to typed source/IR and assumptions; track solver version/options; preserve `UNKNOWN`, timeout and crash distinctly |
| Modules, abstraction, opaque functions | Control visibility and proof dependency | Specification/implementation separation and stable public contract boundaries | **Adapt** | Verify abstraction leakage and dependency invalidation; module interface hash must reflect semantic contract, not implementation details |
| Type system, datatypes, termination discipline | Restrict program states and support automated reasoning | Start with a small typed core; consider algebraic data types and refinement predicates | **Study and subset** | Avoid importing all language features before the core operational semantics and type soundness are clear |
| Dafny source as code plus specification | Makes contracts close to the implementation they constrain | Human-readable LLMLang DSL as a view/edit format over typed SPG | **Evaluate** | Round-trip parse/print; no semantic loss; define canonical source and diagnostics if SPG is authoritative |
| Compiler to multiple target languages | Makes verified code usable in deployment environments | Potential backend integration after semantic core is stable | **Defer** | Prove or validate translation preservation and identify which generated/external code lies outside the guarantee |

## Dafny heap and concurrency boundary

Dafny has a heap of reference objects and arrays, alongside immutable value types such as integers, sets, sequences, multisets, maps, and datatypes. Heap reads and writes can be bounded with `reads` and `modifies` frame clauses. These frames support modular sequential reasoning: they state which heap locations a declaration may depend on or modify. They do not, by themselves, provide mutual exclusion, atomicity, memory-ordering rules, or a concurrent-history semantics ([framing reference](https://dafny.org/latest/DafnyRef/DafnyRef)).

Dafny is a sequential language and has no native constructs for spawning or controlling concurrent execution. It does, however, provide the `{:concurrent}` attribute for declarations intended to be safe when the target-language environment executes them concurrently. The documented restriction is that such a declaration must have empty read and write frames, preventing access to shared mutable state while allowing mutation of newly allocated objects. `{:assume_concurrent}` can relax this restriction, but it represents an assumption because these concurrency semantics are not directly expressed in Dafny syntax. This facility is useful for a restricted race-avoidance condition; it is not a general verifier for concurrent algorithms, synchronization protocols, or linearizability ([Dafny `{:concurrent}` reference](https://dafny.org/latest/DafnyRef/DafnyRef)).

The transfer study should distinguish at least three claims:

1. **Sequential heap safety:** a method respects its frame and functional contract.
2. **Race avoidance for isolated calls:** declarations satisfy Dafny's restricted `{:concurrent}` conditions in the target environment.
3. **Concurrent algorithm correctness:** all allowed interleavings satisfy a stated history/state property, including synchronization and memory-order assumptions.

Only the first is ordinary Dafny verification; the second is a restricted language-enforced condition plus an execution-environment premise; the third requires a separate formal model and proof methodology. LLMLang should not treat `reads`/`modifies` or effect capabilities alone as a concurrency proof. Its research must define shared-memory semantics, atomic operations, synchronization, observable histories, and the correspondence between the model and target runtime.

## 3. Candidate contract core

A useful experiment should start with a small, ordinary procedural example, not the entire Dafny language. A possible LLMLang surface sketch is:

```text
operation max(a: Int, b: Int) -> Int
  requires true
  ensures result >= a and result >= b
  ensures result == a or result == b
  effects none
{
  if a >= b { a } else { b }
}
```

This is illustrative only. The experiment should compare at least three representations: Dafny source; an LLMLang readable surface syntax; and a typed SPG representation. It should test parse/print round-tripping and prove or otherwise validate that all three describe the same bounded semantics. Do not treat surface similarity as a translation proof.

The initial construct set should cover:

- procedure inputs, outputs, and types;
- preconditions and postconditions over inputs, results, and pre/post state;
- loop invariants;
- frame/effect bounds;
- failures and exceptional results;
- termination obligation and allowed divergence;
- explicit assumptions and proof status;
- specification-only declarations versus executable declarations.

Keep quantifier triggers, coinduction, advanced trait/module behavior, custom solver attributes, probabilistic/concurrent semantics, and backend-specific interop outside the first subset unless a motivating use case requires them.

## 4. Verification workflow lessons

Dafny's VC + SMT approach is valuable for automation, but LLMLang should separate four questions:

1. **Was the source parsed and type checked?**
2. **Was the intended verification condition correctly derived from the source semantics and contract?**
3. **Did the solver/checker establish that obligation, under which assumptions and resource limits?**
4. **Does the proved specification represent the stakeholder's intent?**

A solver success cannot compensate for a wrong or unsound source-to-query translation. A proof of a contract cannot establish intent adequacy. LLMLang evidence should bind the exact source/SPG root, contract root, generated query/IR, assumptions, verifier identity/configuration, and result. `UNKNOWN`, timeout, unsupported constructs, and infrastructure errors must not collapse into success. For SMT reuse, test whether independent checking or proof certificates are available and practical for the chosen fragment; otherwise record solver trust explicitly.

The current project has kernel-checked Lean results for deliberately small expression-level source-to-query fragments, and ongoing gaps around command/state semantics and complete source-derived query binding (see Stage 2.3 and Scenario 34). The Dafny study should build on those boundaries rather than implying they already cover Dafny's full proof workflow.

## 5. Syntax evaluation questions

Compare Dafny and candidate LLMLang notation on the same examples using both human and LLM participants or controlled agent trials:

- Can a reader distinguish executable code, specification-only code, assumptions, and proof hints at a glance?
- Are effects, mutation frames, failures, and divergence visible where a contract is declared?
- Can an LLM make a requested implementation-only change without changing a contract?
- Are diagnostics local and actionable when a proof fails?
- Does the surface syntax map bijectively to the typed SPG subset, or are there ambiguous/hidden defaults?
- Is generated Dafny readable enough to audit, or should it be an internal backend artifact?

Evaluate clarity, omission errors, accidental contract weakening/strengthening, edit locality, verification success, and reviewer time. A syntax that looks concise but hides defaults or makes proof failures harder to localize should not be preferred just because it is LLM-generated.

## 6. Integration experiments

### Experiment A: Dafny as an oracle/baseline

For a bounded pure or sequential fragment, implement the same examples in Dafny and the current LLMLang verification path. Compare outcomes and counterexamples. This checks consistency on the sample, not equivalence of the languages.

### Experiment B: LLMLang to Dafny translation

Translate only a declared supported subset. For each translation, retain a source map and exact input/output hashes; reject unsupported source constructs. Independently compare behavior on generated bounded inputs and establish a formal translation-preservation argument before claiming soundness.

The [Dafny mapping for overlapping copy and frames](semantic-representation/RT-05/RT-05-DAFNY-SPG-COPY-FRAME-2026-11-25.md) renders an exact graph into Dafny preconditions, final-state and loop clauses. It records proof provenance across two emitted source profiles and measures the actual array trace. The source proof and the access projection have separate evidence.

### Experiment C: Dafny contracts imported into SPG

Parse a limited set of Dafny declarations and represent their contracts as typed graph objects while retaining the original text. Record constructs that cannot map losslessly. This tests whether the graph is useful without prematurely making SPG the only source of truth.

### Experiment D: AI-assisted maintenance

Compare human/LLM workflows for a proof-preserving refactor, contract change, implementation-only change, and intentionally invalid change. Track unintended edits, proof repair effort, review time, and stale evidence detection.

## 7. seL4 as a high-assurance comparison case

seL4 is not written in Dafny. Its verification framework uses Isabelle/HOL to connect abstract and executable specifications to the C implementation; for selected configurations, a further proof connects C to the machine binary. The C source is parsed into a formal semantic model, and refinement proofs connect that model to higher-level specifications. The project also proves security properties such as integrity and confidentiality for specified configurations ([seL4 proofs](https://sel4.systems/Verification/proofs), [verification FAQ](https://sel4.org/About/FAQ.html), [seL4 white paper](https://beta.sel4.systems/About/seL4-whitepaper.pdf)).

This is not evidence that Dafny cannot express kernel contracts. It shows that high assurance for a kernel requires more than convenient contract syntax: the verification architecture must cover the actual low-level implementation and, where claimed, the binary, while stating hardware, boot, machine-interface, compiler, and configuration assumptions. Dafny `extern` declarations let a Dafny program rely on external implementations through contracts, but do not prove that external C/C++ implementations or ABI bindings satisfy those contracts. Its compiler targets and FFI are not by themselves a verified C-kernel-to-binary pipeline ([Dafny reference](https://dafny.org/latest/DafnyRef/DafnyRef), [installation and target-language notes](https://dafny.org/dafny/Installation)).

Rewriting seL4 in Dafny is technically conceivable as a new kernel project, but it would not preserve the existing seL4 proofs through a source-language substitution. The implementation, low-level architecture bindings, ABI boundary, build/runtime assumptions, refinement chain, security theorems, and binary-level evidence would need to be rebuilt or re-established for the new implementation and configurations. An all-Dafny kernel that calls external low-level code would still need an explicit trust boundary and evidence that the external code refines its contracts.

Add a controlled seL4-inspired case study to the transfer programme:

- Compare a small kernel-like component at three levels: abstract state machine, executable implementation, and an explicit low-level/ABI boundary.
- Ask which obligations Dafny can discharge directly, which need a separate model or proof assistant, and which remain assumptions about hardware, assembly, runtime, or external code.
- Determine whether Dafny is a useful implementation/specification language for the bounded component, a contract frontend, or a baseline beside Isabelle/HOL.
- Do not extrapolate a toy component result to seL4 itself. Record properties, configuration, source/binary scope, assumptions, and tool trust explicitly.

The [Dafny kernel-style lookup and foreign boundary](formal-verification/RT-07/RT-07-DAFNY-KERNEL-FOREIGN-BOUNDARY-2026-11-25.md) measures this boundary on a fixed-width table lookup. Dafny verifies the source implementation and a separate client under an extern declaration. Independent native results detect wrong overflow handling, different refusal priority and an incompatible signed result binding. The case distinguishes the scope of the source proof from the exact external-provider obligation.

## 8. Decision criteria

Prefer reuse of Dafny tooling when it provides the needed verification semantics and the translation boundary can be made explicit and trustworthy. Prefer LLMLang-native constructs only when the requirements materially differ—for example, provenance-aware contract lifecycle, effect/capability composition, or graph-level incremental evidence—and a small formal model demonstrates that difference.

Do not transfer a mechanism solely because it exists in Dafny. For every proposal, record:

- exact construct and intended guarantee;
- LLMLang semantic counterpart, if any;
- source/IR mapping and unsupported cases;
- trust boundary and failure statuses;
- impact on text syntax and typed SPG;
- evidence from examples/prototypes;
- unresolved questions and decision owner/status.

## 9. Expected outputs

1. Construct-by-construct transfer matrix with accepted/adapt/reject/defer status.
2. Candidate LLMLang contract grammar and semantics for a deliberately small subset.
3. Reproducible examples in Dafny and LLMLang, including negative and unsupported cases.
4. A documented trust-boundary and evidence-binding design for any Dafny integration.
5. Recommendation on whether Dafny remains an external baseline, a prototype backend, or a long-term verification component.

No language syntax or backend decision is made by this document.
