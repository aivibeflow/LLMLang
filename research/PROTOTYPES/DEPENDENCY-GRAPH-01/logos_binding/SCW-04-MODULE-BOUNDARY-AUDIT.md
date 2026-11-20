**Current disposition (2026-11-20):** This is a historical audit of the pre-SCW-15 module graph. The original findings are preserved below; the dependency decoupling is now implemented and validated, as recorded in §5.

# SCW-04 — Lean module and trust-boundary audit

**Status:** Audit complete; implementation remains SCW-15.  
**Date:** 2026-11-18

## Observed dependency graph

```text
SourceQuerySemantics.lean
  └── no project imports; defines source Expr, independent QueryTerm,
      evalExpr, evalQuery, translateExpr_preserves_eval

LLMLangLogosBinding.lean
  ├── imports SourceQuerySemantics, Lean, and Cpc.Parser
  └── defines LogosBinding.QueryTerm, Eo.Term renderer, JSON decoder,
      CPC parser-state bridge

RelationalSourceQuerySemantics.lean
  ├── imports SourceQuerySemantics
  ├── imports LLMLangLogosBinding
  └── relational translators and evaluator directly use LogosBinding.QueryTerm

Main.lean
  └── imports the Logos binding and relational module for integration tests

lakefile.lean
  └── pins Cpc at cf18742973861b3718d04c5f25775448098ff474
```

## Finding

`SourceQuerySemantics.QueryTerm` and its evaluator are already Logos-independent. The relational proof does not use them: it aliases its sort to `LogosBinding.QuerySort`, returns `LogosBinding.QueryTerm` from relational translators, and evaluates those terms in a custom mutually recursive evaluator. Thus the relational semantic module transitively imports the Logos/CPC integration layer even though its mathematical source/query statement does not require it.

There are two overlapping but non-identical query ASTs:
- independent AST: `mulConst`, binary `and`/`or`;
- Logos AST: general binary `mul`, list-valued `and`/`or`.

They must not be conflated without an explicit constructor mapping and preservation theorem.

## Target layering

```text
SourceSyntax / SourceSemantics
          -> IndependentQueryIR
          -> RelationalSourceQuerySemantics
          -> LogosQueryAdapter
          -> LLMLangLogosBinding (JSON, CPC parser state, Eo.Term)
```

Semantic modules must not import Logos, CPC, cvc5, or solver APIs. The adapter may import the semantic IR and Logos APIs, and must prove sort/structure preservation for its supported constructors. Unsupported constructors must fail closed.

## Disposition

- SCW-04 audit is complete: dependency defect, duplicate-IR mismatch, trust boundary, and target layering are documented.
- At the audit date, SCW-15 remained open; its subsequent implementation is recorded in §5: move relational translation/evaluation/theorems onto the independent IR, add a separate Logos adapter, and prove adapter preservation.
- SCW-32 remains open and downstream: connect the proved source-derived formula to Logos terms and retain parser-state identity checks.
- No theorem status is upgraded by this audit. Existing theorems remain expression-level only.

## Verification

Inspected `SourceQuerySemantics.lean`, `RelationalSourceQuerySemantics.lean`, `LLMLangLogosBinding.lean`, `Main.lean`, and `lakefile.lean` on `main`. This is a source/dependency audit, not a Lean build; no CI result is claimed.

## 5. Current source graph and disposition — 2026-11-20

The original audit correctly described the source state it inspected. Subsequent SCW-15 work changed the dependency boundary:

- [`RelationalSourceQuerySemantics.lean`](RelationalSourceQuerySemantics.lean) imports `SourceQuerySemantics` only; it no longer imports `LLMLangLogosBinding`.
- [`LogosQueryAdapter.lean`](LogosQueryAdapter.lean) is the separate adapter from the independent source query term to `LogosBinding.QueryTerm), with theorem `toLogosQueryTerm_preserves_eval`.
- [`QfLiaAdmissibility.lean`](QfLiaAdmissibility.lean) combines the relational program and adapter for the bounded QF_LIA profile.
- [`LLMLangLogosBinding.lean`](LLMLangLogosBinding.lean) owns the external `Cpc.Parser` integration, renderer, and parser-state boundary.
- [`Main.lean`](Main.lean) integrates the modules and runs the bounded correspondence checks.

SCW-15 was implemented in PR #41 and built/tested in subsequent work. The latest relevant [Logos-binding CI run 44766546452](https://github.com/aivibeflow/LLMLang/actions/runs/44766546452), associated with PR #94, passed both the parser-state bridge build and semantic-correspondence test steps. No Lean source, `lakefile.lean`, or `lean-toolchain` changes occurred after the PR #94 merge commit in the reviewed main history.

This closes the specific SCW-15 module-decoupling and adapter-preservation scope. It does not close the later SCW-32 source-derived CPC binding, serialized-query correspondence, or parser-state identity obligations. Scenario 34 remains in progress on those boundaries.
