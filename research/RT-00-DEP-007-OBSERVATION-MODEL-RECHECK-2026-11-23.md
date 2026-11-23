# RT-00 — DEP-007 Observation-Model Recheck (2026-11-23)

**Plan item:** §0.3, validate dependency edges as evidence accumulates  
**Edge:** DEP-007, RT-03 → RT-07 (`Requires`)  
**Baseline:** `main` `3772b558d4980d0bba0af15a19090e4eb545c89d`  
**Disposition:** Retain DEP-007 as a strong hypothesis with checked witnesses. For the bounded expression fragment, proof of rewrite correctness depends on an observation model that includes both outcome and ordered event trace. A value-only observation would accept transformations this proof rejects.

## Compared evidence strategies

| Strategy | Coverage and cost | Result for this case |
|---|---|---|
| Prove each rewrite rule and compose by structural induction | Can cover every expression in the model grammar and every input; depends on a stable semantics and proof maintenance | Implemented. `rewrite_preserves` proves equality of the complete run (outcome and trace) for all finite expressions and integer inputs in the modeled grammar. |
| Translation validation for each transformed artifact | Can accept output from an independent optimizer; needs a verifier bound to the exact input/output pair and a semantics rich enough to include effects and failure | Complementary option, not implemented by this proof. It still depends on the RT-03 observation model and source/artifact correspondence. |
| Differential execution against a reference interpreter | Useful for counterexample discovery and concrete compiler/backend checks; covers only executed inputs and variants | Useful as a second line of evidence, but finite tests alone do not establish the universal theorem above. |
| Compare only return values or successful executions | Cheap, but omits order and pre-failure behavior | Falsified: the checked addend swap has the same integer result but traces `[1, 2]` and `[2, 1]`; dropping an emitting failing guard changes failure code/trace into success. |

The evidence favors making the observation relation explicit before selecting rewrite proofs or validation. It does not imply that every runtime effect belongs in the same trace; cleanup, state, calls, concurrency, cancellation, and resources remain outside this Lean model.

## Checked proof and current-main identity

`research/RT-07-OBSERVABLE-REWRITE-CORRECTNESS.md` documents a typed expression grammar with integers, Booleans, addition, equality, lazy conditionals, event emission, and failure. The interpreter evaluates left-to-right, stops at the first failure, and retains the event prefix. `rewrite_preserves` composes the local fold lemmas and proves full-run equality. `swapping_addends_changes_trace` and `discarding_equal_branch_guard_hides_failure` witness why scalar result equality is insufficient.

The exact proof source at current main has Git blob `98bd38f297e91840c56664ef00fbd5f28c3a81b8` and SHA-256 `039808b6adf5d5baa97f6498a15fd04843a4f4c6b1147c9dade68f4440252765`. It is byte-identical to the source in PR #254 CI head `c84cb6cccefbd08695fa06c7e2427859de0b9afa`. Required CI run [#45151548187](https://github.com/aivibeflow/LLMLang/actions/runs/45151548187), job `logos-binding / lean-build-and-test`, reports the step **“Check observable rewrite proof”** successful. The workflow pins Lean 4.36.0 and runs `lean -DwarningAsError=true ObservableRewrite.lean`.

Lean is not installed in this local environment, so the proof was not independently re-executed here. The evidence is the passing required-CI step on the same proof blob as current main, not a new local run.

## Limits and remaining dependencies

The theorem covers every term only within its finite grammar. It does not prove that a LLMLang parser or SPG lowering is complete, that a compiler emits this modeled language, or that a backend preserves the model. Integer overflow, state, cleanup, resource ownership, calls, concurrency, and cancellation require expanded observations or separately justified abstraction boundaries. The proof's standard Lean axioms are printed in the module and the RT-07 report records them.

No external service or maintainer decision is required to apply the bounded result. Closing the implementation decision depends on internal research: stabilize RT-03 semantics and observation boundaries, establish source-to-IR/SPG correspondence, and test or prove backend lowering against that model. Keep DEP-007 at its current confidence; the remaining edge map still needs evidence-by-edge review.

## Question, assumptions, and draft-impact crosswalk (2026-11-23)

- **Research question:** For the fixed Lean expression grammar, is equality of scalar return values sufficient to justify observable rewrite correctness, or must the theorem preserve both the outcome (including failure) and the ordered event trace?
- **Hypotheses and falsifiers:** the existing `rewrite_preserves` theorem checks full-run equality for its specified rewrite rules. The addend swap and failed-guard counterexamples reject the scalar-only candidate. Translation validation and concrete differential testing remain separately proposed, not proven interchangeable with the theorem.
- **Evidence class and version:** proof statement/checker result is bound to the exact Lean proof blob, pinned Lean version and cited CI in the section above; this crosswalk itself contains no new proof run. The full-language parser, SPG lowering, backend and effects beyond the grammar remain unproved.
- **Decision / draft impact:** retain DEP-007 as a **supported bounded research dependency**, not an accepted full-language optimizer rule. No `draft/` text or language semantics change is authorized here. Source-to-IR, compiler and richer runtime observation bridges remain open in the dependency map and [issue #285](https://github.com/aivibeflow/LLMLang/issues/285).
