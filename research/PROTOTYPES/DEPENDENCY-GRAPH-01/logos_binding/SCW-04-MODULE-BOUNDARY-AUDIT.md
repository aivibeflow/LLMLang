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
- SCW-15 remains open: move relational translation/evaluation/theorems onto the independent IR, add a separate Logos adapter, and prove adapter preservation.
- SCW-32 remains open and downstream: connect the proved source-derived formula to Logos terms and retain parser-state identity checks.
- No theorem status is upgraded by this audit. Existing theorems remain expression-level only.

## Verification

Inspected `SourceQuerySemantics.lean`, `RelationalSourceQuerySemantics.lean`, `LLMLangLogosBinding.lean`, `Main.lean`, and `lakefile.lean` on `main`. This is a source/dependency audit, not a Lean build; no CI result is claimed.