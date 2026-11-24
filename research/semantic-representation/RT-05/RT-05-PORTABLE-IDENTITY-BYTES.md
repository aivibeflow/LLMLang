# RT-05 — Portable identity bytes for typed scalar values

**Date** · 2026-11-21

**Baseline** · `b0142c27f5632a859c379b78a10cb22f500ebfd8`

**Status** · Bounded cross-implementation evidence for [Plan §1.2](../../../PLAN.md#12-semantic-identity-hashes-and-canonical-encoding) and [LL-004](../../../TODO.md#ll-004--choose-canonical-encoding-and-hash-algorithm-policy)

## Question and candidate encodings

Does a typed value retain the same hash preimage across implementations with different integer and string representations? The existing example store sorts JSON object keys and accepts Python integers. Passing the same JSON numbers through JavaScript can round them before hashing. [Existing store](../../PROTOTYPES/DEPENDENCY-GRAPH-01/src/semantic_graph.py) · [RFC 8785, input constraints and property sorting](https://www.rfc-editor.org/rfc/rfc8785.html#section-3.2)

| Encoding | Trade-off |
|---|---|
| Restricted canonical JSON with interoperable numeric values | Familiar tooling and compact numbers. The semantic profile must limit integer range or encode wider integers by a separate type rule. |
| Tagged arrays with strict decimal integer strings | Makes the exact integer independent of numeric host types. Requires explicit tag, Unicode, map ordering and validation rules. Both encoders in this experiment implement this option. |
| Deterministic CBOR with defined integer and map rules | Can encode many integers more compactly. Requires decisions on bignum tags, map ordering, Unicode policy and rejection of alternate representations. No CBOR byte comparison was run. |

[CBOR deterministic encoding](https://www.rfc-editor.org/rfc/rfc8949.html#section-4.2)

## Profile and results

The fixture hashes compact UTF-8 JSON for an array containing a version marker, identity domain and typed payload. Integers are canonical decimal strings without a plus sign, leading zeros or signed zero. The profile retains the Unicode scalar sequence, rejects lone surrogates, preserves list order and sorts map keys by their UTF-8 bytes. Map inputs are pairs so duplicate keys remain visible to validation. Domain labels are distinct markers for the fixture. They make no selection of the payloads that ultimately define `OpHash`, `ImplHash`, `CCHash`, `CandidateSetHash`, contract or evidence identity. [Draft identity glossary](../../../draft/GLOSSARY.md)

The independently authored Python and Node encoders agreed in all 127 comparisons. Both accepted 116 inputs with identical bytes and SHA-256 digests and rejected 11. The corpus includes:

- The integers `9007199254740992` and `9007199254740993` remain distinct in every tested identity domain. A JavaScript JSON numeric parse collapses that pair under binary64. Large signed values and a 129-bit value also encode exactly.
- The composed and decomposed spellings of é remain distinct. Embedded controls and Unicode line separators produce the same bytes in both encoders. This experiment makes Unicode normalization explicit and does not choose an identifier normalization rule.
- All six permutations of a three-key map agree. U+FFFF precedes U+10000 under the fixture's UTF-8 order. The result distinguishes that order from a JavaScript UTF-16 code-unit sort.
- Reversing a list changes its bytes. A duplicate key, lone surrogate, invalid tag and noncanonical integer spelling each fail admission.

The tested vector favors an exact typed preimage where the language permits integers beyond binary64 and keeps Unicode scalar strings. Choosing a canonical encoding still requires an explicit schema, limits on input size and depth, digest algorithm migration, and integration with the graph identity policies. This corpus covers no links, floats, unions, cyclic graphs or production hashing. [Dependency map](../../RESEARCH-DEPENDENCY-MAP.md)

## Reproduction

From the repository root use CPython 3.12.14 and Node v24.22.1.

```sh
python -B research/semantic-representation/PROTOTYPES/IDENTITY-BYTES-01/compare.py
```

The operation-domain digest for the exact integer `9007199254740993` is `af27415078465aba13b39e03a2b98c7a20f9eeb20acbca6105333f8a2d442dee`. [Comparison harness](../PROTOTYPES/IDENTITY-BYTES-01/compare.py) · [Node encoder](../PROTOTYPES/IDENTITY-BYTES-01/encode.mjs)
