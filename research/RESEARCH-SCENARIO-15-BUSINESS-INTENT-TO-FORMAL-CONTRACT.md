# Research Scenario 15: From Business Intent to Formal Behavioral Contracts

**Status:** Research / design proposal  
**Date:** 2026-11-16  
**Scope:** Transforming human business intent into reviewable, traceable formal contract candidates without requiring stakeholders to write mathematical specifications.

## 1. Executive summary

LLMLang should not ask a business stakeholder to write predicates, temporal logic, or proof obligations. It should let the stakeholder express intent naturally, then progressively transform that intent into structured and reviewable representations.

The central distinction is:

> A proof can establish that an implementation satisfies a formal contract. It cannot establish that the contract faithfully represents the stakeholder's intent.

This creates two independent correctness questions:

1. **Intent/formalization correctness:** Does the accepted contract express the intended business rule in the relevant context?
2. **Implementation correctness:** Does the implementation satisfy that accepted contract?

The second question can be addressed with formal verification. The first requires elicitation, context, provenance, examples, counterexamples, ambiguity management, and an explicit validation/acceptance process.

### Main recommendations

1. Preserve the original human statement as immutable source evidence.
2. Separate human intent, clarified requirement, business rule, formal candidate, validated contract, and implementation proof.
3. Let the LLM propose interpretations and formal candidates, never silently promote them to accepted requirements.
4. Derive rules in the context where behavior is required. A caller's business policy must not be silently embedded in a generic callee.
5. Represent policy inputs explicitly at component boundaries when callers are allowed to choose them.
6. Review formal candidates through readable explanations, examples, counterexamples, boundary cases, and assumptions.
7. Require explicit human confirmation for business-semantic choices that cannot be inferred safely.
8. Check both under-specification and over-specification, including vacuity, contradiction, inconsistency, and unrealizability.
9. Preserve clause-level provenance from each formal predicate back to the exact source and decision that justify it.
10. Treat automated tests and simulations as useful validation evidence, not as proof that the requirement set is complete.

These are research recommendations, not accepted LLMLang normative rules.

## 2. Research question and boundaries

The question is not simply: "Can an LLM translate prose into logic?"

The useful question is:

**How can LLMLang help a person move from an incomplete, contextual business statement to a formal contract whose meaning the person can inspect and confirm, while preserving enough evidence to audit every transformation?**

The system must handle:
- incomplete and ambiguous statements;
- business vocabulary whose meaning depends on domain context;
- rules that apply only to a particular caller, tenant, product, jurisdiction, or time period;
- rules that evolve independently in different contexts;
- rules that depend on other rules or external policy sources;
- multiple plausible formal interpretations;
- examples that clarify intent but do not necessarily define the whole behavior;
- requirements that are inconsistent, impossible, too weak, or too strong;
- changes to the caller's business rule that may require a changed callee contract or implementation.

Out of scope:
- claiming that natural-language processing can recover intent that was never expressed;
- treating LLM confidence as evidence of semantic correctness;
- automatically accepting generated business policy;
- assuming every business requirement can or should be fully formalized;
- claiming that finite tests prove an unbounded property.

## 3. The essential semantic layers

The following layers must remain distinct. They may be represented as linked graph nodes, but they are not interchangeable statuses of one text document.

### 3.1 Human Intent

The original statement, conversation, document excerpt, or other stakeholder-provided source.

Examples:
- "For preferred customers, use the reduced rate."
- "The invoice should be calculated using the rules applicable when the order was placed."
- "Do not charge tax on exempt items."

Human Intent is evidence of what was said, not yet a complete executable requirement.

It should retain:
- exact source content or immutable source reference;
- speaker/authority identity or role, where available and appropriate;
- source location and timestamp;
- conversation/document context;
- language and relevant domain vocabulary;
- links to the clarification dialogue that follows.

Do not rewrite the original source in place. A normalized paraphrase is a derived artifact.

### 3.2 Clarified Requirement

A requirement is the current, explicit interpretation of the intent after resolving material ambiguity.

