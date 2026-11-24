# RT-00 — DEP-008 Typed Proof-Boundary Recheck (2026-11-23)

**Plan item:** §0.3, validate dependency edges as evidence accumulates  
**Edge:** DEP-008, RT-04 → RT-07 (`Constrains`)  
**Baseline:** current `main` `c3f4d6841759415fb502806e1c3e27db30658433`  
**Disposition:** Retain DEP-008 as a strong hypothesis. Proof claims must either model the relevant type/effect/resource semantics or state a narrow boundary that excludes them. Current evidence supports a layered, fail-closed proof boundary as a practical candidate; it does not establish a full-language type/ownership proof architecture.

## Compared proof boundaries

| Strategy | What it promises | Evidence / cost |
|---|---|---|
| One integrated formal semantics for values, effects, ownership, resources, cleanup, and runtime behavior | Strong compositional guarantees if source and implementation correspondence are also proved | Highest modeling and proof burden. Current Lean rewrite theorem does not cover the ownership/resource cases. |
| Typed core proof plus separately scoped checkers/models for effects and resource obligations | Strong local claims with explicit interfaces; unsupported constructs remain unknown/rejected | Closest to the current evidence: Lean proves typed integer/Boolean rewrite preservation with ordered traces; Scenario 119's checker explores ownership cleanup obligations and caller matches in a separate fixture. Composition across those boundaries is not proved. |
| Prove only scalar value results and leave effects/resources to tests or runtime behavior | Lower proof cost | Insufficient for claims about full observable behavior: event order and failure prefixes can change while scalar results match; ownership obligations can change caller exhaustiveness while result tags remain the same. |
| Omit types/resources from the proof claim and rely on an informal statement | Minimal checker/model work | Not evidence-bearing. The claim would be ambiguous about which executions and observations it covers. |

The bounded result favors an explicit, typed proof profile with fail-closed exclusions, and separate evidence for resource/effect mechanisms. This is a candidate assurance structure, not an accepted LLMLang architecture.

## Current-main evidence

### Typed rewrite proof

The `ObservableRewrite` Lean module indexes expressions by `Int`/`Bool` sort and defines a run as an outcome paired with an ordered event list. The theorem `rewrite_preserves` proves complete run equality for every integer input and every expression in that grammar. The proof's source blob is `98bd38f297e91840c56664ef00fbd5f28c3a81b8` on current main and the same on CI head `52322e7a00e95ab02dab0a99e8078de64d33ce34`.

Required CI run [#45153194551](https://github.com/aivibeflow/LLMLang/actions/runs/45153194551), job `logos-binding / lean-build-and-test`, completed successfully under the pinned Lean 4.36.0 toolchain. The `Check observable rewrite proof` step passed. Lean is not installed in the local environment, so this is exact-blob CI verification rather than a local Lean rerun.

The theorem does not model ownership, cleanup, external effects, capabilities, calls, concurrency, cancellation, machine overflow, or source parsing/lowering. It therefore cannot support claims about those dimensions by itself.

### Ownership/result obligations

Scenario 119 compares transfer-before-cleanup and staged-transfer policies and two result encodings. Its checker enumerates close-result subsets and verifies result shapes against a separate disposition model. The current-main reproduction command is:

```sh
python -B -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_rt04_owned_call_match.py' -v
```

CPython 3.12.14 result: **10 tests passed**. The tests include missing caller arms after an obligation contract expands, distinct retained/reconcile debts, timing-dependent feasibility of a plain `Result`, and policy differences in exact match-arm counts. This is executable fixture evidence, not a proof of the runtime ownership semantics or a real resource adapter.

SHA-256 identities at the baseline:

- `ObservableRewrite.lean`: `039808b6adf5d5baa97f6498a15fd04843a4f4c6b1147c9dade68f4440252765`
- `test_rt04_owned_call_match.py`: `829ff02bb194f325938b7f92518fed945a2c5e0a906fa5dd46f29e39d67ce9a5`
- `rt04_owned_call_match.py`: `48600753efd64b43061277463ece1ab86460723b2b239f663126a1f625f5e373`
- `rt04_return_disposition.py`: `23f8eadbc83cdcd140f994b78fe33a4afeebdc42a5c6c0d9621b9172423cbb5e`

## Remaining dependencies

No external service or maintainer decision was needed. Closing the implementation choice depends on internal research: formalize the resource/capability observation model, bind ownership models to source-derived typed graphs, and prove or test the boundary between the typed core and resource handlers. Until then, keep unsupported effects/resources outside the theorem's claim and treat them as unknown unless a dedicated evidence path covers them. DEP-008 is not established by these fixtures; §0.3 still requires evidence-by-edge review.
