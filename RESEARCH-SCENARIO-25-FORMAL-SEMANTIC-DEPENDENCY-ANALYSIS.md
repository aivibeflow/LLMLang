# Scenario 25 — Formal Semantic Dependency Analysis

**Status:** Research result / proposal, not an accepted language specification  
**Date:** 2026-11-16  
**Scope:** Formal foundations and an architectural proposal for deriving safe semantic dependency information from LLMLang programs.

## 1. Executive summary

Scenarios 20–24 explored discovering dependencies through static candidates, runtime observations, counterfactual experiments, factorial interaction analysis, and adaptive experiment scheduling. Those techniques can reveal behavior that an analyzer did not model, but they do not provide a proof that an unobserved dependency does not exist.

This scenario investigates a more fundamental direction: derive dependencies from the formal semantics of the program and prove properties of those dependencies.

The central proposal is to make **formal semantic dependency analysis the primary source of dependency information**, while retaining experimental discovery as a secondary evidence channel for opaque, external, or not-yet-modeled behavior.

The most important distinction is:

- A **sound may-depend graph** is a conservative over-approximation: every semantic dependency represented by the formal model must be included. Extra edges are allowed.
- A **proven independence fact** establishes that changing a particular input cannot change a specified observable behavior under explicitly stated assumptions.
- A **proven influence fact** establishes that at least one valid pair of executions differs observably when the selected input is changed.
- An observed runtime difference is evidence about tested executions, not a universal proof.

The graph used for safe impact analysis should prefer false positives over false negatives. An edge may cause unnecessary re-verification; a missing edge may cause stale evidence to be reused.

This document is research, not a normative change to LLMLang-CONCEPT.md or either RFC.

## 2. Research questions

1. Can dependencies be defined directly over LLMLang's formal semantics rather than inferred only from syntax or observed runs?
2. Can the analyzer prove that an input may influence an observable result, or prove that it cannot?
3. How should data dependencies, control dependencies, state, effects, exceptions, termination, concurrency, and dynamic dispatch be represented?
4. What exactly does it mean for a dependency graph to be sound or complete?
5. Which language restrictions and semantic declarations make useful proofs tractable?
6. How should proven dependencies feed impact analysis, proof invalidation, and selective recomputation?
7. Where should the system fall back to UNKNOWN or experimental evidence?

## 3. Dependency is not one relation

The word dependency is overloaded. LLMLang should not collapse these relations into one undifferentiated edge type.

### 3.1 Syntactic/read dependency

A component reads a value produced by another component, or a variable occurs in an expression.

This is cheap to compute, but it does not prove that the value can affect observable behavior. For example:

```
y = x * 0
return y
```

The expression reads x, but for mathematical integers the returned value is independent of x. For machine integers, overflow and trap semantics must be considered before making that claim.

### 3.2 Data-flow dependency

A value may flow from a definition to a use. SSA, def-use chains, alias analysis, memory SSA, and interprocedural summaries are useful mechanisms for representing this relation.

Data-flow edges are necessary for many dependency analyses, but are not sufficient: a branch condition can affect which observable effects occur even when it does not contribute to the returned value.

### 3.3 Control dependency

A value may affect whether an operation executes, which branch is selected, loop iteration count, or the order of operations.

Control influence is observable when the observation model includes the resulting return, error, state, external effect, ordering, or termination behavior. Whether timing and resource use are observable must be explicitly specified.

### 3.4 Semantic may-dependency

Input factor p may semantically influence observation O if there exist two valid executions that differ only in p (and in explicitly permitted nondeterministic choices) and produce distinguishable observations.

For deterministic semantics under a fixed context:

