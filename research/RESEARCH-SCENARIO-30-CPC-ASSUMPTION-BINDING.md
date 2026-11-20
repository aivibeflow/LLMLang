# Research Scenario 30 — Binding CPC Assumptions to the Canonical Relational Query

**Status:** Source-level integration analysis; no Lean wrapper or real proof integration has been built.  
**Date:** 2026-11-17  
**Depends on:** Scenarios 27–29.  
**Question:** What exactly must LLMLang establish before a Logos-checked CPC proof can count as evidence about the canonical relational query generated from a typed LLMLang program?

## 1. Executive conclusion

The Logos source audit confirms the core boundary identified in Scenario 29, and makes it more precise:

- `Eo.parseProof` returns a pair `(List Term × CCmdList)`.
- The first element is populated from top-level CPC `assume` commands, not by parsing or checking the original SMT-LIB query.
- The parser collects assumptions only before the first proof step. Declarations/definitions are parser state; `include` and `reference` do not bind the proof to the original query.
- `logos_check_proof` checks the parsed assumptions and commands. Its correctness theorem concludes that the conjunction of the parsed assumption list is unsatisfiable.
- The checker does not compare that list with an independently generated LLMLang query.

Therefore, “one SMT-LIB assert” does **not** establish “one CPC assumption identical to that assert”. The shape of the CPC assumptions must be observed and bound, not inferred from the source query's surface syntax.

**Most promising first implementation:** a deliberately narrow, exact-binding mode. Generate a canonical relational query, generate its expected Logos `Term` AST independently from the same canonical query IR, and accept a proof only when the parsed CPC assumption list is exactly equal to the expected list. Any preprocessing, splitting, rewriting, introduced assumption, missing assumption, or AST mismatch returns `UNKNOWN`. This mode may reject many otherwise valid cvc5 proofs; that is an intentional fail-closed limitation.

Do not widen this boundary through string comparison, hashes alone, solver exit codes, or unproved normalization.

## 2. Source-level audit of pinned Logos

Audited repository: https://github.com/cvc5/logos  
Audited revision: `cf18742973861b3718d04c5f25775448098ff474`  
Lean toolchain: `leanprover/lean4:v4.34.0`

### 2.1 Parser contract

In `Cpc/Parser.lean`, `Eo.parseProof` delegates to `Logos.Parser.parseProof parserConfig proof` and returns:

```lean
Except String (List Term × CCmdList)
```

In `Logos/Parser/Datatypes.lean`, the generic parser:
1. parses the supplied proof text as s-expressions;
2. invokes `parseCommands`;
3. elaborates/resolves parsed terms using the configured datatype representation;
4. returns the assumption terms and command list.

In `Logos/Parser/Core.lean`, `parseCommands`:
- appends every top-level `assume` command to the assumption list;
- rejects an assumption appearing after the first proof command;
- accumulates proof commands separately;
- treats declarations/definitions as parser state;
- returns the assumption list in source order.

The parser is not an SMT-LIB input parser. It parses the CPC proof artifact.

### 2.2 What the executable theorem proves

In `Cpc/Api.lean`:
- `logos_check_proof` parses the CPC text and invokes `logos_verdict`;
- `logos_verdict` checks refutation, assumption translation side conditions, and command translation side conditions;
- `logos_assumption_arglist` folds the parsed list into the checker's argument list;
- `logos_assumption_term` converts that argument list into the conjunction used by the soundness theorem.

The fold order is significant. The source documents that for parser assumptions `A1 ... An`, the checker argument list is `[An, ..., A1]`, and the resulting conjunction has `An` as its outermost conjunct. A wrapper must use the library's actual function rather than reimplementing an assumed ordering.

In `Cpc/ApiCorrect.lean`, `correct___logos_check_proof` states, in substance:

```lean
parseProof input = Except.ok (assums, cmds) ->
logos_check_proof input = Except.ok Verdict.correct ->
eo_satisfiability (logos_assumption_term assums) false
```

This is a theorem about the parsed assumption list. It does not establish that the list is the original LLMLang query.

### 2.3 Consequence

The following inference is invalid without an additional binding argument:

```text
cvc5 was given LLMLang query Q
Logos returned correct for proof file P
therefore Q is unsatisfiable
```

The supported conclusion is only:

```text
Logos returned correct for P
therefore conjunction(parsed_assumptions(P)) is unsatisfiable
```

The missing link is a formally justified relation between Q and those parsed assumptions.

## 3. Query-to-proof binding options

### Option A — Exact assumption-list equality (selected MVP)

Construct the expected assumption list as Lean `Term` values directly from the canonical Relational Query IR. Parse the CPC proof using Logos and compare:

```lean
parsedAssumptions == expectedAssumptions
```

