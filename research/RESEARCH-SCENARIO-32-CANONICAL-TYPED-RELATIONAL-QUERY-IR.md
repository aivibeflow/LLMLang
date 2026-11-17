# Research Scenario 32 — Canonical Typed Relational Query IR

**Status:** Python typed query IR, SMT-LIB renderer, and deterministic version-1 JSON exporter implemented; 27 focused Python tests and compileall pass in CI. Lean typed query AST, independent Logos Eo.Term renderer, parser-state declaration binding, and strict version-1 JSON decoder compile and pass all 13 executable test groups in CI (run 44095462826, commit 7f6e0d5). Source-to-query correspondence remains unproved.  
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

Latest confirmed focused run: **27 tests passed**. Python compileall passed. The tests were executed locally against a compatibility fixture reproducing the repository's formal_core AST dataclasses and exception interface; a full repository checkout and full prototype suite were not available. No cvc5 solver or Logos checker was invoked.

## 6. Remaining obligations

The following pieces are implemented, but their coverage and proof strength must not be overstated:

- The pinned Logos source API has been audited.
- The Lean parser-state bridge retains the final declaration state and compares assumptions with ordinary `Eo.parseProof` on the current fixtures.
- The declaration binder resolves names to exact parser-assigned UConst nodes and rejects duplicate, extra, missing, ambiguous, and wrong-sort declarations.
- A typed Lean query AST and independent Eo.Term renderer compile.
- Native structural equality tests pass for reflexive equality, a compound arithmetic expression, and a compound Boolean expression.

Remaining work:

1. Expand exact structural AST tests across every accepted constructor and edge case, including subtraction, unary negation, ite, and multi-operand Boolean forms.
2. Establish parser-path equivalence for the entire accepted CPC subset, not only the current fixtures; explicitly reject declarations and command forms outside that subset.
3. Implement a strict Lean-side decoder for the canonical typed query IR, with schema, sort, declaration, and operator validation. The decoded source names must be resolved only through the parser-state-derived bindings.
4. Prove in Lean that the generated expected Eo.Term has the intended SMT semantics.
5. Establish that the Python SMT-LIB renderer and Lean Logos-Term renderer denote the same canonical query.
6. Bind the complete parsed CPC assumption list to the expected terms by native structural equality.
7. Prove the product-program query corresponds to the typed LLMLang program semantics.
8. Bind source digests, renderer versions, solver/checker identities, and exact artifacts into a signed evidence manifest.

Until these obligations are met, the output remains QF_LIA_CANDIDATE_QUERIES. Neither a solver UNSAT answer nor a Logos-checked CPC proof can yet become a program-level PROVEN result.

## 7. Next implementation step