[
MayDep(P,p,O) iff
exists x,x'.;
x equiv_{
eg p} x'
land Obs(P,x) 
e Obs(P,x')
]

This is an existential statement. A single valid counterexample establishes influence for the modeled semantics and observation boundary.

### 3.5 Semantic independence / noninterference

Input p is independent of O if every pair of valid inputs equal in all dimensions except p produces the same observation:

[
Independent(P,p,O) iff
orall x,x'.;
x equiv_{
eg p} x'
Rightarrow Obs(P,x)=Obs(P,x')
]

This is a universal relational property over pairs of executions. It is much stronger than failing to find a counterexample in tests or observing no difference in a finite experiment.

For nondeterministic programs, the definition must compare sets or distributions of possible observations, or use a specified coupling relation. Comparing only one arbitrary run from each side is unsound.

### 3.6 Proof dependency

A proof artifact depends on the exact assumptions, definitions, contracts, implementations, lemmas, verifier, configuration, and semantic model used to establish it.

This is not identical to runtime semantic dependency. A proof may syntactically use a lemma that is logically redundant; conversely, a proof may depend on an assumption that is not an input to the executable program.

Proof dependency must remain separately recorded for verification reuse and invalidation.

### 3.7 Provenance and observed dependence

Provenance says where an assertion came from. Runtime observations say what happened in selected executions. Neither is, by itself, a semantic dependency proof.

Keep at least these relations distinct:

| Relation | Meaning | Suitable for safe impact analysis? |
|---|---|---|
| Syntactic/read | A value is referenced | Useful conservative input; not a semantic proof |
| Data/control flow | A value or condition can flow through program structure | Useful conservative input if analysis is sound |
| Semantic may-depend | A valid pair of executions can differ observably | Yes; establishes influence |
| Proven independence | No valid pair can differ observably under assumptions | Yes; permits pruning within proof scope |
| Observed influence | Difference observed in selected executions | Evidence; not universal |
| Proof dependency | Exact inputs used by a proof | Yes, for proof artifact validity |
| Provenance | Origin and history of an assertion | Audit/traceability, not dependency by itself |

## 4. Formal foundation: semantics first, graph second

A graph should be derived from a semantic model, not treated as the definition of program behavior.

Let:

- P be a pinned program semantic value;
- C be a pinned execution context: environment, binding snapshot, initial state, and declared external assumptions;
- X be the typed input space;
- O be an observation function defined by the relevant contract.

The semantic model can be expressed as a trace semantics:

[
llbracket P rbracket_C(x) subseteq Trace
]

The set notation allows nondeterminism. An observation function maps traces to contract-visible observations:

[
Obs_C : Trace ightarrow Observation
]

The observation model must explicitly decide which dimensions matter:

- returned values;
- declared errors and exceptional outcomes;
- state changes at the observable boundary;
- external effects and their payloads;
- effect ordering and concurrency-visible histories;
- termination versus divergence;
- resource bounds, timing, and other side channels, if part of the contract.

A dependency claim without a pinned observation model is underspecified. A program can be independent with respect to its return value and dependent with respect to its emitted events, exceptions, termination, or timing.

For deterministic programs, the observation is a single value. For nondeterministic programs, one conservative independence definition is equality of the sets of possible observations for all paired inputs:

[
orall x,x'.;
x equiv_{
eg p} x'
Rightarrow
{Obs(t)mid tinllbracket Prbracket_C(x)}
=
{Obs(t')mid t'inllbracket Prbracket_C(x')}
]

This set equality may be stronger or weaker than the desired property for a particular application; probabilistic programs may require distributional equivalence instead. LLMLang must select the semantics explicitly rather than silently assuming determinism.

## 5. How formal analysis can establish dependency facts

No single technique solves every case. A layered analyzer is more realistic.

### 5.1 Structural semantic analysis

Lower the program into a typed, canonical semantic IR. Candidate mechanisms include:

- SSA and explicit def-use chains;
- control-flow and control-dependence graphs;
- memory SSA and alias/effect summaries;
- explicit call, return, parameter, and result edges;
- explicit state transitions and effect operations;
- explicit dispatch/binding targets.

This creates a conservative structural dependency model. It is a foundation, not the final semantic truth.

Interprocedural analysis must preserve calling context. A callee's effects and dependencies must be related to actual arguments, returned values, state regions, and effect capabilities. A context-insensitive summary may be safe but unnecessarily broad; an incorrectly context-sensitive summary can omit dependencies.

### 5.2 Abstract interpretation

Abstract interpretation can derive sound approximations of semantic behavior from a formal concrete semantics.

For dependency analysis, an abstract domain can track which input dimensions may influence each value, state region, control decision, or observable effect. Transfer functions propagate and join dependency information.

A sound abstraction should satisfy a formally stated simulation/over-approximation condition: every concrete behavior relevant to the property must be represented by the abstract result.

The analyzer may report extra dependencies because of joins, widening, alias uncertainty, or abstraction loss. That is acceptable for safe impact analysis.

Patrick Cousot's *Abstract Semantic Dependency* is especially relevant: it defines value dependency from trace semantics and derives a sound approximate dependency algorithm using abstract interpretation. It also connects dependency abstractions with information flow, slicing, noninterference, and taint analysis.

### 5.3 Relational verification / noninterference

To prove independence of p, compare two executions of the same program:

- left execution receives x;
- right execution receives x';
- all inputs except p are related/equal;
- initial states and external contexts satisfy an explicit relation;
- final observations must be equivalent.

This is a relational verification problem, often represented by a product program or a relational Hoare judgment.

A product program executes two renamed copies in a synchronized or otherwise justified relation. Standard deductive verification can then prove a relational postcondition. This is useful because noninterference and dependency are properties of pairs of executions, not of one trace.

A proof of independence can be discharged by:
- a dependency-aware type/effect system;
- a relational program logic;
- product-program construction plus ordinary verification;
- SMT-backed symbolic reasoning for a supported fragment;
- a combination of these techniques.

A failed proof is not proof of dependence. It means UNKNOWN unless a valid counterexample is produced.

### 5.4 Proving positive influence

Positive influence is existential. A solver may produce a witness pair (x, x') satisfying:

1. all non-target inputs are equal under the declared relation;
2. both executions satisfy input and environment assumptions;
3. observations differ.

The witness is a formal counterexample to independence and a proof of possible influence within the model.

If no witness is found within a bounded search, the result is not independence. It is UNKNOWN or BOUNDED_NO_WITNESS.

### 5.5 Program slicing

Program dependence graphs and system dependence graphs are useful for computing conservative slices and interprocedural impact closure. However, a graph's usefulness depends on the language features and representation it supports.

Research has documented incompleteness in dependence-graph slicing for object-oriented programs, including cases involving partial object definitions. This is a direct warning against treating a conventional PDG as a universally complete semantic dependency oracle.

LLMLang should define its own IR semantics and prove the soundness of its analysis over that IR. Existing graph algorithms can be implementation techniques, not an imported correctness guarantee.

### 5.6 Effects and state

Dependencies must include more than scalar values.

A function can influence another observable result through:
- mutation of shared state;
- reads from state mutated by another component;
- emitted events;
- I/O, network, database, clock, random source, or filesystem effects;
- exceptions and failure paths;
- locks, synchronization, scheduling, and concurrent histories.

An effect system can make these interactions explicit and help the analyzer construct conservative summaries. Effects should identify both effect kinds and the state/capability regions they may access.

A declared effect set is only useful as a proof boundary if the implementation is verified to obey it. An unchecked foreign function cannot be assumed pure because its signature says so.

## 6. Soundness, completeness, and undecidability

These terms must be used precisely.

### 6.1 Sound over-approximation

For impact analysis, the key safety obligation is:

> If the formal semantics permits component A to influence observable component B, the conservative dependency analysis must include a path or dependency relation from A to B.

This permits false positives but forbids false negatives within the analyzed semantic model.

The obligation is conditional on:
- correctness of the language semantics;
- correctness of the IR lowering;
- soundness of alias/effect/call resolution;
- explicit modeling of external and nondeterministic behavior;
- correctness of the analyzer implementation.

### 6.2 Exactness is generally not computable

For unrestricted programs, deciding whether an arbitrary input can ever affect an arbitrary output is undecidable in general. A program can encode termination or halting questions into whether an output changes.

Therefore LLMLang must not promise an always-exact dependency graph for arbitrary programs.

The practical options are:
1. compute a conservative may-depend graph;
2. prove independence for selected pairs when the verifier can discharge the relational obligation;
3. produce concrete influence witnesses when found;
4. return UNKNOWN when neither result can be established;
5. restrict the language or a verification fragment to make stronger automation possible.

### 6.3 Do not equate three different guarantees

- **Analyzer soundness:** no modeled semantic dependency is omitted from the may-depend result.
- **Analyzer precision:** the result contains few unnecessary edges.
- **Completeness of proof automation:** the analyzer can prove every true dependency or independence fact in the target class.

Soundness is essential for safe impact analysis. High precision is desirable. Complete automation for unrestricted programs is not a realistic requirement.

## 7. Proposed dependency evidence model

Do not store a single mutable status on a graph edge. Store immutable, scoped evidence records.

Suggested evidence kinds:

| Evidence kind | Meaning |
|---|---|
| MAY_DEPEND | Conservative analysis includes a possible dependency |
| PROVEN_INFLUENCE | A valid relational witness demonstrates an observable difference |
| PROVEN_INDEPENDENCE | A relational proof establishes observational noninterference |
| OBSERVED_INFLUENCE | A runtime experiment observed a difference |
| NO_DIFFERENCE_OBSERVED | Tested runs did not show a difference |
| UNKNOWN | Available methods could not decide |
| UNSUPPORTED | The relevant construct is outside the analyzer's verified model |

Every evidence record should pin at least:

- program semantic hash;
- relevant input/output entity or factor identifiers;
- observation-model hash;
- execution-context and binding snapshot hashes;
- initial-state relation / environment assumptions;
- semantic model and IR version;
- analyzer or verifier identity and version;
- configuration and proof obligations;
- dependency/effect closure;
- proof artifact or counterexample witness digest;
- resource bounds, if any;
- result status and limitations.

Evidence is immutable. New program, context, observation model, assumptions, verifier, or relevant dependency creates a new evidence key. Reuse requires exact compatibility, consistent with the existing verification-reuse research.

## 8. Architecture proposal

Formal Semantic Dependency Analysis should become a first-class service in the semantic/verification architecture.

```text
Typed Requirement IR
        |
        v
Formal Contract + Semantic Program IR
        |
        v
Semantic Model / Effect Model
        |
        +------------------------------+
        |                              |
        v                              v
Sound May-Dependency Analysis   Relational Proof Engine
        |                              |
        v                              v
Conservative Dependency Graph   Independence / Influence Evidence
        |                              |
        +---------------+--------------+
                        |
                        v
                 Impact Planner
                        |
          +-------------+-------------+
          |             |             |
          v             v             v
       Re-derive      Re-test       Re-prove
          |             |             |
          +-------------+-------------+
                        |
                        v
               Verification Records

Experimental Discovery (Scenarios 20–24)
        |
        v
Observed evidence / counterexamples / model-gap signals
        |
        +----> refine semantic model or keep affected region UNKNOWN
```

The formal graph is the default safety mechanism. Experimental discovery does not delete a may-depend edge and does not turn NO_DIFFERENCE_OBSERVED into PROVEN_INDEPENDENCE. It can produce counterexamples, reveal missing effects, and prioritize formalization.

### 8.1 Impact-planning rule

For a changed input or semantic entity:

1. Follow sound may-depend edges to compute a conservative impact closure.
2. Exclude an edge from the closure only when a matching PROVEN_INDEPENDENCE record applies to the exact program, observation boundary, context, assumptions, and semantic model.
3. If a dependency is UNKNOWN, UNSUPPORTED, or externally opaque, keep the downstream artifact in the impact closure.
4. Re-derive contracts/tests as appropriate, and re-run or re-prove obligations whose exact inputs changed.
5. Reuse evidence only when its full verification key remains identical.

A proven independence fact can justify pruning a particular relation. It does not justify pruning unrelated effects or proof dependencies.

### 8.2 Keep separate graphs / relations

Do not merge all edges into one untyped graph:

- **Semantic dependency graph:** sound may-depend relations between semantic inputs and observations.
- **Effect/state graph:** reads, writes, emitted effects, state regions, and capabilities.
- **Proof dependency graph:** exact logical inputs to verification artifacts.
- **Provenance/audit graph:** origin, derivation, runtime observations, approvals, and evidence history.
- **Lineage graph:** supersedes, refines, derives-from, splits, and merges.

These graphs can be connected by typed references, but each has different semantics and invalidation rules.

## 9. Language design implications for LLMLang

A language intended to support reliable dependency proofs should make hidden influence difficult to express.

Potential design directions (not accepted requirements):

1. **Explicit inputs:** business policy, tenant configuration, request context, time, randomness, and environment are explicit inputs or capabilities.
2. **Pure-by-default functions:** pure computations have no hidden state or external effects.
3. **Typed effects:** mutation, I/O, network, database, clock, random, concurrency, and other effects are declared and checked.
4. **Explicit state ownership:** mutable state is partitioned into typed regions with declared read/write access.
5. **Explicit dynamic binding:** virtual dispatch and implementation selection are resolved through pinned binding snapshots or conservative target sets.
6. **No implicit ambient globals:** global state must be represented by explicit capabilities or modeled context.
7. **Constrained foreign interfaces:** foreign code carries verified contracts/effect summaries or is marked opaque/UNKNOWN.
8. **No untracked reflection or dynamic code loading:** or else the affected semantic region is explicitly opaque.
9. **Explicit nondeterminism:** random, scheduler, and external-response choices are modeled as inputs or nondeterministic effects.
10. **Observable boundaries are contractual:** each contract defines which outputs, errors, state changes, effects, ordering, termination, and resource dimensions are observable.
11. **Loop and recursion obligations:** invariants, variants, or bounded/unknown outcomes are explicit when proofs require them.
12. **Refinement-checked lowering:** compiler and runtime transformations must preserve the semantics on which dependency proofs rely.

These restrictions have costs. LLMLang should not prohibit all dynamic behavior merely to simplify the analyzer. It should make the boundary visible and refuse to claim proofs beyond that boundary.

## 10. Compiler, runtime, and backend trust boundary

A proof over Semantic Program IR is not automatically a proof about machine execution.

The chain needs explicit obligations:

1. source/semantic representation corresponds to the accepted Requirement and Contract;
2. source-to-IR lowering preserves relevant semantics;
3. optimization passes preserve semantics or are translation-validated;
4. backend code generation preserves relevant semantics;
5. runtime and foreign interfaces satisfy declared behavior/effect contracts.

If only the IR-level analyzer is verified, the result must say **PROVEN_WITHIN_IR_MODEL**, not imply end-to-end source/runtime correctness.

This aligns with the existing LLMLang direction: LLMs can propose transformations, but an independent verification boundary must validate the exact artifacts and toolchain identities.

## 11. Worked example: caller-owned tax policy

Consider two callers using a generic tax calculation function:

- preferred-order caller supplies rate 15%;
- standard-order caller supplies rate 20%;
- a new business requirement changes only preferred-order rate to 12% for orders from a specified effective date.

The generic calculation is:

[
tax = round(amount 	imes rate)
]

The business rule belongs to the caller/context that chooses the rate. The generic function receives the rate as an explicit input.

A dependency analysis should distinguish:

- preferred-order policy → preferred caller's rate input: dependency;
- standard-order policy → standard caller's rate input: dependency;
- preferred caller's rate → its tax observation: dependency;
- standard caller's rate → its tax observation: dependency;
- preferred caller's rate → standard caller's tax observation: independent, provided the two computations have isolated state/effects and no shared observable channel;
- preferred policy → generic function's implementation: no dependency if the implementation is unchanged and its explicit contract remains valid.

The final independence claim requires more than the apparent call graph. If both callers share mutable state, a global cache, an external tax service, or an effectful rate registry, those channels must be modeled or the claim remains UNKNOWN.

This example illustrates why caller-owned business rules and explicit callee inputs make dependency proofs easier.

## 12. Relationship to Scenarios 20–24

Scenarios 20–24 remain useful, but their role changes:

- Scenario 20 discovers dependency candidates and classifies evidence.
- Scenario 21 uses counterfactual execution to detect observed influence.
- Scenario 22 uses coverage to select useful experiments.
- Scenario 23 tests multi-factor effects and interactions.
- Scenario 24 schedules experiments adaptively.

Under this proposal, these mechanisms are not the primary authority for deciding that a dependency does not exist. They are auxiliary tools for:
- finding concrete counterexamples to a claimed independence;
- discovering behavior omitted from the semantic model;
- prioritizing unknown areas;
- validating analyzer predictions;
- exploring opaque external systems.

If an experiment finds an observable influence where the formal analyzer claimed independence, this is a soundness incident: invalidate the affected analysis/evidence, preserve the counterexample, and repair the semantic model or analyzer. Do not dismiss it as a statistical anomaly without investigation.

## 13. Failure modes and conservative behavior

| Situation | Required behavior |
|---|---|
| Alias analysis cannot resolve a memory target | Include all possible targets or mark the region UNKNOWN |
| Dynamic dispatch target set is incomplete | Do not claim independence; use conservative target set / UNKNOWN |
| Foreign function lacks verified effect contract | Treat relevant state/effects as opaque |
| External service behavior is not modeled | Pin contract assumptions; otherwise UNKNOWN |
| Solver finds a valid differing pair | PROVEN_INFLUENCE with witness |
| Solver proves relational equivalence | PROVEN_INDEPENDENCE within exact scope |
| Solver times out / proof search fails | UNKNOWN, never independence |
| Bounded search finds no counterexample | BOUNDED_NO_WITNESS, not PROVEN_INDEPENDENCE |
| Observation model omits a relevant effect | No valid independence claim for that effect |
| Compiler/runtime correspondence is unproved | Limit claim to the verified IR model |
| Nondeterminism is modeled as one arbitrary run | Reject universal independence claim as unsound |

## 14. Proposed research conclusions

### Supported conclusions

1. Semantic dependency should be defined over sets of possible executions and an explicit observation model, not merely over source-level references.
2. A sound conservative may-depend graph is the right foundation for safe impact analysis.
3. Proving independence is a relational verification problem (noninterference / observational equivalence).
4. Proving positive influence can use a concrete pair of executions as a witness.
5. Data-flow, control-flow, effects, state, dispatch, exceptions, termination, and concurrency must be covered by the semantic model.
6. Proof dependencies and provenance must remain separate from runtime semantic dependencies.
7. Exact dependency analysis for unrestricted programs is not generally decidable; UNKNOWN is a necessary result.
8. Experimental discovery remains valuable as a secondary channel and a way to expose gaps in the formal model.

### Preliminary architectural recommendation

Adopt a layered design:

- a canonical typed semantic IR;
- an explicit effect/state model;
- a sound over-approximate may-dependency analyzer;
- a relational proof engine for selected independence/influence obligations;
- immutable, exactly scoped evidence records;
- an impact planner that treats UNKNOWN as potentially affected;
- experimental discovery as auxiliary evidence and model-gap detection.

### Not established by this scenario

- No final LLMLang syntax is selected.
- No particular abstract domain or solver is selected.
- No universal proof automation guarantee is claimed.
- No formal proof of an LLMLang dependency analyzer exists yet.
- No normative concept/RFC document is changed.
- No production-ready implementation is proposed.

## 15. Next research step

**Scenario 26 — Minimal Formal Semantic Core for Dependency Proofs**

Define a small language/IR fragment and its operational semantics, then implement a deliberately bounded analyzer/proof prototype. The prototype should test:

1. arithmetic/data dependencies, including algebraic cancellation;
2. control dependencies and observable effects;
3. mutable state and aliasing;
4. caller/callee parameter and return dependencies;
5. explicit effect capabilities;
6. finite-domain relational proof of independence and witness generation;
7. UNKNOWN for unsupported or incomplete semantics;
8. sound conservative fallback when alias/dispatch/effect information is incomplete.

The goal is not to prove arbitrary programs. It is to establish a small, explicit semantic kernel whose guarantees can be stated and tested.

## 16. References

1. Patrick Cousot, **Abstract Semantic Dependency**, SAS 2019. Defines semantic value dependency from trace semantics and derives sound approximate dependency analysis by abstract interpretation.  
   https://cs.nyu.edu/~pcousot/publications.www/Cousot-SAS-dependency-2019.pdf  
   https://cs.nyu.edu/~pcousot/COUSOTpapers/SAS-2019-Dependency.shtml

2. **Product Programs and Relational Program Logics**, Journal of Logical and Algebraic Methods in Programming, 2016. Explains product programs and relational reasoning for noninterference, equivalence, and other two-execution properties.  
   https://doi.org/10.1016/j.jlamp.2016.05.004

3. Gilles Barthe, Juan Manuel Crespo, César Kunz, **Relational Verification Using Product Programs**.  
   https://software.imdea.org/~ckunz/rellog/

4. Susan Horwitz, Thomas Reps, David Binkley, **Interprocedural Slicing Using Dependence Graphs**, 2004. Explains system dependence graphs and the importance of calling-context relationships for interprocedural slicing.  
   https://doi.org/10.1145/989393.989419

5. **Program Slicing of Java Programs**, Journal of Logical and Algebraic Methods in Programming, 2023. Demonstrates incompleteness cases in existing dependence-graph approaches for object-oriented programs.  
   https://doi.org/10.1016/j.jlamp.2022.100826

6. Andy Podgurski, Lori A. Clarke, **A Formal Model of Program Dependences and Its Implications for Software Testing, Debugging, and Maintenance**. Distinguishes syntactic dependence from semantic dependence.  
   https://citeseerx.ist.psu.edu/document?doi=874839c8446557e7f79b29494ffc6660d02a9eb3&repid=rep1&type=pdf

7. Alan Mycroft, Dominic Orchard, Tomas Petricek, **Effect Systems Revisited—Control-Flow Algebra and Semantics**. Relates effect analysis to control flow and semantic models of effects.  
   https://doi.org/10.1007/978-3-319-27810-0_1

8. **WhyRel: an auto-active relational verifier**, 2025. Discusses relational verification for mutable dynamically allocated state and current automation limitations.  
   https://doi.org/10.1007/s10009-025-00786-1
