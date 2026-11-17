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

1. Audit the exact Logos Term and sort constructors at the pinned Logos revision.
2. Implement a separate Logos-Term renderer over RelationalQuery / Term.
3. In Lean, establish that the generated expected term has the intended SMT semantics.
4. Establish that the SMT-LIB renderer and Logos-Term renderer denote the same canonical query.
5. Bind parsed CPC assumptions to the expected Logos terms by exact structural equality.
6. Prove the product-program query corresponds to the typed LLMLang program semantics.
7. Bind source digests, renderer versions, solver/checker identities, and exact artifacts into a signed evidence manifest.

Until these obligations are met, the output remains QF_LIA_CANDIDATE_QUERIES. Neither a solver UNSAT answer nor a Logos-checked CPC proof can yet become a program-level PROVEN result.

## 7. Next implementation step

Implement the Logos-Term renderer only after verifying the exact pinned Logos API types and constructors. Keep it as a separate module and test it against golden Lean terms. Do not create a Python approximation of Lean structural equality and do not normalize parsed proof assumptions.