The parser-state wrapper, exact declaration binding, typed Lean query AST, and independent Eo.Term renderer are implemented and CI-validated. A strict Lean decoder for the versioned canonical JSON envelope has now been added. It enforces exact field sets, typed atoms, exact operator arities, identifier syntax, declaration uniqueness, and the linear-multiplication restriction. Adversarial fixtures cover malformed leaf atoms, empty symbols, non-null operator atoms, invalid factor/declaration identifiers, unknown schema versions, unknown fields, and nonlinear multiplication. The latest CI result for these additions is successful: [GitHub Actions run 44095462826](https://github.com/aivibeflow/LLMLang/actions/runs/44095462826), commit `7f6e0d552c42a1749db58a88e819d132cab51c0f`. The tested trust boundary is: decode independently in Lean, resolve declarations only through parser-state-derived UConst bindings, then compare the complete parsed assumption list by native structural equality. The test suite covers the listed fixtures and constructors; it is not an exhaustive proof of parser equivalence or semantic correspondence. Do not create a Python approximation of Lean structural equality and do not normalize parsed proof assumptions.


## 8. Pinned Logos API audit notes

The source audit was performed against commit cf18742973861b3718d04c5f25775448098ff474, not against an unpinned branch.

- Eo.Term includes Boolean, Numeral, UConst, Var, UOp, and Apply constructors.
- The parser's declare-const path calls declareSymbol; non-sort declarations are assigned sequential UConst IDs via mkUConst (ufCount + 1).
- The parser's @var macro constructs Term.Var (Term.String name) type for bound variables. It is not the representation used for declared SMT constants.
- The Eo-to-SMT translation maps Term.UConst to SmtTerm.UConst using the sequential identifier and mapped sort; Term.Boolean and Term.Numeral map to their corresponding SmtTerm literals.
- The audited operator mappings include ite, not, or, and, eq, plus, neg, mult, lt, and leq, represented by nested Term.Apply nodes headed by Term.UOp.
- Eo.parseProof returns the parsed top-level assumption list and proof command list. The public return value does not include the parser's name-to-UConst symbol table.

This means a Logos-Term renderer can build the expected formula structure, but it cannot safely assign UConst indices from query-IR declaration order unless the proof artifact's declaration sequence is independently shown to be identical. That is a proof-binding requirement, not a formatting detail.


## 9. Parser-state bridge sketch (superseded by compiled prototype)

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

This source-level sketch is superseded by the compiled implementation in `PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/`. CI currently verifies agreement between the state-preserving parser path and ordinary `Eo.parseProof` on the exercised fixtures, and checks exact state-derived bindings. The current tests do not yet constitute exhaustive equivalence over the full accepted QF_LIA CPC grammar.


## 10. Canonical JSON wire envelope (version 1)

The Lean decoder now defines the intended interchange shape. The envelope is UTF-8 JSON with exactly these top-level fields:

- `schema`: the literal `llmlang.qf_lia.relational-query/1`;
- `factor`: non-empty source-level factor name;
- `declarations`: array of objects with exactly `name` and `sort` (`Int` or `Bool`);
- `factor_difference` and `observations_differ`: recursively typed term objects;
- `observation_contract`: non-empty contract identifier.

Every term object has exactly `op`, `sort`, `args`, and `atom`. Literal and symbol nodes use an integer, Boolean, or string atom respectively and an empty argument array. Composite nodes use `atom: null`. The decoder rejects unknown/missing fields, unknown schema versions and operators, wrong sorts, malformed arities, duplicate declarations, invalid identifiers, malformed leaf atoms, non-null composite-node atoms, and nonlinear multiplication. It does not coerce values.

This is a wire-format contract for the Lean decoder, not yet a complete Python exporter or a formal proof that the Python producer emits only valid documents. The decoder must be exercised by CI with positive and adversarial fixtures before this boundary is treated as validated.


## 11. Current CI evidence and semantic boundary

The Lean workflow succeeded on commit `7f6e0d552c42a1749db58a88e819d132cab51c0f`:

- [Logos CPC parser-state binding — run 44095462826](https://github.com/aivibeflow/LLMLang/actions/runs/44095462826).
- Lean 4.34.0 and the pinned Logos dependency resolved successfully.
- The `LLMLangLogosBinding` library built successfully.
- All executable test groups 1–13 passed, including exact AST fixtures, canonical JSON decoding, malformed atom/identifier rejection, unknown fields/schema rejection, and nonlinear multiplication rejection.

The separate Python workflow succeeded with 27 focused tests and `compileall`:
[Strict QF_LIA profile — run 44089075437](https://github.com/aivibeflow/LLMLang/actions/runs/44089075437).

These results establish implementation-level regression evidence only. In particular, they do **not** establish:
- a semantics-preserving translation from the actual LLMLang source AST to the relational query;
- equivalence between the Python SMT-LIB renderer and Lean's Logos-Term renderer for all accepted inputs;
- formal correctness of the Logos parser or cvc5;
- a program-level `PROVEN` result.

The next proof milestone is specified in [Scenario 34 — Source-to-Query Semantic Correspondence](RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md). Scenario 34 deliberately separates expression translation, command execution, paired execution, and query validity so that a proof for a smaller fragment cannot accidentally be presented as a proof for the whole program.
