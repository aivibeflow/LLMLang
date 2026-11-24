# RT-00 — Negative-result and rejected-alternative boundary recheck

**Research item:** `PLAN.md` §0.2 — record negative results and rejected alternatives  
**Date:** 2026-11-24  
**Baseline main:** `5434727fae861c42887419f63c06b22cc6c33807`  
**Evidence type:** bounded cross-document review of five implementation-relevant studies  
**Status:** selected-report audit; no new technical experiment or architecture decision  
**Question:** Do recent studies make negative evidence distinguishable from untested alternatives and scoped recommendations?

## Crosswalk

| Study | Negative result / rejected option | Scope and status | Not established |
|---|---|---|---|
| RT-19 transaction/recovery | The broad monolithic storage interface is rejected **for the next experiment** because it hides different atomic units. Git-only acceptance is insufficient **as the sole workspace lifecycle**; it can remain a synchronization receipt. | Source/API comparison of the in-memory Toolchain and SQLite Content Store contracts; no crash test. | Permanent architectural rejection, production database suitability, or actual recovery behavior. |
| RT-19 multi-file publication | Per-file replacement is explicitly not a multi-file atomic visibility boundary. Generation-manifest and generation-pointer designs remain candidates; no failure control has run. | Mechanism analysis plus a 9/9 rerun of the existing one-file/in-memory tests. | Filesystem-wide behavior or a selected repository layout. |
| RT-25 workload fit | Timing ranges overlap; jemalloc has lower sample live RSS but higher peak RSS in the archived synthetic graph run. The report refuses a general speedup or allocator-selection conclusion. Missing TCMalloc/mimalloc and actual workloads are unavailable, not failed candidates. | 16 archived fresh processes, eight per provider, one synthetic graph and one Linux host. | Statistical equivalence, tails, general memory superiority, or a decision to reject jemalloc. |
| RT-32 Lean observation binding | A return-only proof accepts reordered effects, while the full observation check rejects the claimed trace equality, byte round trip and order-only contract substitution. The profile also rejects subtraction outside its admitted grammar. | Lean-checked claims for two exact SPG bodies and one bounded integer/effect profile. | A falsifier for all source programs, arbitrary traces, or a complete proof architecture. |
| RT-13 LLVM checked add | Three LLVM-verifier-accepted controls produce SAT mismatches and native counterexamples; an unmodeled `add nsw` is rejected as unsupported. | Exact O0/O3 checked-add IR, declared reader grammar, solvers, and native controls. | General LLVM semantics or complete source-to-native correspondence. |

## Findings

The selected reports distinguish three materially different cases:

1. **Tested counterexample or rejection:** RT-32/RT-13 report adversarial controls with exact witnesses or `unsupported` outcomes. Those are falsifiable results within their declared model/reader scope.
2. **Recommendation-level exclusion:** RT-19 narrows the next experiment without saying the excluded alternatives can never be used. This distinction is present in its prose but depends on reading the qualifier (“for the next slice” / “as the sole lifecycle”).
3. **No evidence or neutral result:** RT-25's missing candidates/workloads and overlapping ranges are explicitly not presented as a failed benchmark or proof of equivalence.

Negative results are therefore recorded in these studies, with their limits stated. The format is not uniform: some reports give explicit counterexample rows, while others place recommendation scope and unavailable evidence in prose. A stable per-claim label such as **Falsified in model**, **Rejected for this experiment**, **Not tested**, **Unsupported input**, or **Neutral/overlapping result** would make that distinction easier to audit. These labels should supplement the existing evidence classes, not replace them.

## Decision boundary

No study in this sample turns a negative control into an accepted project decision. RT-19's rejected next experiment is not a permanent architecture prohibition; RT-25 does not reject an allocator; RT-32 and RT-13 reject particular bounded controls, not all alternative implementations. This review adds no normative rule and does not close the corpus-wide Stage 0.2 audit.

## Remaining dependencies

- Independent claim-level review of the selected reports and the pending Stage 0.2 human-review queue.
- Consistent claim-level labels and confidence/falsifier/downstream-impact records across the full corpus.
- Reproduction of the pinned solver/Lean results before they are used as the sole basis for a final implementation decision.
- Maintainer approval before the proposed Stage 0.2 quality vocabulary becomes project policy.

**Conclusion:** these recent studies preserve the distinction between falsified bounded controls, scoped recommendation, and unavailable/untested evidence. They do not yet use a uniform negative-result vocabulary; the bounded check supports incremental Stage 0.2 progress only.
