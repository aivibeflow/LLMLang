# Research Scenario 17: A Typed Requirement Intermediate Representation

**Status:** Research / design proposal  
**Date:** 2026-11-16  
**Scope:** A compact, provenance-preserving intermediate representation between clarified business intent and formal contracts, with finite-domain consistency checks and scenario generation.

## 1. Executive summary

Scenario 15 separated human intent, clarified requirements, business rules, formal candidates, validated contracts, and implementation proofs. Prototype 16 demonstrated one caller-scoped tax-policy change, but its formal predicates were strings. Strings are useful for display; they are not a safe semantic substrate for independent checking.

This scenario asks what the smallest useful typed Requirement IR should contain.

### Main recommendation

Use a **typed, provenance-carrying requirement graph** whose core is deliberately smaller than a general-purpose formal language:

1. **Source and decision references** preserve where a requirement came from and who resolved material ambiguity.
2. **Requirement nodes** identify owner, scope, constraint, applicability trigger, required action, temporal bound, assumptions, unresolved items, and explicitly required dimensions.
3. **Typed expression nodes** represent predicates and Boolean composition. They must not be stored as opaque predicate strings.
4. **BusinessRule nodes** retain the component that owns a business decision.
5. **Component contracts** describe the caller/callee boundary and explicit policy inputs.
6. **Analysis results** report invalid structure, missing provenance, unresolved meaning, assumptions, contradictions, underdetermination, and bounded-analysis exhaustion as distinct outcomes.
7. **Scenario generation** enumerates finite input domains and returns both satisfying cases and counterexamples.

The proposed IR is a bridge, not the final formal language. It should lower into specialized backends such as FRET/FRETISH, Alloy, TLA+, SMT, or a contract logic when the requirement needs those capabilities.

The research prototype is intentionally finite and small. It does not parse natural language, infer intent, prove source-code correctness, or establish completeness of a requirement set.

## 2. Why another representation is needed

Prototype 16 represented a formal clause with a predicate string such as `selected_rate_basis_points == 1200`. That retains an explanation and provenance, but a checker cannot safely distinguish:
- a variable from a literal;
- an integer from a string;
- equality from assignment;
- a caller-local policy from a generic calculation rule;
- a valid expression from malformed or unsupported syntax.

Parsing arbitrary strings later would simply move the ambiguity into a second language.

The IR should therefore make semantic structure explicit at creation time. Human-readable text remains attached for explanation, but machine checks operate on typed nodes.

## 3. What existing approaches contribute

### 3.1 EARS: constrain the shape of requirement statements

EARS provides a small set of readable sentence patterns for ubiquitous, event-driven, state-driven, unwanted-behavior, and optional-feature requirements. Its value for LLMLang is not that its prose becomes the semantic core; it is that it encourages explicit separation of preconditions, triggers, system identity, and response. The original EARS work also identifies ambiguity, vagueness, complexity, omission, duplication, wordiness, inappropriate implementation, and untestability as recurring requirements problems.

**Adopt:** structured capture of scope, condition, trigger, and response.

**Do not adopt as the IR:** unconstrained or semi-structured English strings as the only machine representation.

### 3.2 NASA FRET / FRETISH: readable requirements with defined semantics

NASA's FRET accepts hierarchical requirements in structured natural language, gives them formal semantics, and provides natural-language, mathematical, diagrammatic, and simulation views. It can translate FRETISH requirements into temporal logic and connect them to analysis tools. FRET's approach demonstrates the value of a round trip: the stakeholder should inspect not only the original sentence but also the exact semantics attributed to it.

**Adopt:** explicit semantic interpretation, multiple explanatory views, simulation, and downstream formalization.

**Do not duplicate:** FRET's temporal logic machinery in the first Requirement IR prototype. LLMLang should be able to export suitable requirements to FRET-like tools.

### 3.3 Alloy and TLA+: analysis backends, not business-facing IR

Alloy is a relational modeling language whose analyzer explores structures and finds counterexamples within a selected scope. Alloy 6 adds native mutable state and temporal operators. TLA+ provides a formal framework for describing state-transition systems and temporal properties.

These tools are useful after the requirement's vocabulary, scope, and meaning are explicit. They are not a reason to force every stakeholder-facing requirement into one universal formal notation.

**Adopt:** a backend boundary. Keep the IR typed and backend-neutral; translate only the subset a backend can represent, and report unsupported constructs rather than silently weakening them.

### 3.4 Property-based testing: executable examples and counterexamples

Property-based testing generates inputs to check executable properties and can shrink failing examples. It is useful for exploring a requirement's finite or sampled input space and producing reviewable counterexamples.

**Adopt:** scenario generation from explicit domains and predicates, with counterexample preservation.

**Do not claim:** generated tests establish completeness or prove an unbounded property.

