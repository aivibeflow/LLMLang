# Research Scenario 31 — A Strict QF_LIA Relational Query Profile

**Status:** Implementation design based on source audit; no code changes yet.  
**Date:** 2026-11-17  
**Depends on:** Scenarios 26–30.  
**Question:** What must be restricted or changed in the current symbolic relational prototype before its queries can safely enter the QF_LIA Logos proof-checking path?

## 1. Executive conclusion

The current Scenario 27 encoder is broader than the first Logos proof profile and cannot be reused unchanged.

Source audit findings:
- `typed_ir.py` accepts `Int`, `Bool`, and `String`.
- `typed_ir.py` accepts multiplication of arbitrary integer expressions.
- `symbolic_relational.py` also accepts `Int`, `Bool`, and `String`.
- Its encoder emits `(set-logic ALL)`.
- Its observation tuple includes an `outcome` string literal, even though the current typed symbolic fragment only admits a top-level return and rejects error/event outcomes.
- Its expression encoder permits variable-by-variable multiplication.

These are valid reasons to keep the existing general symbolic prototype separate, but they are incompatible with the narrow QF_LIA-only Logos MVP.

**Selected direction:** add a separate strict QF_LIA query-building path. Do not silently narrow or reinterpret the existing Scenario 27 API. The new path must reject unsupported inputs before emitting any query, produce only Bool/Int terms, emit `(set-logic QF_LIA)`, and omit the constant string outcome observation because the accepted program fragment has only normal return. Existing broad symbolic analysis remains unchanged and must not be presented as eligible for Logos proof checking.

## 2. Current incompatibilities

| Area | Current prototype | QF_LIA proof profile |
|---|---|---|
| Input sorts | Int, Bool, String | Int, Bool only |
| State/local literals | Int, Bool, String | Int, Bool only |
| Expression literals | Int, Bool, String | Int, Bool only |
| Multiplication | Any Int × Int | At least one operand is an integer literal |
| Logic declaration | `ALL` | `QF_LIA` |
| Outcome observation | String literal `"return"` | Omit; normal return is fixed by the supported core |
| Solver output | Solver-reported SAT/UNSAT | Still only solver-reported; CPC proof required for proof path |

The QF_LIA path must be a distinct API/version and evidence identity. It must not change the meaning of old evidence records or make old `ALL` queries appear eligible for the new proof boundary.

## 3. Supported QF_LIA subset

### 3.1 Sorts and values

Allowed:
- mathematical integers;
- Booleans;
- integer and Boolean constants;
- explicitly declared integer and Boolean inputs;
- explicitly initialized integer and Boolean local/state values.

Rejected:
- strings and string constants;
- reals, bit-vectors, arrays, sets, sequences, datatypes;
- uninterpreted sorts and functions;
- floats, null, and host-language values outside exact `int` / `bool` (Python bool must not be accepted as an integer).

### 3.2 Expressions

Allowed:
- `not`, `and`, `or`;
- integer unary negation;
- integer addition and subtraction;
- integer multiplication only when one operand is a literal integer constant;
- equality over Bool or Int;
- integer `<` and `<=`;
- `ite` with a Boolean condition and same-sort branches;
- pure non-recursive functions after inlining, provided the expanded body remains inside this fragment.

Rejected:
- multiplication of two non-literal expressions;
- division, modulo, exponentiation, nonlinear arithmetic;
- string operations and equality;
- quantifiers, arrays, uninterpreted functions, and all unsupported AST nodes.

The MVP should be syntactically conservative. It need not prove that an arbitrary expression is constant before accepting multiplication. For example, `(x * (2 + 3))` may be rejected even though one side is mathematically constant. Constant folding can be added later as a separately tested and versioned transformation.

### 3.3 Program shape

Retain the existing typed-core restrictions:
- deterministic execution;
- explicit initial locals and state;
- assignment, state store, conditional branches with joined environments;
- pure non-recursive calls, inlined into the expression;
- one top-level final return;
- no loops, recursion, exceptions, events, I/O, external calls, concurrency, aliasing, or nondeterminism.

The QF_LIA path must validate the entire program and all function bodies, not merely the expressions that happen to appear in one emitted query.

## 4. Observation semantics

The current symbolic encoder adds `outcome = "return"` to its observations. In the strict typed fragment, the only accepted terminal command is a top-level `Return`; `Raise` and `Emit` are rejected, and nested returns are rejected. Both paired executions therefore have the same normal-return outcome by construction.

The QF_LIA relational query should compare:
- the return value;
- each explicitly selected observable state region.

It should not encode the constant outcome string. This omission is valid only while the program validator guarantees that every accepted execution reaches the same normal-return outcome. If the core later supports errors, early termination, events, or nondeterminism, outcome semantics must be revisited and the proof profile versioned.

