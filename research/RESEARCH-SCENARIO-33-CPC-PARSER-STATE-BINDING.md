# Research Scenario 33 — CPC Parser State and Exact Symbol Binding

**Status:** Source-audited design; Lean wrapper not compiled.  
**Date:** 2026-11-17  
**Pinned Logos revision:** cf18742973861b3718d04c5f25775448098ff474  
**Depends on:** Scenarios 29, 30, and 32.  
**Question:** How can expected query terms be mapped to the exact uninterpreted-constant identities used by Logos when its public parseProof API discards the parser's declaration table?

## 1. Problem

The CPC assumption parser does not represent a declared SMT constant by its source spelling. In the pinned Logos implementation:

- declare-const calls declareSymbol;
- declareSymbol increments ufCount and calls mkUConst (ufCount + 1) for non-sort declarations;
- the Eo-to-SMT translation maps Term.UConst i T to SmtTerm.UConst (native_uconst_id i) (translated sort).

The parser's public parseProof returns only (assumptions, commands). It uses run' and discards the final parser state. Comparing a query symbol name directly to a Term.UConst is therefore incorrect.

## 2. Source-audited opportunity

The parser exposes enough lower-level API to retain the state without writing a second CPC parser:

- ParserM T is StateT (State T) (Except String).
- parseCommands is public and returns parsed assumptions and commands.
- State is public and contains ufCount and terms.
- State.ofOps initializes the parser state from the operator table.
- Parser configuration exposes ops and macros.

The state terms map stores declarations by name. A declared constant is represented there by a UConst node, while zero-argument definitions store an expression term and parameterized definitions are stored as macros.

## 3. Selected bridge

Add a small downstream Lean wrapper that:
1. Parses CPC S-expressions using the same Logos S-expression parser.
2. Initializes the parser state from the exact pinned Eo.parserConfig operator table and macro list.
3. Runs the public Logos.Parser.parseCommands with StateT.run, not run'.
4. Returns assumptions, commands, and the final parser state.
5. Extracts the name-to-(UConst ID, sort) map from the final state.
6. Rejects duplicate or ambiguous declarations, unsupported sorts, and missing expected symbols.
7. Constructs the expected Eo.Term query using the state-derived UConst IDs.
8. Compares the entire parsed assumption list with the expected assumptions using Lean's native structural equality.

This avoids a second CPC declaration parser and avoids assumptions about declaration order in a separate implementation.

## 4. Restricted-parser equivalence condition

The normal parseProof path calls a private parseConfigured helper. When datatypeTerms are present, that helper builds an elaboration configuration and resolves datatype terms before returning the assumptions. The proposed wrapper calls parseCommands directly.

The QF_LIA profile contains only Bool and Int constants and no declared datatypes. Nevertheless, this does not automatically prove equivalence. Before using the wrapper as a proof boundary:

- explicitly reject CPC datatype and sort declarations;
- test the wrapper against parseProof on a corpus of QF_LIA CPC proofs;
- establish that the direct parser path and ordinary parseProof produce structurally equal assumptions and commands for the accepted subset;
- fail closed on any parse shape outside that subset.

## 5. Lean sketch

The following is a design sketch, not compiled code:

```lean
def parseProofWithState (proof : String) :
    Except String (List Eo.Term × Eo.CCmdList × Logos.Parser.State Eo.Term) := do
  let sexps ← Sexp.Parser.manySexps!.run proof
  let initial := {
    Logos.Parser.State.ofOps Eo.parserConfig.ops with
      macros := .ofList Eo.parserConfig.macros
  }
  let ((assumptions, commands), finalState) ←
    (Logos.Parser.parseCommands Eo.parserConfig sexps).run initial
  return (assumptions, commands, finalState)
```

The exact imports, namespaces, inferred StateT result type, and Lean syntax still require compilation against the pinned toolchain.

## 6. Safety properties and fail-closed cases

Return UNKNOWN if any of the following occurs:

- parser wrapper does not compile or differs from the pinned source API;
- parseProof and the state-preserving path disagree on the accepted subset;
- a query symbol is absent from the final declaration map;
- a query symbol has an unexpected sort;
- a declaration name maps to multiple UConst nodes;
- unexpected uninterpreted sorts or function declarations occur;
- the complete parsed assumptions are not exactly the expected assumption list;
- any assumption uses an unbound or extra UConst;
- a CPC proof is incomplete or Logos does not report a checker-accepted result.

No sorting, rewriting, alpha-normalization, or semantic equivalence comparison is allowed at the final assumption-binding boundary.

## 7. Evidence boundary

The wrapper exposes parser state; it does not prove the Python query encoder correct. The expected Eo.Term must be generated independently in Lean from a typed query representation or a verified serialization of that representation. The Lean code must prove that its expected term corresponds to the canonical query IR. The CPC assumptions must then match it structurally, and the pinned Logos checker theorem must establish unsatisfiability of those exact parsed assumptions.

Until those steps are built and proved, this bridge is a design candidate only. It does not upgrade any Scenario 31 result beyond QF_LIA_CANDIDATE_QUERIES.