### 3.5 Requirements traceability

A formal predicate must remain traceable to its source statement and to any clarification decision that materially selected its interpretation. Traceability is not just a link from a requirement ID to a test ID. It is clause-level provenance through the transformations that produce a contract.

**Adopt:** explicit source and decision references on requirement nodes, with dangling-reference checks.

## 4. Proposed conceptual model

The IR separates five semantic concerns.

### 4.1 Evidence

- **IntentSource** — immutable source statement or document excerpt.
- **ClarificationDecision** — a question, alternatives, selected interpretation, and decision authority.
- **EvidenceReference** — a typed link from a requirement clause to source and/or decision evidence.

A source statement is not automatically an executable requirement. A clarification decision is not a new source statement; it records how an ambiguity was resolved.

### 4.2 Requirement

A Requirement has:
- stable local identifier;
- **owner** — component, actor, or business process responsible for the rule;
- **scope** — where the rule applies (for example, a caller, tenant, jurisdiction, product, or workflow);
- **constraint** — typed Boolean expression;
- optional **trigger** — named event and optional typed condition;
- optional **action** — operation, target, and typed arguments;
- optional **temporal bound** — relation, amount, and unit;
- source and decision references;
- explicit assumptions;
- unresolved questions;
- **required dimensions** — facts the author/reviewer has explicitly said must be determined before acceptance.

The last field is important. A machine cannot infer every dimension that a human intended to specify. It can, however, check that dimensions explicitly marked as required are not left with multiple possible values.

### 4.3 Typed expressions

The initial expression algebra is intentionally small:
- Predicate(variable, operator, literal);
- Junction(and/or, terms);
- Negation(term).

Each variable has a declared type and finite domain in the prototype. Operators are type-checked. The IR does not allow arbitrary source snippets or unparsed expressions.

A later language may add arithmetic, records, option types, sets, quantified expressions, units, intervals, state predicates, and temporal logic. These should be added as typed constructors with explicit semantics, not as escape hatches containing strings.

### 4.4 Business-rule ownership and component contracts

A BusinessRule records the component that owns a business decision. A ComponentContract records whether a component is acting as caller or callee and which policy inputs it accepts.

This supports an explicit check of the Scenario 15 principle:

- caller-owned business policy remains owned by the caller;
- a generic callee accepts the selected policy as an explicit input;
- a caller-specific rate must not silently become a constant inside a reusable calculation function.

For example:

`preferred_order` owns the decision to select 1200 basis points for a qualifying order.

`calculate_tax` accepts `rate_basis_points` and computes tax using its declared arithmetic and rounding contract.

The IR does not forbid a shared policy service. It requires that ownership and delegation be explicit rather than accidentally inferred from implementation placement.

### 4.5 Analysis result

Analysis is not a Boolean pass/fail. The prototype distinguishes:
- **INVALID** — malformed structure, unknown variables, or type errors;
- **NEEDS_REVIEW** — unresolved questions, assumptions, dangling provenance, contradiction, or underdetermination;
- **FINITE_MODEL_CONSISTENT** — the modeled finite constraints have at least one satisfying assignment and no configured review issue was found;
- **UNKNOWN** — the finite state space exceeded the configured analysis bound.

These statuses must not be collapsed into one green "valid" result. In particular, finite consistency does not mean that the requirement is complete, correct, realizable in the real system, or faithful to human intent.

## 5. Consistency, contradiction, and underdetermination

### 5.1 Contradiction

For requirements in the same declared scope, the prototype enumerates the finite variable domains and checks whether at least one assignment satisfies all constraints. If none does, it reports a contradiction.

Example:
- preferred-order rate must equal 1200;
- preferred-order rate must equal 1500.

If the declared domain contains both values but no value can satisfy both clauses, the scope is inconsistent.

This is a finite-domain check. It is not a general theorem prover.

### 5.2 Underdetermination

A requirement may be consistent but still leave an important decision open.

Example:
- the caller is `preferred_order`;
- the reviewer marked `rate_basis_points` as a required dimension;
- the finite model still permits 1200, 1500, and 2000.

The IR reports that dimension as underdetermined.

Crucially, the checker only performs this check for dimensions explicitly declared as required. It must not pretend to know all missing business context.

### 5.3 Analysis bounds

Exhaustive enumeration grows as the product of domain sizes. The prototype has a configurable maximum assignment count. If the bound is exceeded, it returns UNKNOWN, never a success status.

A production implementation should route larger problems to an appropriate solver/backend, preserve exact input identities, and record solver/version/configuration in the analysis evidence.

## 6. Scenario and counterexample generation

Given finite variable domains and typed constraints, the prototype emits assignments labeled:
- satisfying;
- violating, with the IDs of violated requirements.