It should identify:
- subject/component;
- trigger and applicability conditions;
- required or forbidden outcome;
- relevant business entities and terms;
- time semantics and effective period;
- jurisdiction/tenant/product scope where applicable;
- exceptions and priority rules;
- unresolved questions and assumptions.

A clarification is not merely an LLM-generated rewrite. A material interpretation must be accepted by an authorized stakeholder or grounded in an authoritative source.

### 3.3 Business Rule

A Business Rule is a reusable domain decision or constraint with an explicit scope and authority.

Examples:
- preferred customers receive a 15% tax rate in a particular jurisdiction and period;
- tax exemption applies to a specified product category when a valid exemption certificate is present;
- the tax policy is selected according to the order's legally relevant date.

A Business Rule should not be identified solely by the function that happens to implement it. Its identity and scope derive from its domain meaning and governance context.

Potential fields:
- applicability predicate;
- decision or constraint;
- authority/source;
- scope (global, jurisdiction, tenant, product, caller, etc.);
- effective interval;
- precedence/override rules;
- required facts and their sources;
- exceptions;
- owner/approver;
- lifecycle and supersession links.

A rule can be referenced by multiple callers. Different callers can also have different rules even if they call the same function.

### 3.4 Formal Candidate

A Formal Candidate is a machine-processable interpretation proposed from clarified requirements and business rules.

It may contain:
- typed predicates;
- preconditions and postconditions;
- state invariants;
- effects and failure conditions;
- temporal properties;
- explicit assumptions;
- data-domain constraints;
- candidate examples and counterexamples;
- references to source clauses and clarification decisions.

A candidate is not an accepted contract merely because it parses or verifies.

The system should preserve alternative candidates when the source permits materially different interpretations. It must not silently choose one merely because it is easier to formalize.

### 3.5 Validated Contract

A Validated Contract is a formal contract candidate whose business meaning has been reviewed and accepted by the relevant authority, and whose formal structure has passed the required consistency and realizability checks for its declared scope.

Validation has multiple dimensions:
- semantic review by an authorized human;
- traceability and provenance completeness;
- well-formedness and type checking;
- consistency and satisfiability checks;
- realizability/feasibility analysis where applicable;
- review of assumptions and environment boundaries;
- appropriate scenario and boundary-case review.

"Validated" does not mean universally true. It means accepted for a defined scope, baseline, and set of assumptions.

### 3.6 Implementation Proof

Implementation Proof is evidence that a particular implementation satisfies a particular accepted contract under exact assumptions and tool identities.

It must bind to:
- contract hash;
- implementation hash;
- relevant dependency and environment roots;
- abstraction/model hashes;
- proof obligations;
- verifier/checker identity and configuration;
- assumptions;
- proof artifact or independently checkable certificate.

A proof never retroactively validates the business meaning of the contract.

## 4. Proposed transformation pipeline

The proposed workflow is:

`Human Intent ightarrow Clarification ightarrow Business Rule ightarrow Formal Candidate ightarrow Human Validation ightarrow Validated Contract ightarrow Implementation Proof`

This is not necessarily a one-way waterfall. A reviewer may return to clarification or business-rule modeling when a counterexample reveals missing meaning.

### Step 1 — Capture intent

Store the original statement without loss. Identify candidate domain terms, actors, actions, conditions, quantities, time references, and referenced systems.

LLM output at this stage is extraction metadata, not a new requirement.

### Step 2 — Build context

Retrieve only context that can legitimately clarify the statement:
- caller and callee contracts;
- enclosing workflow/business process;
- domain glossary and entity definitions;
- applicable policies and their authority;
- existing decisions and accepted requirements;
- relevant historical versions.

Context must be versioned/pinned. A future change in a glossary or policy must not silently rewrite an earlier accepted interpretation.

### Step 3 — Detect ambiguity and missing dimensions

Classify uncertainty rather than hiding it. Useful classes include:
- lexical: a term has multiple meanings;
- referential: it is unclear which entity a phrase denotes;
- scope: it is unclear where/when the rule applies;
- temporal: event time, processing time, or effective time is unclear;
- quantitative: rounding, units, thresholds, precision, or inclusive boundaries are unclear;
- modal: "must", "may", "should", "unless", and "only" are not equivalent;
- exception: an omitted exception could change outcomes;
- authority: the source or person may not be authorized to define the rule;
- dependency: the rule depends on another policy or external fact.

