# RT-07 — Identical branch elimination and guard evaluation

When both branches of a conditional have the same semantics, control flow can be simplified while retaining evaluation of the guard. This study checks that rewrite and the additional obligations for erasing the guard. The [Boolean evaluation study](RT-07-BOOLEAN-EFFECT-ORDER-2026-11-25.md) supplies the related short-circuit boundary. The research applies to [PLAN §2.1](../../../PLAN.md#21-formal-semantics-of-the-language), [#293](https://github.com/aivibeflow/LLMLang/issues/293) and the transformation evidence requirements in [#297](https://github.com/aivibeflow/LLMLang/issues/297).

An observation contains a result tag and value, the final observed state, and ordered effects. A successful guard feeds its post-guard state into the selected body. A guard error, cancellation or divergence carries its modeled observation through and skips the body. The model records a finite prefix for divergence.

Lean proves that replacing two identical branch bodies with a sequence preserves this observation if the sequence evaluates the guard once and propagates its non-returning outcomes. It also proves an exact condition for erasing the guard at a fixed initial state for **every** possible body. The guard must return a Boolean, preserve the observed state, and emit an empty observed trace. Sufficiency follows by substitution. Necessity uses a successful body that leaves state unchanged and produces no effects, so all three guard conditions are observable. Both checked theorems depend only on `propext`. Erasure for a specific body can have a weaker condition when a separately checked property shows that the body hides the difference under the declared profile.

| Design choice | Obligation |
| --- | --- |
| Evaluate guard once, then use the common body | Establish that both branches have the same semantics under the requested observation. Preserve the guard's ordering, state and non-returning outcomes. |
| Delete the guard | Establish transparency under the requested profile, or prove equivalence for the exact body. A successful Boolean value alone supplies insufficient evidence. |
| Duplicate guard evaluation | Establish a separate equivalence. An observable event or a state change can distinguish the second evaluation. |

## Evidence

The finite fixture covers 150 guards from three initial states, five state update policies, two choices of event visibility and five outcome tags. Each guard is tested with six bodies. The erasure criterion agrees exactly with agreement across all six bodies.

| Check | Count |
| --- | ---: |
| Original and once-evaluated sequence agree | 900 |
| Erasing the guard changes the observation | 792 |
| Of those, only the trace changes | 108 |
| Evaluating the guard twice changes the observation | 210 |
| Guards that can be erased for every tested body | 12 |

The C harness tests the conditional and three rewritten variants. On pinned Clang, it emits separate LLVM IR modules at O0 and O3, then compiles and runs each exact module. Each produces all 3,600 expected rows. Both IR digests are stored together with the source and observation digests. The fixture implements cancellation and divergence as explicit outcome markers for finite replay. It does not exercise actual scheduling, thread cancellation or nontermination.

The Lean rewrite covers the stated model. The native comparison covers exact emitted modules over the finite input corpus. Applying the result to a compiler requires source-to-model correspondence, evidence that the two actual branches have equal meaning, and a binding from the selected pass input to the emitted target. The [rule proof and translation validation comparison](../../compiler-and-translation/RT-13/RT-13-RULE-PROOF-AND-TRANSLATION-VALIDATION-2026-11-25.md) checks the last distinction independently. [DEP-014 and DEP-016](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register)

## Reproduce

Run from the repository root on x86-64 Linux with CPython 3.12.14, Clang Debian 19.1.7 (3+b1), and Lean 4.36.0 at `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`. The Clang executable used has SHA-256 `0a3c55936ac43954fbe4914e6e73b577ca9e35e75d89ef13d3e28c187f41ca1a`. Set `CLANG` to the matching executable when it is outside the path. [Machine-readable evidence](IDENTICAL-BRANCH-01/evidence.json)

```sh
set -eu
fixture=research/formal-verification/RT-07/IDENTICAL-BRANCH-01
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
lean -DwarningAsError=true "$fixture/Rewrite.lean" > "$out/axioms.txt"
cmp "$fixture/axioms.txt" "$out/axioms.txt"
LC_ALL=C python3 -B "$fixture/run.py" > "$out/evidence.json"
cmp "$fixture/evidence.json" "$out/evidence.json"
```