The comparison must be Lean structural equality over the actual `Term` AST, not equality of rendered text or hashes.

Acceptance requires:
- the CPC proof parses successfully;
- the parsed assumption list has exactly the expected length and order;
- every parsed assumption is structurally equal to the corresponding expected assumption;
- Logos returns `Verdict.correct`;
- the existing translation side conditions pass;
- the expected term is well-typed, closed, Boolean, and within the supported semantic fragment;
- the Lean theorem connects this exact equality to the assumptions passed to the Logos soundness theorem.

A mismatch is not a weak success. It is `UNKNOWN` / `QUERY_BINDING_MISMATCH`.

**Advantages:** smallest proof obligation; no assumptions about cvc5 preprocessing; no permissive normalization; easiest to audit.

**Disadvantages:** cvc5 may split, simplify, reorder, or otherwise transform the assumptions. Such proofs will be rejected even if mathematically valid. The MVP must not silently repair this by normalizing either side.

### Option B — Proof-producing query transformation (future extension)

If exact equality proves too restrictive, define a small, explicit transformation language between the canonical query and the CPC assumption conjunction.

Each transformation step must carry a proof in Lean that it preserves the property needed for unsatisfiability transfer. The proof must cover:
- Boolean rewrites and conjunction splitting;
- substitutions and let/definition expansion;
- introduced fresh constants and their existential interpretation;
- eliminated or abstracted terms;
- declaration/sort correspondence;
- the exact scope and ordering of assumptions.

For transformations introducing auxiliary symbols, plain syntactic equality or a same-variable implication is insufficient. The formal statement must account for existential extension/projection (or establish a stronger equisatisfiability theorem).

The target theorem is a verified relation sufficient to transfer unsatisfiability from the Logos assumptions to the original canonical query. Prefer a theorem of equisatisfiability; a one-way satisfiability-preservation theorem is acceptable only when its direction is explicitly proved sufficient for the desired unsatisfiability conclusion.

This option is more general but significantly increases the trusted formalization and is not required for the MVP.

### Option C — External matching by text/hash

Rejected. Text equality is sensitive to formatting and does not prove semantic identity. Hash equality only proves equality of the hashed byte strings. Neither binds parsed Lean terms to the canonical query semantics.

### Option D — Second solver/checker agreement

Useful as defense in depth and diagnostics, but rejected as the query-binding proof. Two tools can agree on a transformed or incorrectly generated query. Agreement does not prove correspondence to LLMLang source semantics.

## 4. Canonical query IR and dual generation

The canonical Relational Query IR must be the single source for both outputs:

```text
Typed LLMLang IR + selected input factor + observation boundary
                         |
                         v
              Canonical Relational Query IR
                         |
              +----------+----------+
              |                     |
              v                     v
       SMT-LIB QF_LIA text    Expected Logos Term AST
              |                     |
              v                     |
          cvc5 solver               |
              |                     |
              v                     |
           CPC proof                |
              |                     |
              v                     v
       Logos parseProof ------> exact structural equality
                         |
                         v
                Logos proof checker
                         |
                         v
              checked unsatisfiability
```

The two renderers must be deterministic and versioned. The query IR hash, renderer versions, expected AST hash, exact SMT-LIB bytes, CPC proof hash, Logos revision, and checker result must be included in the evidence record.

Important: generating both representations from one IR prevents accidental divergence in the generator, but does not itself prove either renderer correct. The Lean formalization must establish:
1. the expected `Term` AST has the intended SMT semantics;
2. the SMT-LIB renderer denotes the same canonical query;
3. the paired-execution relational formula correctly represents the selected LLMLang property;
4. the typed LLMLang IR semantics is preserved by the relational query translation.

Until these correspondence theorems exist, a checked CPC proof is evidence about the query AST, not yet a proof about the LLMLang program.

## 5. Exact MVP restrictions

The first integration must use the narrow QF_LIA profile from Scenario 29:
- Boolean and mathematical integer terms only;
- no quantifiers, arrays, strings, datatypes, uninterpreted functions or sorts;
- no nonlinear multiplication;
- no division, modulo, partial arithmetic, concurrency, effects, exceptions, or external calls;
- closed Boolean query terms after all free program inputs have been explicitly declared as constants in the proof context;
- no unproved simplification, normalization, or auxiliary-symbol introduction between expected AST construction and accepted CPC assumptions.

If the solver emits assumptions that do not exactly match the expected list, reject the proof and retain `UNKNOWN`. Do not expand the supported fragment merely to make the first integration pass.

## 6. Lean wrapper design

The wrapper should import the pinned Logos API and expose a small function whose inputs are:
- CPC proof text;
- expected assumptions generated from canonical query IR.