For every material ambiguity, present the smallest useful clarification question. If there are multiple defensible interpretations, show them as alternatives with their behavioral consequences.

### Step 4 — Produce a structured requirement

Convert the clarified meaning into a readable structure. A lightweight template can capture:
- **Subject:** which system/component/person is constrained?
- **Scope:** in which mode, jurisdiction, tenant, product, or lifecycle stage?
- **Trigger:** what event or condition activates the rule?
- **Condition:** what must already hold?
- **Response:** what must or must not happen?
- **Timing:** when and for how long?
- **Exceptions:** what changes or cancels the obligation?
- **Evidence:** which source/decision supports each clause?

This resembles the motivation behind EARS and FRETISH: structured natural language can reduce ambiguity without requiring stakeholders to author formal logic.

### Step 5 — Separate caller policy from callee capability

This is particularly important for LLMLang.

Suppose a caller invokes `calculate_tax`.

The caller's business rule may be:
- preferred customers in jurisdiction J receive rate 15%;
- the rate is determined using the order date;
- a valid exemption overrides the standard rate.

The callee's reusable computational responsibility may be:
- calculate tax from taxable basis, an explicitly supplied applicable rate/policy, currency, and rounding rule;
- return a defined result or a defined error;
- perform no hidden jurisdiction/customer policy selection.

The caller contract expresses why and when a policy is selected. The callee contract expresses what calculation means given the supplied inputs.

For example:

`caller policy: selected_rate = policy_for(customer, jurisdiction, order_date)`

`callee contract: tax = round(taxable_basis * selected_rate, currency_rounding)`

This is illustrative, not proposed final LLMLang syntax.

If the tax policy is intentionally owned by a shared domain service, that ownership must be explicit. It should not emerge accidentally because one implementation of `calculate_tax` happens to contain a 15% constant.

### Step 6 — Generate formal candidates

The LLM can propose:
- a candidate domain model;
- candidate predicates;
- preconditions and postconditions;
- state transitions;
- failure/effect constraints;
- temporal constraints;
- proof obligations;
- candidate tests and examples.

Every generated clause must link to one or more source/decision references. Clauses without adequate support must be marked as assumptions or unresolved proposals.

Do not collapse distinct business rules into one predicate merely to simplify the proof.

### Step 7 — Explain the candidate back to the stakeholder

A formal candidate must have a human-readable interpretation. Show:
- what it guarantees;
- what it does not guarantee;
- when it applies;
- which inputs it treats as authoritative;
- what happens at boundaries;
- which assumptions it makes;
- what behavior remains unconstrained.

The reviewer should be able to challenge the interpretation without understanding the underlying logic notation.

### Step 8 — Validate with examples and counterexamples

Generate concrete scenarios from the candidate:
- ordinary positive cases;
- negative cases;
- boundary values;
- conflicting conditions;
- missing or stale data;
- exceptional flows;
- temporal transitions;
- alternative interpretations.

Ask the stakeholder to confirm or correct the expected outcome, not merely whether the generated prose "looks right".

Examples are a review instrument. Unless the requirement explicitly defines a finite input domain, a set of examples does not exhaust the behavior space.

### Step 9 — Run formal quality checks

Before a candidate can become a validated contract, check as appropriate:
- syntax and type correctness;
- satisfiability/consistency;
- contradictory assumptions;
- vacuous satisfaction;
- missing preconditions;
- over-permissive postconditions;
- unreachable or impossible states;
- realizability;
- conflicting requirements;
- unbound variables and undefined terms;
- missing effect/failure/termination behavior;
- ungrounded assumptions;
- missing traceability.

A successful proof of implementation conformance is not a substitute for these checks.

### Step 10 — Human acceptance and immutable baseline

An authorized person accepts a specific candidate digest, not an editable text label.

The accepted record should bind:
- exact candidate and source digests;
- clarification/decision digests;
- business-rule versions;
- applicable scope;
- assumptions;
- validation results;
- approving authority;
- acceptance timestamp.

A later correction creates a new candidate/contract revision. It must not mutate the meaning of the previously accepted baseline.

