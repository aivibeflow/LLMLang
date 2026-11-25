# RT-04 refinement and dependent result boundaries

**Date** 2026-11-25 · **Plan** §5.1 · **Issue** [#324](https://github.com/aivibeflow/LLMLang/issues/324)

A bounded value starts below its source limit and is advanced by a nonnegative offset. Lean checks exact conversion between `Fin n` and the refinement `{x : Nat // x < n}`. A dependent result at index `n + offset` can always hold the mathematical output. Another proof identifies when the original index fails. A checked witness crosses the largest unsigned 16-bit value while staying within the dependent natural-number index. All four propositions are axiom-free.

Rust 1.85.1 checks an opaque `Below<N>` type across a separate provider library and client. The smart constructor checks the input bound. The transition computes a checked 16-bit sum and then validates the chosen destination bound. Separate attempts to forge the private wrapper, assign a value with the wrong index, and use an unrestricted generic constant arithmetic expression are rejected at both optimization levels.

| Runtime disposition per optimization | Count |
| --- | ---: |
| Accepted exact value | 3,732 |
| Source bound refused | 12,294 |
| Arithmetic overflow refused | 874 |
| Destination bound refused | 650 |

Both builds agree across 35,100 observations. The independent oracle checks the source range, exact arithmetic and destination range in that order. A wrapping-add comparator would admit 863 overflowing requests per build after the wrapped value fell below the destination limit.

Source validity, the relationship between indices, and the representability of the computed value require distinct proof obligations. A checked abstract refinement can be transported through an exact conversion. A dependent natural-number guarantee needs a separate checked representation obligation at a fixed-width native boundary. The candidate covers immutable values and one operation. General language inference, machine arithmetic lowering, effectful refinement and foreign admission remain open.

Reproduce with Rust 1.85.1, Lean 4.36.0 and CPython 3.12.14 from the repository root.

```bash
study=research/language-design/RT-04/DEPENDENT-BOUNDARY-VALUES-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two independent replays reproduced the exact result and proof ledgers.
