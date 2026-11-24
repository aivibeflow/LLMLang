# Kernel-checking the Logos model witness

- **Date:** 2026-11-24
- **Research:** RT-07, RT-36, Scenario 34 (SCW-34)
- **Baseline:** `4b253db7152d58d3859e159fbc3f868fbfd28a77`
- **Evidence:** Same-statement proof replacement and exact Lean axiom comparison

Replacing the proof of empty-regular-language canonicity with `rfl` removes the extra upstream native-computation axiom from LLMLang's model-existence theorem. The pinned Logos revision with its published proof still carries that dependency. A version with the kernel proof can discharge the well-formed-model premise of the scalar source-refutation theorem using standard Lean axioms.

| Model witness | Axioms of `exists_wellFormed_agreeing_model` |
| --- | --- |
| Published Logos proof | `propext`, `Classical.choice`, `Quot.sound`, and `Smtm.native_re_canonical_none._native.native_decide.ax_1_1✝` |
| Temporary rebuild with the kernel proof | `propext`, `Classical.choice`, `Quot.sound` |

The experiment changes the body of `native_re_canonical_none` while preserving its statement and `simp` attribute. It rebuilds `Common`, `Support`, `Model`, and `Nonvacuity` under the pinned Logos verification package's Lean arguments. It then checks the exact LLMLang [model-extension fixture](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/upstream-model/LogosModelExtension.lean) against those modules. The other four reported theorems have the same axioms in both builds, including the control in which name-only lookup violates model typing. The temporary build leaves the upstream checkout and compiled `TypePreservation` module hashes unchanged.

## Reproduce

Use Logos `cf18742973861b3718d04c5f25775448098ff474`, Lean 4.34.0 (`293d5d0c0c3f3dded4688b3ccd6a33939ac5102b`) and Mathlib `5ed2965256430c3649e86755f9576b54eca72435`. Compare both exact output ledgers from the [replay](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/upstream-model/replay.py).

```sh
fixture=research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding
output=$(mktemp -d)
python3 -B "$fixture/upstream-model/replay.py" --checkout /path/to/pinned/logos --model-extension > "$output/published.txt"
python3 -B "$fixture/upstream-model/replay.py" --checkout /path/to/pinned/logos --kernel-model-extension > "$output/kernel.txt"
cmp "$fixture/evidence/logos-model-extension/axioms.txt" "$output/published.txt"
cmp "$fixture/evidence/logos-kernel-model-witness/axioms.txt" "$output/kernel.txt"
```

Upstream acceptance or an LLMLang dependency decision is still required to use the replacement outside this replay. The [source-refutation theorem](RT-07-LOGOS-SOURCE-REFUTATION-COMPOSITION-2026-11-24.md) also requires the independently audited full-rule verdict theorem. Its proof dependencies and the correspondence to the runtime checker remain separate from the model witness.