### Step 11 — Derive implementation obligations

Only after contract acceptance should LLMLang derive implementation obligations and connect them to code, tests, and proofs.

A changed caller rule may cause:
- a changed caller contract;
- a changed explicit policy input;
- a changed callee contract if the required capability itself changes;
- a new implementation binding if a different implementation is required;
- no callee change at all if the existing generic capability already supports the new policy input.

Impact analysis should follow typed semantic dependencies, not textual name similarity alone.

## 5. Caller-driven evolution: worked example

### Initial state

Two callers invoke the same calculation function:

- `standard_order` selects a 20% rate;
- `preferred_order` selects a 15% rate.

Both call the same generic `calculate_tax` capability.

The caller-specific rules are not interchangeable. The shared calculation operation may still be reusable.

### Business change

The business changes the preferred-customer rule from 15% to 12%, effective for orders placed on or after a specified date.

Correct evolution:

1. The business intent is recorded in the preferred-order context.
2. The applicable preferred-customer rule is clarified, including the effective-date semantics.
3. A new immutable Business Rule state is created.
4. The preferred caller's contract is updated to select 12% under the new applicability condition.
5. The caller now supplies the new rate/policy to `calculate_tax`.
6. If the callee's existing contract already accepts arbitrary valid rates and defines rounding correctly, its contract and implementation need not change.
7. The standard caller remains on its existing 20% rule.
8. A new snapshot selects the updated preferred caller and unchanged standard caller.

Incorrect evolution:

- changing a hidden constant inside `calculate_tax` from 15% to 12%;
- changing every caller because they share a function;
- treating the function hash as the business-rule identity;
- assuming that a successful proof of the new implementation establishes that 12% was the intended policy.

### When the callee must change

The callee must change if the new requirement changes the computational capability itself, for example:
- rate is no longer a scalar but a progressive schedule;
- rounding must occur per line rather than on the aggregate;
- the operation must account for multiple tax jurisdictions;
- a new failure or side-effect guarantee is required.

This is a semantic dependency from the caller's requirement to the callee's capability contract, not merely a call-graph dependency.

## 6. Provenance and traceability model

A formal predicate should not be an orphaned formula.

Proposed clause-level provenance:

`FormalClause ightarrow ClarifiedRequirement ightarrow IntentSource`

Additional links may include:
- `derived_from`: candidate clause was generated from a source clause;
- `supported_by`: decision, policy, example, or authoritative document supports it;
- `assumes`: clause depends on an explicit assumption;
- `confirmed_by`: authorized human accepted the interpretation;
- `supersedes`: a later requirement or rule replaces an earlier one;
- `applies_in`: scope/context in which it is effective;
- `verified_by`: evidence that an implementation satisfies the accepted clause.

These relations have different meanings and must not be collapsed into a generic "linked to" edge.

A single formal clause may be supported by multiple sources. A single source requirement may produce multiple formal clauses. A business rule may be used by many callers. Therefore traceability is a many-to-many typed graph.

### Provenance completeness

A candidate should expose at least:
- clauses with direct source support;
- clauses derived from accepted decisions;
- clauses based on assumptions;
- clauses inferred by the LLM without explicit confirmation;
- source material not yet represented in the candidate;
- source material that conflicts with the candidate.

A useful status vocabulary could distinguish:
- `GROUNDED`: traceable to an explicit source/decision;
- `ASSUMED`: relies on a declared assumption;
- `INFERRED`: proposed interpretation not yet confirmed;
- `UNRESOLVED`: multiple meanings remain;
- `CONFLICTED`: evidence sources disagree;
- `ACCEPTED`: authorized human acceptance recorded.

These are research labels, not current LLMLang status definitions.

## 7. Preventing weak, strong, and vacuous contracts

A formally valid contract can still be a poor representation of intent.

### Under-specification

The contract permits behavior the business did not intend to allow.

Example: "calculate tax" is formalized only as "return a non-negative number". A function that always returns zero may satisfy it.

Potential checks:
- compare the contract against concrete alternative implementations;
- ask whether materially different outputs are still allowed;
- generate mutants or alternative behaviors that satisfy the contract;
- identify unconstrained output/state dimensions.

