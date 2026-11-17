# Research Scenario 32 — Canonical Typed Relational Query IR

**Status:** Implemented Python prototype for the typed query representation and SMT-LIB renderer; no Logos-Term renderer or Lean correspondence theorem.  
**Date:** 2026-11-17  
**Depends on:** Scenarios 29–31.  
**Question:** What intermediate representation is needed so that one canonical relational query can drive independent SMT-LIB and Logos proof-term generation without making rendered text the semantic source of truth?

## 1. Executive conclusion

Scenario 30 requires one canonical Relational Query IR to feed two independent outputs:

1. SMT-LIB QF_LIA text for cvc5.
2. An expected Logos Term AST for exact CPC-assumption binding.

The first Scenario 31 prototype emitted SMT-LIB directly from strings and hashed a dictionary of rendered fragments. That was useful for testing the narrow fragment, but it was not yet a typed canonical query IR and could not serve as a clean shared source for an independent Logos-Term renderer.

**Selected direction:** use a small immutable, typed expression tree and a typed relational-query record. Each backend is a separate renderer over this same structure. The IR itself contains no SMT-LIB snippets and no Logos-specific structures.

## 2. Implemented representation

New module: src/qf_lia_ir.py.

- Term(op, sort, args, atom) — typed expression node.
- Declaration(name, sort) — explicitly declared Bool/Int constant.
- RelationalQuery(factor, declarations, factor_difference, observations_differ, observation_contract) — canonical per-factor product-program query.
- render_smt2(query) — deterministic SMT-LIB QF_LIA renderer.

The profile builder in src/qf_lia_profile.py constructs the typed IR first, then calls the SMT-LIB renderer. Each FactorQuery retains the typed query object, its canonical digest, the exact SMT-LIB text, and the SHA-256 digest of those exact bytes.

## 3. IR-level restrictions

The renderer validates the entire query before producing output:

- declarations have unique generated identifiers and only Bool/Int sorts;
- every symbol is declared with the same sort used at its occurrence;
- terms are well-typed;
- only the supported Bool/Int operators are accepted;
- multiplication must have an integer-literal operand;
- all assertion roots are Boolean;
- no strings, quantifiers, arrays, uninterpreted functions, or unknown nodes are representable by the accepted term grammar.

The profile builder still performs source-AST validation and constructs the paired executions. The renderer is a second fail-closed boundary: it does not assume that every caller constructed a valid query object.

## 4. Why this is better than a text-first representation

A text-first design makes it difficult to establish that:
- two output backends received the same semantic query;
- a parsed proof assumption corresponds to a specific query term;
- a query digest commits to operator and sort structure rather than only to a serialization convention;
- a backend has not silently widened the accepted fragment.

The typed IR allows:
- a deterministic canonical structural digest;
- a separate exact-byte digest for each rendered artifact;
- an independent Logos-Term renderer in the future;
- backend-specific validation without letting backend syntax leak into the source representation.

A shared IR does not prove either renderer correct. It only gives both renderers the same explicit input. Formal correspondence theorems remain necessary.

## 5. Validation performed

The focused QF_LIA tests now cover:
- acceptance and rendering of linear Int/Bool queries;
- branch ite construction;
- paired input sharing;
- selected-state observations;
- pure function inlining;
- literal multiplication, including zero and negative constants;
- rejection of nonlinear multiplication both in the source AST and directly in a malformed query IR;
- query-IR type and renderer-source identity;
- deterministic query and byte digests;
- unsupported sorts, operators, effects, recursion, and malformed program shapes.

Latest focused run: **26 tests passed**. Python compileall passed. The tests were executed locally against a compatibility fixture reproducing the repository's formal_core AST dataclasses and exception interface; a full repository checkout and full prototype suite were not available. No cvc5 solver or Logos checker was invoked.

## 6. Remaining obligations

