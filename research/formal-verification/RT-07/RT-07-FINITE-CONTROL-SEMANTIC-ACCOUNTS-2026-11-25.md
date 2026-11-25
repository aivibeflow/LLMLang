# RT-07 — Operational, denotational and axiomatic accounts of finite control

This study extends the [deterministic state and Result comparison](RT-07-THREE-SEMANTICS-STATE-RESULT-2026-11-25.md) with nondeterministic control and infinite execution. It checks the distinctions a proposed reference semantics and a proof interface need to carry for [PLAN §2.1](../../../PLAN.md#21-formal-semantics-of-the-language) and [#293](https://github.com/aivibeflow/LLMLang/issues/293).

A program has three internal locations and two distinct tagged terminal locations. Each internal location independently chooses any subset of the five locations as successors. A finite path ends with return, error or deadlock. A path that keeps taking steps forever has the divergence observation. Error and deadlock are finite observations that a postcondition may admit or forbid. An empty successor set emits deadlock explicitly. The choice model quantifies over every successor and permits every infinite path, including one that keeps ignoring an available exit.

| Account | Construction | Use in this fragment |
| --- | --- | --- |
| Operational | Explore successor paths from one location. A path reaching an ancestor records possible divergence. | Enumerate observations and obtain a path witnessing an unwanted outcome. |
| Denotational | Grow the least fixed point of finite observation sets and shrink the greatest fixed point of locations with an infinite suffix. | Recover all observation classes from compositional successor equations. |
| Axiomatic | Apply the same backward rule at each location. A nonempty branch requires every successor's judgment. Finite stops test the selected postcondition. | Calculate total satisfaction as the least fixed point and liberal satisfaction as the greatest fixed point. |

The least denotational iteration accumulates finite observations reachable within a growing path length. The greatest divergence iteration retains locations admitting a path of the corresponding length. In a finite graph, a repeated location on such a path yields a reachable cycle and hence an infinite execution. In the backward account, starting internal locations at false derives a total judgment only when every path finishes with an allowed tag. Starting at true removes locations that can reach a forbidden finite stop. Liberal satisfaction can therefore hold even when an allowed or forbidden finite stop is never reached along some infinite path.

Lean checks that backward conjunction in a finite unfolding agrees with universally checking the reachable leaves. It also checks that total satisfaction is equivalent to liberal satisfaction and absence of an unfinished leaf. Both proofs have an empty axiom list. The finite graph runner checks the fixed-point and unbounded-path correspondence across the stated graph family. The Lean statements concern finite unfoldings, and the graph correspondence argument above is an additional finite-graph argument.

## Results

| Check | Count |
| --- | ---: |
| Graphs | 32,768 |
| Starting location comparisons, operational against denotational | 98,304 |
| Postcondition comparisons against each backward account | 786,432 |
| Liberal judgments accepted in the presence of divergence and rejected by total satisfaction | 239,631 |
| Return/error-only judgments accepted despite a forbidden reachable deadlock | 19,290 |

All comparisons between accounts matched. The postcondition corpus uses every subset of the three finite tags, including the empty postcondition. With a return-only postcondition, a location that may return or take a self-loop passes the liberal judgment and fails the total one. A location that may return or reach a deadlock fails both. Adding deadlock to that postcondition admits both. A lone error fails both under the return-only predicate. The [finite ledger](CONTROL-SEMANTIC-ACCOUNTS-01/evidence.json) includes all four controls and a digest of the complete ordered comparison rows.

Together with the deterministic pilot, the results support comparing candidate rules in three forms before extending the core. For control with possible divergence, a receipt should identify the fixed-point interpretation and the treatment of finite error and deadlock. Concrete scheduler policies, fairness, infinite observable traces, state carried across branches and correspondence to source programs remain open.

## Reproduce

Use CPython 3.12.14 and Lean 4.36.0 at commit `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`. Run from the repository root.

```sh
set -eu
fixture=research/formal-verification/RT-07/CONTROL-SEMANTIC-ACCOUNTS-01
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
lean -DwarningAsError=true "$fixture/Accounts.lean" > "$out/axioms.txt"
cmp "$fixture/axioms.txt" "$out/axioms.txt"
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > "$out/evidence.json"
cmp "$fixture/evidence.json" "$out/evidence.json"
```