This is useful for:
- reviewing a proposed formalization with a stakeholder;
- generating initial example-based tests;
- finding boundary combinations;
- demonstrating why two candidate interpretations differ;
- creating regression scenarios when a requirement changes.

The current prototype enumerates the full finite Cartesian product. It does not yet minimize cases, generate pairwise combinations, infer useful domains from prose, or execute the scenarios against implementation code.

A future test-generation layer should support:
1. positive examples;
2. negative examples;
3. boundary values;
4. temporal transitions;
5. pairwise and property-based sampling;
6. minimal counterexample reduction;
7. traceability from each generated test to the exact requirement and IR snapshot.

## 7. Prototype 17

The prototype is implemented in:
- `PROTOTYPES/DEPENDENCY-GRAPH-01/src/requirement_ir.py`
- `PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_requirement_ir.py`
- `PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-17-RESULTS.md`

It provides:
- typed variables and finite domains;
- typed predicates and Boolean composition;
- event triggers, actions, and temporal-bound records;
- source/decision provenance references;
- assumptions, unresolved items, and required dimensions;
- type and dangling-reference validation;
- finite-domain contradiction detection;
- explicitly requested underdetermination checks;
- satisfying and violating scenario enumeration;
- an explicit caller-policy / callee-input boundary check;
- an UNKNOWN result when the analysis bound is exceeded.

The test suite contains ten focused tests. Their source has been added to the repository. Execution status is reported separately in Prototype 17 Results; source presence must not be confused with a successful test run.

## 8. What the prototype demonstrates

1. A typed predicate is more inspectable and checkable than an opaque predicate string.
2. Contradictory finite constraints can be found without involving an LLM.
3. A requirement can explicitly declare which business dimensions must be resolved.
4. Missing provenance and unresolved questions remain visible instead of disappearing during formalization.
5. Scenario generation can produce both satisfying assignments and counterexamples from the same IR.
6. Caller policy ownership and callee policy inputs can be checked as a structural boundary.
7. Exhausting the analysis budget produces UNKNOWN, not success.

## 9. What remains unsolved

- Natural-language extraction and semantic equivalence are not implemented.
- The prototype does not establish that a source statement contains the whole business intent.
- A finite domain may omit real values or important states.
- Contradiction checking is limited to explicit finite constraints in the same scope.
- Underdetermination is checked only for dimensions explicitly marked required.
- Temporal records are data structures only; no temporal logic semantics are evaluated.
- Trigger and action records are not yet executed by a state-transition engine.
- The prototype does not check business authority or access control.
- There is no arithmetic expression tree, units system, interval algebra, quantification, or solver integration.
- It does not derive a proof that implementation code satisfies the requirement.
- It does not establish completeness of traceability or test coverage for arbitrary systems.

## 10. Recommended next step

The next useful experiment is **Scenario 18 — Requirement Evolution and Semantic Impact**:

1. represent a requirement revision as a new immutable IR state;
2. compute which formal clauses, contracts, generated scenarios, and verification records depend on it;
3. distinguish direct semantic impact from merely contextual/provenance changes;
4. prove that changing one caller's business rule does not invalidate unrelated caller rules or the generic callee contract;
5. preserve old IR snapshots and analysis evidence;
6. test split, merge, supersession, and concurrent edits to requirements.

This follows naturally from the dependency-graph experiments and will test whether Requirement IR fits the existing content-addressed model without reintroducing a global mutable requirement identity.

## 11. References

- Mavin et al., *Easy Approach to Requirements Syntax (EARS)*, IEEE Requirements Engineering Conference, 2009. [Paper copy](https://ccy05327.github.io/SDD/08-PDF/Easy%20Approach%20to%20Requirements%20Syntax%20%28EARS%29.pdf).
- NASA, [Formal Requirements Elicitation Tool (FRET)](https://software.nasa.gov/software/ARC-18066-1) and [FRET source repository](https://github.com/NASA-SW-VnV/fret).
- Giannakopoulou et al., [Formal Requirements Elicitation with FRET](https://ntrs.nasa.gov/api/citations/20200001989/downloads/20200001989.pdf).
- NASA, [FRET Tutorial: Requirements Elicitation, Formalization, and Analysis](https://ntrs.nasa.gov/api/citations/20260003596).
- Alloy Tools, [Alloy 6](https://alloytools.org/alloy6.html) and [About Alloy](https://alloytools.org/about.html).
- Hypothesis, [Strategies reference](https://hypothesis.readthedocs.io/en/latest/reference/strategies.html) and [Shrinking strategies](https://github.com/HypothesisWorks/hypothesis/blob/master/guides/strategies-that-shrink.rst).
- *Generating test data from SOFL specifications*, Journal of Systems and Software, 1999. [Abstract](https://www.sciencedirect.com/science/article/pii/S0164121299000667).
