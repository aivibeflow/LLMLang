# RT-07 — Check a refutation through the source-owned wire path

**Date** · 2026-11-21

**Baseline** · `7aaf83a`

**Status** · Executable end-to-end fixture for SCW-31–34 in [Plan §2.3](../PLAN.md#23-lean-logos-smt-and-solver-integration)

## Question

Which independent checks are needed to treat solver output as evidence about a typed source program? An independently checked proof establishes a result about its parsed assumptions. To use it for source reasoning, those assumptions also need to represent the intended source formula. The merged version-2 encoder builds its exact envelope from the typed program, observation contract and selected factor. This experiment connects that boundary to the existing CPC assumption validator and Logos verdict. [Source-owned query envelope](RT-07-SOURCE-OWNED-QUERY-ENVELOPE.md) · [Formal verification architecture](LLMLang-FORMAL-VERIFICATION.md)

## Check stages and observations

1. Reconstruct the source-owned envelope and require exact submitted bytes.
2. Bind the parser declarations and compare both ordered CPC assumptions to the decoded wire query.
3. Ask Logos to check the same proof text, and require the complete `correct` verdict.

The fixture preserves the failing stage in its result. A parse error, an incompatible source query and an incomplete verdict are distinct outcomes. The parser-state path already checks that its retained assumptions agree with ordinary Logos parsing.

| Control | Result |
|---|---|
| Constant program, its exact envelope and a flat valid CPC proof | All three checks pass. |
| Exact envelope and matching assumption list with no derivation | Source and assumption checks pass. Logos returns incorrect. |
| Substitute false in the envelope and supply a valid proof of it | The submitted envelope and proof agree. Logos accepts that proof independently. The source-owned byte check rejects the pair. |
| Keep the correct envelope and substitute the wrong proof | Source binding passes. Exact assumption comparison rejects. |
| Regenerate the envelope for a program returning the input and replay the constant-program proof | The new source envelope passes. The old proof fails assumption binding. |

## Evidence boundary

This is an end-to-end executable witness for one typed source program, the compact version-2 wire profile and a flat CPC derivation. The Lean source-to-query theorems and declaration closure establish earlier parts of the chain. Comparison and verdict routines are executed against the pinned decoder, parser and Logos implementation. General denotation preservation through serialization and final Logos rendering, supported alias profiles, authenticated transport metadata and production solver limits remain open. The fixture does not treat solver text, incomplete verdicts or a valid proof of a different query as source evidence.

## Reproduction

Use Lean 4.36.0 and the pinned Logos revision. From `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding` run:

```sh
lake build --fail-fast LLMLangLogosBinding
lake env lean -DwarningAsError=true --run SourceWireRefutationTests.lean
lake env lean -DwarningAsError=true --run SourceQueryEnvelopeTests.lean
```

Both sets of controls passed. [Acceptance check](PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SourceWireRefutation.lean) · [Executable proofs and controls](PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SourceWireRefutationTests.lean)