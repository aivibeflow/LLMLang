# RT-11 — Non-interference with three concurrent edits

A pairwise impact check can miss an effect that only appears when three independently valid changes are combined. This study extends the [two-edit non-interference comparison](RT-11-COMPOSED-NONINTERFERENCE-2026-11-25.md) for [PLAN §3.2](../../../PLAN.md#32-incremental-analysis-and-invalidation) and [#299](https://github.com/aivibeflow/LLMLang/issues/299).

Three edits toggle three distinct Boolean fields. The observation comes from an independently enumerated truth table. It can depend on any field or combination of fields. An impact plan may promise preservation after a specific schedule or preservation after every admitted observation prefix. Each such claim binds the baseline, any intermediate edit state and the exact requested observation.

| Gate | Scope |
| --- | --- |
| Independent edit checks | Compare each single edit against the baseline. |
| Pairwise checks | Compare every single edit and every pair against the same baseline. |
| Ordered plan with exact intermediate evidence | Compute the exact state and compare its observation after each step in the chosen order. |
| Order-independent preservation | Check all reachable subsets, or prove an invariant preserved by every edit that makes the required observation stable. |

Lean proves that an invariant and exact observation equality compose across an arbitrary finite edit list. The proof requires each edit to preserve the invariant and the required observation from every admissible intermediate state. Lean also checks a three-input conjunction witness. Each pair preserves false at an all-false baseline. Applying all three makes the observation true. The three declarations have empty axiom lists.

## Results

The runner enumerates all 256 Boolean observation tables, eight baselines and six orders for the three edits. An independent XOR endpoint calculation agrees with all 12,288 ordered schedules. The reachable-subset check agrees with checking every schedule prefix.

| Result | Profiles |
| --- | ---: |
| All truth tables and baselines | 2,048 |
| Single-edit gate admits | 256 |
| Of those, the final combined observation changes | 128 |
| Pairwise gate admits | 32 |
| Of those, the final combined observation changes | 16 |
| At least one schedule preserves every prefix | 736 |
| Every schedule preserves every prefix | 16 |
| Some schedules preserve every prefix and some change it | 720 |

An individually validated edit can lose applicable evidence when another edit changes its input. The candidate planning gates therefore bind the approved order and revalidate a changed intermediate subject, or use a checked invariant that covers all admitted orders. Limiting a claim to atomic final publication can reduce the required scope when intermediate states are unobservable. That assumption belongs in the declared contract.

The experiment covers finite total data updates with independent writes. General source dependency discovery, checked merge correspondence, partial failure and asynchronous execution remain open. [DEP-011](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register)

## Reproduce

Use CPython 3.12.14 and Lean 4.36.0 at `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9` from the repository root. The [ledger](THREE-EDIT-INTERFERENCE-01/evidence.json) records the exact corpus counts, proof inputs and ordered-row digest.

```sh
set -eu
fixture=research/toolchain-and-collaboration/RT-11/THREE-EDIT-INTERFERENCE-01
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
lean -DwarningAsError=true "$fixture/Noninterference.lean" > "$out/axioms.txt"
cmp "$fixture/axioms.txt" "$out/axioms.txt"
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > "$out/evidence.json"
cmp "$fixture/evidence.json" "$out/evidence.json"
```
