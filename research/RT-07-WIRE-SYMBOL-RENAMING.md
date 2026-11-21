# RT-07 — Prove evaluation preservation under wire symbol renaming

**Date** · 2026-11-21

**Baseline** · `78b0627`

**Status** · Lean theorem and envelope integration for the typed part of SCW-32

## Question and boundary

Does changing internal symbols to the version-2 envelope's names change what the typed query denotes? The merged source-envelope gate binds submitted bytes to Lean output. It previously renamed symbols during serialization. This experiment separates a typed renaming stage, proves its relation to the evaluator and uses that stage to generate both encoded assumptions. [Source-owned envelope](RT-07-SOURCE-OWNED-QUERY-ENVELOPE.md) · [Scenario 34](RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md#76-qf_lia-admissibility-and-external-wirechecker-boundary)

| Approach | Trade-off |
|---|---|
| Rename inline while writing JSON | Shorter pipeline. A preservation proof must reason through both the name transformation and encoding. |
| Materialize a renamed typed term | Separates the evaluable term transformation from byte serialization. Adds a traversal and a distinct proof boundary. |
| Retain only internal names end to end | Avoids renaming when the downstream boundary can use those names. The existing version-2 convention expects explicit factor suffixes. |

## Checked result

For every typed lowered term and environment on renamed names, `eval_rename` proves that evaluation after renaming equals original evaluation under the pulled-back environment. The sort index stays fixed. The proof recurses through both the term and the ordered Boolean operand lists. The envelope's `wireTerm_preserves` specializes this theorem to the declaration-derived name map used by the serializer.

The production path in the research prototype checks that each occurrence has an exact name and sort binding and that the projected wire names are unique. It then emits the typed renamed term. The existing source-envelope controls pass, and the generated Int and Bool fixture envelopes match the pre-change bytes. The direct comparison checks bytes for those fixtures, while the theorem applies to typed renaming on all terms admitted by the representation.

The theorem integrates with the existing lowering theorem, which preserves the evaluator before renaming. It does not establish parser/decoder denotation preservation, mathematical injectivity of the concrete name scheme, or correctness of the final Logos representation. The concrete uniqueness check is operational evidence. Non-injective maps do not in general preserve satisfiability across arbitrary environments even though the pulled-back equality remains valid.

## Reproduction

Use Lean 4.36.0 with the pinned Logos dependency. From `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding` run:

```sh
lake build --fail-fast LLMLangLogosBinding
lake env lean -DwarningAsError=true --run SourceQueryEnvelopeTests.lean
```

[Typed renaming and proof](PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/QuerySymbolRenaming.lean) · [Envelope integration](PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SourceQueryEnvelope.lean)