### Over-specification

The contract forbids behavior that the business did not intend to forbid.

Example: the requirement says "use the applicable rate", but the formalization hardcodes one rate or one ordering of internal operations.

Potential checks:
- identify predicates not directly supported by source or accepted decision;
- compare multiple implementations that should be equivalent at the observable boundary;
- ask whether implementation detail has leaked into the contract.

### Vacuity and contradiction

A contract may be satisfied because its precondition can never hold, or because assumptions are inconsistent.

Potential checks:
- satisfiability checks for assumptions and preconditions;
- reachable-state analysis;
- vacuity checks for antecedents and temporal triggers;
- realizability checks;
- explicit counterexample explanations.

Dafny's own guidance illustrates the core danger: a technically verified implementation can create false confidence if the specification does not state the intended property. Recent work on specification-strength analysis also motivates checking whether a contract permits materially different implementations, not merely whether the chosen implementation verifies.

## 8. Human confirmation policy

Not every generated detail requires the same kind of human intervention.

### Usually safe to automate as a proposal

- term extraction;
- candidate decomposition into atomic requirements;
- detection of likely ambiguity;
- candidate formal syntax;
- candidate proof obligations;
- candidate positive/negative examples;
- traceability suggestions;
- consistency diagnostics.

### Human confirmation required when it changes business meaning

- choosing among materially different interpretations;
- defining policy precedence;
- setting a rate, threshold, limit, or exception not stated in an authoritative source;
- deciding event-time versus processing-time semantics;
- defining the scope of a rule;
- deciding whether a behavior is allowed or forbidden;
- accepting a formal candidate as the business contract;
- approving a change to an accepted business rule.

### Human confirmation may be delegated only explicitly

An organization may define authoritative policy sources or delegated approvers. LLMLang should represent that authority and its scope as data/policy, not infer it from who last edited a file or from the LLM's confidence.

## 9. Role of tests, examples, and simulation

Examples are especially valuable because they allow stakeholders to validate meaning without learning formal logic.

A useful review set includes:
- canonical example;
- boundary examples;
- exception examples;
- negative examples;
- pairwise/conflicting-rule examples;
- temporal examples;
- counterexamples to plausible alternative interpretations.

Property-based testing can explore many generated inputs. Model checking can explore bounded state spaces. Interactive simulation can show the behavior implied by a temporal formula.

However:
- passing examples does not prove completeness;
- finite testing does not prove an unbounded property;
- a simulation only demonstrates the model that was encoded;
- a counterexample is evidence that a candidate or implementation has a problem, but its business interpretation still requires review.

FRET is a useful precedent because it presents requirements in natural language, formal logic, diagrams, and simulation, allowing users to inspect the semantics rather than trusting a hidden translation.

## 10. Candidate data model

The following is a conceptual shape, not a final schema:

```text
IntentSource
  source_hash
  source_kind
  exact_content_or_reference
  source_location
  speaker_or_authority_ref
  timestamp
  context_snapshot

ClarificationDecision
  decision_hash
  question
  alternatives
  selected_interpretation
  rationale
  authority_ref
  source_refs

BusinessRule
  rule_hash
  applicability
  decision
  scope
  effective_interval
  authority_ref
  input_fact_refs
  exception_refs

FormalCandidate
  candidate_hash
  formal_language_and_version
  clauses[]
  assumptions[]
  unresolved_items[]
  candidate_examples[]
  quality_diagnostics[]

FormalClause
  clause_hash
  typed_predicate
  source_refs[]
  decision_refs[]
  provenance_status
  explanation

ValidatedContract
  contract_hash
  accepted_candidate_hash
  scope_snapshot
  assumption_set_hash
  validation_evidence[]
  approval_record

ImplementationProof
  proof_record_hash
  contract_hash
  implementation_hash
  dependency_root
  verifier_identity
  proof_obligations[]
  assumptions_hash
  result
  evidence_ref
```

Content addressing is appropriate for immutable semantic states. Provenance and approval records may have their own contextual lifecycle and should not be mixed into a semantic value hash unless they change the value's semantics.

