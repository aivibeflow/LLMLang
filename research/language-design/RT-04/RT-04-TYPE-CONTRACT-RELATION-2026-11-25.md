# RT-04 provider type compatibility and separate behavior guarantees

**Date** 2026-11-25 · **Plan** §5.1 · **Issue** [#324](https://github.com/aivibeflow/LLMLang/issues/324)

A separately compiled Rust client requests a provider whose associated return type is `Ticks`. Five providers expose an unsigned 16-bit physical result. Two transparent wrapper types represent distinct logical units with the same measured size and alignment. The typed Rust client admits four providers and refuses the `Millis` provider. A C-ABI test caller can observe the raw scalar from all five. This is an explicit fixture boundary.

For the common typed interface, the pointwise contract requires `x ≤ result ≤ x + 32`. The stronger relational claim is monotonicity across two calls at ordered inputs.

| Provider | Typed admission | Pointwise refusals out of 256 | Monotonicity violations out of 32,896 pairs |
| --- | --- | ---: | ---: |
| Identity in ticks | Accepted | 0 | 0 |
| Constant offset in ticks | Accepted | 0 | 0 |
| Alternating offset in ticks | Accepted | 0 | 753 |
| Out-of-range offset in ticks | Accepted | 256 | 0 |
| Different unit in milliseconds | Refused | 223 on the raw route | 0 on the raw route |

At two optimization levels, 2,048 typed client calls and 2,560 raw C-ABI calls agree with their independent expected values. The sound typed consumer refuses the unit mismatch even though both layouts occupy two bytes with alignment two. Seven Lean propositions establish range and order properties of the mathematical models or give concrete witnesses against them. Four proofs are axiom-free. The remaining audit reports only `propext`, `Classical.choice` and `Quot.sound` where required.

Type admission checks the logical result type. A pointwise contract checks its requested behavior. A relational proof checks the property across calls when the relevant semantics and assumptions are available. The instrumented model and runtime corpus are exact for these simple providers. Source and foreign ABI semantics across toolchains, production type and provider identities, and general proof-to-native correspondence remain open.

Reproduce with Rust 1.85.1, Lean 4.36.0 and CPython 3.12.14 on x86-64 Linux.

```bash
study=research/language-design/RT-04/TYPE-CONTRACT-RELATION-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two clean builds and kernel replays reproduced the ledger byte for byte.
