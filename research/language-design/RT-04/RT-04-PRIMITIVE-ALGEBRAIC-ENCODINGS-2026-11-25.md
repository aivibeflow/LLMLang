# RT-04 primitive validity and algebraic representation

**Date** 2026-11-25 · **Plan** §5.1 · **Issue** [#324](https://github.com/aivibeflow/LLMLang/issues/324)

Lean checks that distributing `Bool × (Unit ⊕ α)` into `Bool ⊕ (Bool × α)` has a two-sided inverse. It also checks elimination of an uninhabited `Empty` alternative, Boolean encoding round trips, and refusal of raw Boolean values above one. Four propositions have no axioms. The invalid-flag arithmetic proof uses only `propext` and `Quot.sound`.

The native experiment instantiates `α` as an unsigned 8-bit value. One 16-bit representation uses an outer Boolean field and an inner presence tag. The other uses a top-level sum tag and places the Boolean alongside each branch payload. A rank over the 514 logical values provides an independently enumerated comparison. The decoder checks the exact tag and required unused bits before returning a rank.

| Decoder result across each full 16-bit corpus | Count |
| --- | ---: |
| Valid raw Boolean values | 2 |
| Valid raw byte values | 256 |
| Valid words for each algebraic representation | 514 |
| Words accepted by both algebraic decoders | 258 |
| Shared words with different meanings | 256 |

The same word 512 represents a true Boolean with the unit alternative in the product-first encoding and a false Boolean with byte zero in the sum-first encoding. GCC and Clang at two optimization levels match the exact independent oracle across all 1,048,576 decoder checks. Both encoders round-trip every logical value within their declared profile.

A candidate type layer can distinguish source value validity, algebraic conversion and target representation. An explicit conversion can preserve the logical value under the checked isomorphism. Reinterpreting raw shared words can change the value. A production LLMLang primitive and type grammar, general foreign validity and ABI compatibility remain open.

Reproduce with GCC 14.2.0, Clang 19.1.7, Lean 4.36.0 and CPython 3.12.14 from the repository root. `GCC`, `CLANG` and `LEAN` can identify the direct executable paths.

```bash
study=research/language-design/RT-04/PRIMITIVE-ALGEBRAIC-ENCODINGS-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two fresh sets of shared objects and kernel checks produced byte-identical evidence.