The observation contract identifier for this profile must be distinct from the current general symbolic observation contract.

## 5. Query generation contract

For each input factor:
1. declare a left and right copy of that factor;
2. share every other input between both executions;
3. use identical initial state and initial locals;
4. execute both copies using the same validated program semantics;
5. require the selected factor values to differ;
6. assert that at least one observed return/state value differs;
7. emit an explicit `QF_LIA` logic declaration;
8. reject the query if any emitted term or declaration is outside Bool/Int linear arithmetic.

The generated query should be deterministic. Its evidence identity must bind:
- canonical typed IR digest;
- strict profile version;
- validator source digest/version;
- relational encoder source digest/version;
- observation-contract version;
- canonical query IR digest;
- exact SMT-LIB bytes and SHA-256;
- input factor and observation boundary.

Do not treat a deterministic string hash as a proof of encoder correctness.

## 6. Implementation plan

Add a new module, tentatively `src/qf_lia_profile.py`, with three separate responsibilities:

1. **Profile validator** — validates the full typed program and rejects strings, non-linear multiplication, and unsupported sorts/operators before query generation.
2. **Canonical relational query builder** — builds a typed query representation from the validated program, selected factor, and observation contract.
3. **SMT-LIB renderer** — renders only the accepted canonical query and always emits `(set-logic QF_LIA)`.

The new API must not call the existing `analyze_symbolically` function as its query generator because that function runs the solver and emits `ALL` plus the string outcome observation. It may reuse well-tested expression semantics only after factoring out a shared encoder with an explicit profile parameter and tests proving the two profiles do not leak into each other.

The initial implementation should prefer a separate conservative encoder over a broad refactor. A refactor can follow after the strict path has golden tests.

## 7. Required tests

### Acceptance
- integer identity/linear arithmetic query;
- Boolean input and conditional branch;
- multiplication by positive, zero, and negative integer literals;
- inlined pure function with linear body;
- integer and Boolean observable state;
- deterministic byte-for-byte rendering.

### Rejection
- String input, local, state, literal, or return;
- variable multiplied by variable;
- expression multiplied by expression, even if it could fold to a constant;
- Bool used as Int;
- unsupported function/operator/node;
- recursive function;
- any hidden String outcome term;
- any query declaring `ALL` or a non-QF_LIA logic.

### Relational correctness
- left/right copies differ only in the selected factor;
- all other inputs are shared;
- initial state and locals are identical;
- return and selected state differences are included;
- outcome is absent only because the validator guarantees normal return;
- compare generated query behavior against the finite reference evaluator on exhaustive small integer/Boolean domains.

No test that merely checks for the substring `QF_LIA` is sufficient. The validator must reject unsupported terms before rendering, and tests must inspect the full emitted declarations and expression tree.

## 8. Proof obligations still outstanding

Even after this profile validator and encoder pass their tests:
- Python tests do not prove the validator sound;
- the renderer is not formally verified;
- exact Logos assumption binding is not implemented;
- the source-to-query relational correspondence is not proved;
- no real cvc5 CPC proof or Logos proof has been checked.

Therefore this profile can produce **QF_LIA-eligible candidate queries**, not `PROVEN` results. The only allowed proof-related status before Lean correspondence is `CHECKER_REPORTED_CORRECT_UNBOUND` or, after Scenario 30 exact AST binding, `CHECKER_REPORTED_CORRECT_BOUND`.

## 9. Sources and audit scope

Audited LLMLang sources:
- `PROTOTYPES/DEPENDENCY-GRAPH-01/src/typed_ir.py`
- `PROTOTYPES/DEPENDENCY-GRAPH-01/src/symbolic_relational.py`
- `PROTOTYPES/DEPENDENCY-GRAPH-01/src/formal_core.py`
- `PROTOTYPES/DEPENDENCY-GRAPH-01/src/proof_boundary.py`

Related research:
- [Scenario 26 — Minimal Formal Semantic Core](RESEARCH-SCENARIO-26-MINIMAL-FORMAL-SEMANTIC-CORE.md)
- [Scenario 27 — Symbolic Relational Verification](RESEARCH-SCENARIO-27-SYMBOLIC-RELATIONAL-VERIFICATION.md)
- [Scenario 29 — Verified SMT Proof Checking](RESEARCH-SCENARIO-29-VERIFIED-PROOF-CHECKER-AND-ENCODER-VALIDATION.md)
- [Scenario 30 — CPC Assumption Binding](RESEARCH-SCENARIO-30-CPC-ASSUMPTION-BINDING.md)

No code or normative LLMLang document is changed by this research scenario.