## 11. Architecture implications for LLMLang

This workflow fits the existing research direction:

- **Specification Graph:** intent sources, clarified requirements, business rules, formal candidates, accepted contracts.
- **Design Graph:** responsibility boundaries, caller/callee contracts, policy selection and data flow.
- **Implementation Graph:** executable implementation and explicit inputs/effects.
- **Context Planner:** retrieves caller context, relevant policy, glossary, decisions, and pinned versions.
- **Change Engine:** creates candidate graph changes and preserves alternatives.
- **Semantic Engine:** checks typed structure, dependencies, consistency, and impact.
- **Verification Engine:** checks formal obligations against exact accepted contract and implementation roots.
- **Approval layer:** records acceptance of exact candidate digests by authorized actors.

The LLM should be outside the trusted verification boundary. It may generate a candidate, explanation, example, or proof attempt. It cannot certify its own interpretation or proof.

The Context Planner should not retrieve all project history. It should retrieve the minimal relevant caller context plus the authoritative rules and dependencies needed to interpret the current request. The exact context root should be recorded so a later reviewer can reconstruct why a candidate was proposed.

## 12. Failure modes and required system behavior

| Failure mode | Required response |
|---|---|
| Ambiguous business term | Preserve alternatives and ask a targeted clarification |
| Missing policy value | Mark unresolved; do not invent a default |
| Conflicting authorities | Surface conflict and authority scope |
| Caller context unavailable | Mark interpretation incomplete |
| LLM adds unsupported predicate | Mark inferred/unsubstantiated; require review |
| Candidate is inconsistent | Reject validation; show contradiction |
| Candidate is vacuous | Warn or block acceptance according to policy |
| Candidate is unrealizable | Explain conflicting obligations/constraints |
| Examples disagree with stakeholder | Return to clarification |
| Source rule changes | Create new immutable rule/contract state |
| Proof succeeds but provenance is incomplete | Do not claim business intent validated |
| Verification is unknown or timed out | Preserve UNKNOWN/NOT_CHECKED, never success |

## 13. External approaches and what LLMLang can learn

### EARS — Easy Approach to Requirements Syntax

EARS uses a small set of structured natural-language patterns for ubiquitous, event-driven, state-driven, unwanted-behavior, and optional-feature requirements.

Useful lesson:
- a small number of recognizable sentence structures can improve consistency and make requirements easier to inspect;
- requirements should be atomic, testable, and avoid mixing implementation decisions into behavioral statements.

Limit:
- structured prose alone does not provide a complete formal semantics or prove that the selected interpretation matches business intent.

References:
- Mavin et al., "Easy Approach to Requirements Syntax" (2009), DOI: https://doi.org/10.1109/RE.2009.9
- University of Manchester publication record: https://research.manchester.ac.uk/en/publications/easy-approach-to-requirements-syntax-ears/

### NASA FRET / FRETISH

FRET is a requirements elicitation and formalization tool. FRETISH provides a structured natural-language front end; FRET provides formal logical interpretations, natural-language explanations, diagrams, simulation, and exports for analysis tools.

Useful lesson:
- show the stakeholder the semantics in several forms;
- use simulation to test whether the formal interpretation matches expected scenarios;
- support hierarchical requirements and traceability.

Limit:
- the user still needs to provide correct domain meaning, conditions, and responses. A formalized sentence is not automatically an authorized business decision.

References:
- NASA Software Catalog: https://software.nasa.gov/software/ARC-18066-1
- NASA paper, "Formal Requirements Elicitation with FRET": https://ntrs.nasa.gov/archive/nasa/casi.ntrs.nasa.gov/20200001989.pdf
- FRET repository documentation: https://github.com/NASA-SW-VnV/fret

For a programmer-oriented worked example, see [CF-007 — compositional bank transfer](CONTRACT-FORMALIZATION-CORPUS/cases/CF-007-compositional-bank-transfer.md): natural-language intent, explicit clarification, FRETish-inspired observation clauses, abstract callee contracts, and an analytical caller proof. Observation binding, progress, and source/contract correspondence remain independent obligations; the sketches are not parser-validated.

### Controlled Natural Language research

