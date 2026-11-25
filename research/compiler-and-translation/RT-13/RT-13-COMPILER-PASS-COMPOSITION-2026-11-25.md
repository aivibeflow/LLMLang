# RT-13 — Composing preservation obligations across compiler passes

A compiler pipeline needs a preservation result for the actual sequence of artifacts. This study checks which obligations let two independently validated steps compose. It extends [rule proofs and translation validation](RT-13-RULE-PROOF-AND-TRANSLATION-VALIDATION-2026-11-25.md) and [exhaustive evidence scope](RT-13-EXHAUSTIVE-EVIDENCE-BOUNDARY-2026-11-25.md) for [PLAN §2.5](../../../PLAN.md#25-correctness-of-optimization-and-translation) and [#297](https://github.com/aivibeflow/LLMLang/issues/297).

| Obligation | Evidence required for this model |
| --- | --- |
| Bind the subjects | Each receipt refers to exact source and target artifacts. The first target must be the second source, or a checked bridge must establish correspondence for the required claim and domain. |
| Carry the input guard | Every requested input satisfies both pass domains. Pass-local evidence for an input outside the requested subset does not establish that a different input is admitted. |
| Preserve definedness and observations | Each admitted input yields an observation on both sides. The observation includes the result and ordered effects. A narrower receipt needs a checked lifting argument before it can support the complete claim. |
| Compose under a common interpretation | Artifact types, behavior of imported operations, toolchain semantics and environmental assumptions agree on the bridge. The fixture supplies one common interpretation. Production correspondence and checker trust require explicit evidence. |

Lean checks composition across one exact intermediate and across a separately proved bridge. Each step supplies a defined, equal observation on its admitted inputs. Equality at the intermediate gives equality at the outer endpoints. It also checks that result-only equality can hide an ordered-trace difference. The three declarations use no axioms. The Lean statements assume the stage predicates and their common meaning. They do not prove a production loader or receipt's authenticity.

## Finite comparison

Eight concrete tables contain results, ordered effects and absent defined outcomes for two inputs. Two tables intentionally have identical observations and distinct artifact bytes. The runner enumerates every two-edge candidate with nonempty receipt guards and either result-only or complete observations, retaining the 57,132 cases where both local claims hold. It validates each policy independently against direct full preservation at the endpoints.

| Check applied to two locally valid receipts | Admitted | Admitted with false endpoint preservation |
| --- | ---: | ---: |
| Exact intermediate, requested guard and complete scope | 340 | 0 |
| Checked intermediate bridge, requested guard and complete scope | 1,442 | 0 |
| Skip intermediate identity or bridge | 2,018 | 576 |
| Skip requested guard coverage | 1,278 | 598 |
| Accept either receipt observation scope | 2,312 | 592 |
| Check only the two local claims | 57,132 | 34,994 |

The bridge route admits 1,102 more cases by checking equality for distinct artifacts under the exact requested domain. It can admit a pair that agrees within one guarded input but differs elsewhere. An unbound intermediate can retain the wrong trace before the second receipt even begins. A missing domain check can use both receipts outside their guards. A result-only chain loses effects even when the two pass stages share one exact intermediate.

An exact-subject chain has a smaller evidence surface. A bridge supplies more reuse when guard, observation and interpretation are explicit. These options need source/IR correspondence, exact actual pass outputs and complete disposition of the assumptions before production use. The finite model admits deterministic observations with explicit absence of defined behavior. General nondeterministic refinement, CFG effects, UB semantics for unrestricted LLVM, and compiler integration remain further work. [DEP-014 and DEP-016](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register)

## Reproduce

Use CPython 3.12.14 and Lean 4.36.0 at `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`. Run from the repository root. The [ledger](PASS-COMPOSITION-01/evidence.json) records the artifact identities, checks and counterexamples.

```sh
set -eu
fixture=research/compiler-and-translation/RT-13/PASS-COMPOSITION-01
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
lean -DwarningAsError=true "$fixture/Chain.lean" > "$out/axioms.txt"
cmp "$fixture/axioms.txt" "$out/axioms.txt"
LC_ALL=C python3 -B "$fixture/run.py" > "$out/evidence.json"
cmp "$fixture/evidence.json" "$out/evidence.json"
```