1. **Completed source audit at pinned Logos revision** (cf18742973861b3718d04c5f25775448098ff474): the Eo term constructors include Boolean, Numeral, UConst, Var, UOp, and Apply. The parser maps declare-const to sequential UConst identifiers; the parser macro @var builds Var nodes for bound variables. Arithmetic/logical operators are represented as curried Apply nodes headed by UOp constructors. The pinned translation maps these to SmtTerm constructors.
2. Implement a separate Logos-Term renderer over RelationalQuery / Term, using the exact audited Eo constructors.
3. **A parser-state bridge is available without writing a second CPC parser.** The pinned Logos parser exposes parseCommands and its ParserM state type. ParserM is StateT (State T) (Except String), and parseCommands can be run with State.ofOps to retain the final State. The state contains ufCount and terms. A thin Lean wrapper can return the usual assumptions/commands plus this final state. For the strict QF_LIA subset, which has no declared datatypes, direct parseCommands can be used; its equivalence to the ordinary parseProof path must be checked for this subset.
4. Extract each declared symbol's UConst ID and sort from the final parser state. Reject duplicate/ambiguous bindings, wrong sorts, or missing expected names. This avoids a second parser and binds names to the exact IDs used by the CPC parser.
5. Implement a separate Logos-Term renderer over RelationalQuery / Term, using the exact audited Eo constructors.
6. In Lean, establish that the generated expected term has the intended SMT semantics.
7. Establish that the SMT-LIB renderer and Logos-Term renderer denote the same canonical query.
8. Bind parsed CPC assumptions to the expected Logos terms by exact structural equality.
9. Prove the product-program query corresponds to the typed LLMLang program semantics.
10. Bind source digests, renderer versions, solver/checker identities, and exact artifacts into a signed evidence manifest.
4. In Lean, establish that the generated expected term has the intended SMT semantics.
5. Establish that the SMT-LIB renderer and Logos-Term renderer denote the same canonical query.
6. Bind parsed CPC assumptions to the expected Logos terms by exact structural equality.
7. Prove the product-program query corresponds to the typed LLMLang program semantics.
8. Bind source digests, renderer versions, solver/checker identities, and exact artifacts into a signed evidence manifest.

Until these obligations are met, the output remains QF_LIA_CANDIDATE_QUERIES. Neither a solver UNSAT answer nor a Logos-checked CPC proof can yet become a program-level PROVEN result.

## 7. Next implementation step

Implement and build a small Lean wrapper around the public parseCommands API that preserves the final parser state. Derive the symbol-to-UConst map from that exact state, then build the expected Eo.Term tree and compare the complete parsed assumption list by native structural equality. Do not create a Python approximation of Lean structural equality and do not normalize parsed proof assumptions.


## 8. Pinned Logos API audit notes

The source audit was performed against commit cf18742973861b3718d04c5f25775448098ff474, not against an unpinned branch.

- Eo.Term includes Boolean, Numeral, UConst, Var, UOp, and Apply constructors.
- The parser's declare-const path calls declareSymbol; non-sort declarations are assigned sequential UConst IDs via mkUConst (ufCount + 1).
- The parser's @var macro constructs Term.Var (Term.String name) type for bound variables. It is not the representation used for declared SMT constants.
- The Eo-to-SMT translation maps Term.UConst to SmtTerm.UConst using the sequential identifier and mapped sort; Term.Boolean and Term.Numeral map to their corresponding SmtTerm literals.
- The audited operator mappings include ite, not, or, and, eq, plus, neg, mult, lt, and leq, represented by nested Term.Apply nodes headed by Term.UOp.
- Eo.parseProof returns the parsed top-level assumption list and proof command list. The public return value does not include the parser's name-to-UConst symbol table.

This means a Logos-Term renderer can build the expected formula structure, but it cannot safely assign UConst indices from query-IR declaration order unless the proof artifact's declaration sequence is independently shown to be identical. That is a proof-binding requirement, not a formatting detail.


## 9. Parser-state bridge sketch (not yet compiled)

The pinned parser exposes the following relevant contracts:

- ParserM T is StateT (State T) (Except String).
- parseCommands returns the parsed assumptions and command list.
- State stores ufCount and terms, where declared constants are represented by UConst nodes.
- parseProof currently uses run' internally and discards this final state.

A downstream Lean wrapper can preserve it by running parseCommands directly:

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

This is a source-level sketch only. It has not been compiled against the pinned Lean/Logos toolchain. The wrapper must reject unsupported datatype declarations and prove/test that, for the QF_LIA-only CPC subset, bypassing parseProof's datatype elaboration does not change parsed assumptions. The state-derived map must reject ambiguous repeated declarations rather than guessing which UConst a name denotes.
