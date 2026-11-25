# RT-10 two-location atomic observations and total order

**Date** 2026-11-25 · **Plan** §5.2 · **Issue** [#325](https://github.com/aivibeflow/LLMLang/issues/325)

Two C workers each store one to their own initially zero atomic location and then read the other worker's location. Tests synchronize the setup and collection of each iteration. The workers run on distinct permitted CPUs. Three runs per compiler and memory-order profile exercise relaxed, release/acquire and sequentially consistent memory orders.

An independent enumeration of the four operations admits six total orders that respect each worker's program order. Their possible read pairs are `01`, `10` and `11`. Both reads seeing zero would require each to precede the other worker's write, which creates a cycle with the two program orders. Lean proves this contradiction without axioms. A separate checked proposition records that older reads supply no corresponding release/acquire edge in this model.

| Profile | First native batch, both reads zero | Fresh native batch, both reads zero | Trials per batch |
| --- | ---: | ---: | ---: |
| Relaxed | 15 | 32 | 300,000 |
| Release/acquire | 7 | 26 | 300,000 |
| Sequentially consistent | 0 | 0 | 300,000 |

Each batch contains 18 native processes and 900,000 trials across GCC 14.2.0 and Clang 19.1.7. The raw counts vary with scheduling. Both batches reproduce the same finite-order ledger and show the two-old-value outcome under both weaker profiles. Sequential consistency is checked against the exact enumeration. Two independent release/acquire pairs can read the initial state. Those reads do not supply a cross-thread release/acquire edge for the current writes.

This evidence covers one store-buffering litmus on Linux x86-64 and the explicitly enumerated total-order fragment. Portable LLMLang memory semantics, litmus scope beyond these atomics, target coverage and stronger compiler correspondence remain open.

Reproduce with GCC, Clang, Lean 4.36.0 and Python on x86-64 Linux with at least two permitted CPUs.

```bash
study=research/runtime-and-systems/RT-10/ATOMIC-STORE-BUFFERING-01
python "$study/run.py" --exact /tmp/llmlang-atomic-exact.json --native /tmp/llmlang-atomic-native.json
cmp "$study/evidence.json" /tmp/llmlang-atomic-exact.json
```