A 2025 systematic literature review of controlled natural languages for requirements specification covers 133 primary studies and categorizes approaches including standalone templates, requirement patterns, elementary templates, and linguistic rules. It identifies limitations in automated tooling, domain vocabulary support, empirical evaluation, and adoption.

Useful lesson:
- structured natural language is a practical bridge, not a universal solution;
- domain vocabulary and validation evidence matter;
- LLMLang should support more than one front-end style.

Reference:
- https://pure.etsmtl.ca/en/publications/controlled-natural-language-for-requirements-specification-a-syst/

### Automated formalization with FRETish

Research on FRETish describes compositional translation from structured natural language into metric temporal logic, with a framework for checking that generated formulas conform to the language semantics.

Useful lesson:
- formalization itself needs a defined, testable translation semantics;
- the transformation should be inspectable and independently checkable.

Reference:
- https://www.sciencedirect.com/science/article/pii/S0950584921000707

### Requirements NLP surveys

Systematic mapping work documents NLP tasks such as ambiguity detection, terminology extraction, requirements classification, traceability, and requirements analysis. Much of the research is evaluated in limited settings, so automation should be treated as decision support rather than autonomous requirements authority.

References:
- https://doi.org/10.1145/3444689
- https://link.springer.com/article/10.1007/s00766-023-00411-0

### Formal specification and proof

Dafny demonstrates the value of executable preconditions, postconditions, frame specifications, and termination metrics. Its documentation also makes clear that verification is relative to the written specification, and that soundness does not solve specification-intent mismatch.

References:
- https://dafny.org/latest/DafnyRef/DafnyRef
- https://dafny.org/blog/2023/10/27/proof-dependencies/

## 14. Open research questions

1. What is the smallest useful canonical Requirement IR that supports business, temporal, state, and effect requirements without forcing all requirements into one logic?
2. How should LLMLang represent domain vocabulary and contextual definitions without making every term globally unique?
3. How should the system distinguish an authoritative policy source from an explanatory or historical document?
4. What is the correct representation of delegated approval and policy precedence?
5. How should a candidate represent partial formalization when only some clauses are formalizable?
6. Can the system measure specification weakness by generating alternative implementations or mutations that satisfy the contract?
7. How should temporal semantics and effective-date semantics be exposed to non-specialists?
8. How should requirements that depend on probabilistic or externally nondeterministic behavior be represented?
9. What independent checker should validate the translation from the candidate IR into the proof engine's logic?
10. How should LLMLang detect that a caller's business rule is being incorrectly pushed into a reusable callee?
11. How should the graph represent a business rule that is jointly owned by multiple callers or a shared policy service?
12. What minimum review evidence is sufficient for low-risk versus safety-critical requirements?

## 15. Proposed next experiment

Build a small end-to-end experiment around `calculate_tax` with two callers.

Inputs:
- one natural-language rule for each caller;
- one ambiguous effective-date statement;
- one policy change affecting only one caller;
- a generic callee contract that accepts an explicit rate/policy input.

The experiment should test whether the pipeline can:
1. preserve original intent;
2. identify ambiguity and ask a precise question;
3. create distinct caller-scoped business rules;
4. generate a formal candidate with clause-level provenance;
5. produce examples and counterexamples for human review;
6. update only the affected caller rule;
7. leave the unaffected caller and generic callee unchanged;
8. report the exact contract and implementation proof obligations created by the change.

Success is not "the LLM guessed the intended tax rule". Success is that the system makes uncertainty visible, asks for missing authority, preserves provenance, and produces a reviewable change whose semantic impact is correctly scoped.

## 16. Conclusion

LLMLang should treat natural-language-to-formal-contract conversion as a controlled requirements-engineering process, not as a translation prompt.

The most important architectural boundary is between **proposing a formal interpretation** and **accepting that interpretation as the business contract**.

The LLM can substantially reduce the effort of elicitation, decomposition, formalization, example generation, and traceability. But the accepted meaning must come from an authorized human or authoritative policy source, and implementation proof must remain a separate, independently checked claim.

This approach also supports caller-driven evolution: business policy changes where the policy is owned and applied; shared lower-level capabilities change only when their own observable contract must change.
