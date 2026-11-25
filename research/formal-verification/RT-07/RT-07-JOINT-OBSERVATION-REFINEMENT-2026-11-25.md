# RT-07 — Joint observations and contextual refinement

This study defines a refinement test for sets of complete observations, and checks which guarantees survive observation projection. It extends the [finite nondeterministic refinement pilot](RT-07-NONDETERMINISTIC-REFINEMENT-2026-11-25.md) and the [declared observation profile](RT-07-DECLARED-OBSERVATION-PROFILE-2026-11-25.md) for [PLAN §2.1](../../../PLAN.md#21-formal-semantics-of-the-language) and [#293](https://github.com/aivibeflow/LLMLang/issues/293).

Model a reference and a candidate by their sets of possible complete observations under the same initial state and environment. A candidate refines the reference if every candidate observation belongs to the reference set. Equivalence requires inclusion in both directions. These definitions give a may-observation refinement and an extensional equivalence. Liveness claims depend on the recorded outcomes, such as whether divergence or deadlock is an observation. Additional context behavior must be represented and checked explicitly.

A declared projection maps one complete run to one observation. Applying the same projection to every run always preserves a refinement. Projected refinement also implies refinement as seen by a downstream observer exactly when that observer takes the same value on all runs with the same projected observation. Lean proves both statements. In the forward direction of the second theorem, singleton run sets force any two runs with equal projections to agree in the downstream observer. In the reverse direction, the reference observation that witnesses projected inclusion also has the candidate's downstream result.

When several fields matter together, project them as a tuple per run. Comparing each field's possible values independently can discard the correlation. For example, consider a candidate that may return after writing or fail with no write and a reference that may return with no write or fail after writing. Their separate tag and write marginals agree. The observer checking whether a return and a write occurred in the same run can see true for the candidate only. Lean checks the abstract two-Boolean counterpart with no axioms.

## Exhaustive finite comparison

The finite alphabet is the product of two result tags and four ordered traces, including the two orders of the same read/write events. The corpus exhausts all 256 run sets, including the empty set as an abstract input, and all 256 Boolean contexts on individual complete observations. A context's behavior on a run set is the set of Boolean outcomes obtained by applying it to each run. The check does not assume that all run sets correspond to well-formed programs.

| Relation or comparison | Count |
| --- | ---: |
| Ordered candidate/reference pairs | 65,536 |
| Exact refinements | 6,561 |
| Exact equivalences | 256 |
| Equivalences when separate marginals are compared | 9,070 |
| Marginal refinements with an extra joint observation | 20,912 |

All 256 Boolean contexts preserve exact inclusion across the corpus, and every rejected exact comparison has a Boolean context that shows the difference. Tag-only refinement preserves four contexts and trace-only refinement preserves 16. Comparing both marginals preserves 18, the union of those two families with their two shared constants counted once. A context that must inspect a joint outcome requires a joint projection or separate proof of its independence from the discarded correlation.

Exact tuple evidence supports consumers that inspect correlations but carries a larger observation space. A narrower projection supports clients that use only its declared fields and can be preferable when evidence or runtime visibility is limited. Both routes require explicit outcome completeness and a common comparison context. Stateful adaptive observers, timing, fairness, higher-order contexts and concrete source-to-observation correspondence are outside this finite model. The observation assumptions feed the RT-03 to RT-07 boundary in [DEP-007](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register).

## Reproduce

Use CPython 3.12.14 and Lean 4.36.0 at `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`. The [ledger](JOINT-OBSERVATION-REFINEMENT-01/evidence.json) records the alphabet, all counts, a context witness and the ordered comparison digest.

```sh
set -eu
fixture=research/formal-verification/RT-07/JOINT-OBSERVATION-REFINEMENT-01
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
lean -DwarningAsError=true "$fixture/Refinement.lean" > "$out/axioms.txt"
cmp "$fixture/axioms.txt" "$out/axioms.txt"
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > "$out/evidence.json"
cmp "$fixture/evidence.json" "$out/evidence.json"
```
