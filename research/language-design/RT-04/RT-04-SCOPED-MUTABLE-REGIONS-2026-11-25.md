# RT-04 exclusive mutable regions and scoped task lifetimes

**Date** 2026-11-25 · **Plan** §5.1 · **Issue** [#324](https://github.com/aivibeflow/LLMLang/issues/324)

A Rust owner holds seven bytes. Two independently provided ranges each name a start and length. The adapter checks arithmetic and bounds before borrowing, validates disjointness, and uses a safe slice split to create two exclusive mutable regions. Scoped threads update those regions and finish before the owner resumes. An empty region owns no bytes and can use the simpler single-region path.

| Outcome per optimization | Count |
| --- | ---: |
| Successful update | 748 |
| Successful update using both scoped worker threads | 252 |
| Out of bounds | 2,745 |
| Overlap | 477 |
| Machine arithmetic overflow | 2 |

Both optimization levels agree with the independent interval-set oracle on 7,944 outcomes and complete output arrays. Invalid ranges leave the owner unchanged. Native Rust rejects two overlapping mutable borrows, a detached thread borrowing the owner's local region, a borrowed return escaping a local owner, and a non-`Send` value moved to a scoped thread. Three Lean propositions check adjacent interval separation, the empty region and a concrete witness to overlap. One is axiom-free and the others use `propext` and `Quot.sound`.

The candidate combines exact dynamic disjointness with statically scoped mutable references. The owner can regain access after the tasks end. The fixture covers one contiguous Rust object and deterministic disjoint writes. Foreign aliasing, cancellation, asynchronous suspension, resource unwinding, memory models and production ownership rules remain open.

Reproduce with Rust 1.85.1, Lean 4.36.0 and CPython 3.12.14 on x86-64 Linux.

```bash
study=research/language-design/RT-04/SCOPED-MUTABLE-REGIONS-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two fresh builds and Lean replays reproduced the checked outcomes.