Its decision procedure:
1. call `Eo.parseProof`;
2. reject parser errors;
3. compare the returned assumption list to the expected list using structural equality;
4. call the same `Eo.logos_verdict` used by the executable, or a proved equivalent API;
5. return a bound result only when exact equality and `Verdict.correct` both hold.

The key theorem should be stated over the exact expected list, not an arbitrary parser output. It should reuse `correct___eo_is_refutation` / `correct___logos_verdict` and derive the unsatisfiability of the expected assumptions from the equality premise.

This is a design target, not compiled Lean code. Names and imports must be checked against the pinned revision during implementation. The wrapper must not weaken or replace Logos's existing side conditions.

## 7. Required adversarial test matrix

| Case | Expected result |
|---|---|
| Correct CPC proof, exact expected assumption list | Bound checker result |
| Correct proof for a different formula | `QUERY_BINDING_MISMATCH` |
| Same formulas in a different assumption order | `QUERY_BINDING_MISMATCH` |
| Missing assumption | `QUERY_BINDING_MISMATCH` |
| Additional assumption | `QUERY_BINDING_MISMATCH` |
| One assumption replaced with a stronger formula | `QUERY_BINDING_MISMATCH` |
| One assumption replaced with a weaker formula | `QUERY_BINDING_MISMATCH` |
| Reordered or algebraically rewritten but equivalent AST | `QUERY_BINDING_MISMATCH` in MVP |
| Malformed CPC proof | `UNKNOWN` |
| Logos `incorrect` | Not proven |
| Logos `incomplete` | Not proven |
| Timeout, crash, missing binary, pin mismatch | `UNKNOWN` |
| Unsupported QF_LIA construct | `NOT_SUPPORTED` |
| Exact assumptions but missing source-to-query theorem | Checker-bound query result only; not LLMLang `PROVEN` |

Tests must include a proof that is valid for a deliberately different query. This is the central negative test: Logos should accept that proof in isolation, while the LLMLang wrapper must reject it because its assumptions do not match the expected query.

## 8. Status model

Do not collapse the following boundaries:

- `SOLVER_REPORTED_UNSAT`: cvc5 reports UNSAT.
- `CHECKER_REPORTED_CORRECT_UNBOUND`: Logos reports correct, but the parsed assumptions are not bound to the expected query.
- `CHECKER_REPORTED_CORRECT_BOUND`: Logos reports correct and the exact expected assumption list matches.
- `QUERY_TRANSLATION_VALIDATED`: formal correspondence from canonical query IR to the exact query/assumptions is established.
- `PROGRAM_PROPERTY_PROVEN`: source-to-query correspondence is also proved, and all proof-context assumptions are explicit.

Only the last state can support LLMLang's property-level `PROVEN`. A bound checker result alone must not be promoted to program-level proof.

## 9. Implementation sequence

1. Add the source-level parser/API audit and this exact-binding contract (this scenario).
2. Implement a QF_LIA-only canonical query IR and independent SMT-LIB / Logos-Term renderers.
3. Implement a Lean wrapper that parses CPC, checks exact assumption-list equality, and reuses Logos's verdict.
4. Build the pinned Logos revision and compile the wrapper; record actual build logs and toolchain hashes.
5. Generate a golden cvc5 CPC proof and inspect the exact parsed assumption list. If it does not equal the expected list, keep the proof unbound; do not assume a single assertion produces one assumption.
6. Run the adversarial mismatch matrix, including a valid proof for a different query.
7. Prove query-renderer correspondence and the relational-query construction.
8. Prove the typed-program-to-query correspondence for the selected property.
9. Only then promote the result to property-level `PROVEN`.

## 10. Research limitations and sources

This audit inspected the pinned Logos source files:
- `Cpc/Parser.lean`
- `Logos/Parser/Datatypes.lean`
- `Logos/Parser/Core.lean`
- `Cpc/Api.lean`
- `Cpc/ApiChecks.lean`
- `Cpc/ApiCorrect.lean`
- `Cpc/LogosTerm.lean`

Useful upstream references:
- [Logos repository](https://github.com/cvc5/logos)
- [Pinned Logos API](https://github.com/cvc5/logos/blob/cf18742973861b3718d04c5f25775448098ff474/Cpc/Api.lean)
- [Pinned parser](https://github.com/cvc5/logos/blob/cf18742973861b3718d04c5f25775448098ff474/Logos/Parser/Core.lean)
- [cvc5 CPC proof documentation](https://cvc5.github.io/docs/cvc5-1.4.2/proofs/output_cpc.html)

The source audit is not a compiled integration. The current environment has no Lean, Lake, cvc5, Logos, Rust, or Cargo installed, and outbound GitHub clone access is unavailable. No real CPC proof, wrapper build, or mathematical correspondence theorem was executed or checked.

No normative LLMLang document is changed by this research scenario.
