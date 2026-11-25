# RT-06 — Guarded dependency discovery from typed SPG

A source call occurrence, an observed target and a covered may-depend set provide different evidence. This study compares all three on an exact typed SPG corpus. It extends [conditional closure](RT-06-CONDITIONAL-DEPENDENCY-CLOSURE-2026-11-25.md) and [dependency evidence classes](RT-06-DEPENDENCY-EVIDENCE-CLASSES-2026-11-25.md) for [PLAN §3.1](../../../PLAN.md#31-semantic-dependency-model) and [#298](https://github.com/aivibeflow/LLMLang/issues/298).

Each program takes an integer and a Boolean gate. If the gate is true, an equality test chooses an abstract call to alpha or beta. If the gate is false, another equality test chooses an exact pin to gamma or an abstract call to beta. Each provider returns a distinct tagged trace and a checked integer expression. Two beta sites share one operation while keeping two different paths. The typed SPG retains exact call mode, occurrence path, guard conjunction, binding and resolved implementation.

| Discovery route | What the experiment checks |
| --- | --- |
| Source syntax | Extract direct and operation call occurrences from the admitted source grammar. Use the result as an inventory of potential sites. |
| Typed SPG | Resolve each reference through its exact implementation pin or the selected binding. Derive each call's guard by following its typed condition paths. |
| Execution and tests | Use exact selected traces as positive witnesses at each executed input. An unobserved provider can still be reachable in other admitted inputs. |
| Formal semantics | Prove that the selected provider is exactly the one whose guard is enabled. A partially unknown gate expands locally to both Boolean possibilities while preserving the known integer tests. |

Lean checks guard equivalence for arbitrary integer thresholds and inputs in the model. It also checks that the expanded gate includes the provider from the actual choice. Both statements depend only on `propext`. The runner separately checks 250 concrete Lean selections against the admitted compiled SPG traces and independent arithmetic. A theorem about the selection model depends on the source and typed-IR decoding for its applicability to a concrete program.

## Results

All 25 compiled bodies retain the 100 expected call occurrences. All 250 executions match the typed guard projection, result and exact provider trace. The request corpus crosses each body with every nonempty subset of five integers and three gate profiles. Guarded sets agree with complete concrete replay in all 2,325 cases.

| Weaker policy | Cases with an error or avoidable ambiguity |
| --- | ---: |
| Keep every statically visible provider | 2,090 cases with extra providers and zero omissions |
| Keep only the first observed provider | 1,310 cases with missing providers |
| Treat an unknown gate as false | 420 cases with missing providers |

At one fixed integer input, both equality guards can hold. The unknown Boolean can select alpha or gamma. A false-only fallback retains gamma and omits alpha. Expanding the unknown value preserves both possibilities without introducing the beta branch when its known equality guard excludes it.

The candidate may-depend graph can retain all syntactically admitted targets as a fallback. It can shrink the result when checked constraints cover branch outcomes for the exact admitted domain. The verifier needs a complete typed site inventory, reliable predicate correspondence and exact selected bindings before treating absence as evidence. The finite corpus leaves higher-order dispatch, recursion, effectful guards, partial evaluation failures and source-to-SPG correspondence for general programs open. [DEP-010 and DEP-011](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register)

## Reproduce

Use Git 2.56.1, CPython 3.12.14 and Lean 4.36.0 at `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`. Run from the repository root with archive commit `22d607ba6f24ff187877a2da500892a3fc2b043b`. The [ledger](SPG-GUARDED-DISCOVERY-01/evidence.json) records the corpus digest, Lean source digest, request comparisons and concrete missed-provider witnesses.

```sh
set -eu
fixture=research/semantic-representation/RT-06/SPG-GUARDED-DISCOVERY-01
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
lean -DwarningAsError=true "$fixture/Guard.lean" > "$out/axioms.txt"
cmp "$fixture/axioms.txt" "$out/axioms.txt"
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > "$out/evidence.json"
cmp "$fixture/evidence.json" "$out/evidence.json"
```
