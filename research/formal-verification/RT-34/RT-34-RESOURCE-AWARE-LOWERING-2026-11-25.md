# RT-34 resource-preserving lowering and foreign-call regression gates

**Date** 2026-11-25 · **Plan** §2.0, CX-15–18 and CX-20 · **Issue** [#412](https://github.com/aivibeflow/LLMLang/issues/412)

The fixture evaluates four C implementations of a repeated operation. Each computes the same scalar result over the tested input domain. The resource contract also observes the number of logical units processed by a separately linked provider. It charges a fixed two units, one per physical call and the exact provider's weight per logical unit. The limit is `2 + 4n`. Provider weight is three or seven. GCC builds each provider and the separate caller at `-O0` and `-O2`.

| Candidate | Resource observations |
| --- | --- |
| Direct loop | One call per logical unit. This reaches the exact limit for the weight-three provider. |
| Batches of two, with an odd tail | Processes the same logical units with `ceil(n / 2)` calls. It improves the declared cost for `n ≥ 2` at weight three. The weight-seven provider exceeds the limit for every positive size. |
| Direct loop with an extra zero-work call per unit | The scalar result and logical units are unchanged. Physical-call cost exceeds the budget for every positive size even with the weight-three provider. |
| Closed-form scalar result | Computes the same scalar result in the sample, while removing all observed logical work. It is refused for every positive size. |

All 3,072 native observations match the separate oracle across four builds, four candidates, 64 sizes and three signed input values. The regression gate evaluates 1,024 candidate/profile/size combinations. It admits 268, refuses 504 for the declared budget, and refuses 252 for missing logical work. Among eligible weight-three candidates, enumeration selects the direct loop at sizes zero and one and the batch at the remaining 62 sizes. Seven Lean results check the natural-number cost inequalities and batched-unit equality. The audit reports exactly `propext` and `Quot.sound` for those proofs.

The resource receipt binds the caller, selected provider, linked subject, build configuration, lowering variant, cost profile and weight, size domain, budget and Lean proof source. Respectively changing the provider, build flags, variant, weight, budget, domain, profile or proof invalidates the old receipt. The caller object stays byte-identical across provider changes at each optimization setting. A missing foreign cost yields an explicit unknown. Revalidating the expensive provider makes the former batch selection fail the resource contract.

This candidate keeps functional and resource guarantees independent. Eligibility combines preservation of the declared logical observations with a checked resource bound. Optimization chooses only among eligible candidates. Incremental reuse binds the exact provider's evidence and recompares the applicable resource receipt when a dependency changes. The runner enumerates four hand-written candidates. It does not implement general synthesis, source-to-cost extraction, independently authorized external claims, runtime enforcement, or wall-time prediction. The symbolic theorems establish properties of the declared natural-number model. The C observations are finite and are limited to sizes 0–63. A canonical production cost model and independent benchmark adjudication remain open.

Reproduce with GCC and Lean 4.36.0 from the repository root.

```bash
study=research/formal-verification/RT-34/RESOURCE-AWARE-LOWERING-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two clean builds and Lean replays reproduced the archived ledger byte for byte.
