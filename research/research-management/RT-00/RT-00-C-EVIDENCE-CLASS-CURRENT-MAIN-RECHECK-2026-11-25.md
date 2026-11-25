# RT-00 C — Current-main evidence-class recheck — 2026-11-25

**Research item:** PLAN §0.2 — distinguish observations, assumptions, conjectures, experimental results, proofs, and accepted decisions
**Baseline:** `main` at `5e96fc6b9ab00d0395cf80e0c1684fd183054fa1`
**Evidence type:** bounded source and ledger crosswalk of three current-main reports
**Status:** selected claim classes rechecked; no quality policy or architecture decision adopted

## Question and method

Do the latest comparison studies keep source observations, model/tool outcomes, experimental results, assumptions, and decisions distinct enough that their evidence is not overstated? I applied the proposed evidence vocabulary claim-by-claim to the RT-23 indexed journal recovery, RT-13 LLVM conversion lowering, and RT-07 Dafny foreign-boundary reports. I inspected the reports and their committed evidence ledgers at the pinned main tree. This is a document audit and ledger consistency crosswalk, not an independent replay or proof review.

## Claim-class crosswalk

| Study and claim | Primary class | Permitted interpretation | Boundary / non-claim |
|---|---|---|---|
| RT-23: full scan and indexed lookup agree on 11 query/CAS cases per tested Git ref backend; bounded scan resolves three and returns `history-window-exhausted` on eight. | Experimental result | Behavior observed in the fixture with 64 journal records, the two ref backends, pinned generations, and exact receipts. | Not a proof of journal completeness, production latency, safe compaction, or crash recovery for the indexed layout. |
| RT-23: a definitive negative index answer requires an append-only mapping, exact receipt validation, and an authorized pinned journal head. | Assumption plus protocol condition | A conditional design argument about how the tested index can be used safely. | The experiment does not establish that LLMLang's future writer, authorization or retention policy satisfies these conditions. |
| RT-13: the bit-guard, ordered-branch and ordered-select functions refine the recorded reference at O0/O3; the pinned validator reports saturation as unsupported. | Model result | Outcomes for exact functions and the recorded validator build/input model; `unsupported` is unknown coverage, not a pass or refutation. | No LLMLang source-to-IR proof, all-target guarantee, saturation proof, or global rejection of LLVM saturation follows. |
| RT-13: plain saturation differs in 63 native observations, while paired poison controls refute an inclusive upper bound and unmasked failed value. | Experimental result | Mismatches and poison observations for the finite archived inputs and x86-64 profile. | Does not select a public LLMLang conversion contract or establish behavior for other widths and FP environments. |
| RT-07: Dafny verifies the local lookup against the mathematical `Expected` function; caller proofs through the extern declaration depend on the declared postcondition. | Proof | The Dafny source theorem under the recorded types, definitions and solver versions; the foreign postcondition is a separate assumption. | The proof does not establish that C provider binaries or their ABI bindings satisfy the declaration. |
| RT-07: wrapping, reversed-priority, and signed-result C controls produce 376, 738, and 286 mismatches respectively; the checked C/unsigned bridge has zero in the tested profile. | Experimental result | Counterexamples and agreement in the named 1,836-input generated-caller fixture. | Not a universal C/ABI correctness claim, kernel result, hardware guarantee or source-to-binary proof. |

No one of the three reports records an accepted LLMLang architecture decision. Recommendations and conditional design implications remain research claims; CI, a passing proof check, and a merged research report do not themselves constitute policy adoption. Conjecture/hypothesis is not the primary class for these reported results: the reports test candidate routes and controls rather than claiming an unresolved hypothesis has been established.

## Result

The evidence boundary is clearest when each report is read as a mixture of classes rather than assigned one class as a whole. RT-23 is primarily a bounded executable experiment with protocol assumptions. RT-13 combines a bounded validator/model result with native observations. RT-07 combines a source-level proof conditional on a foreign declaration with independent native experiments of provider/ABI cases. These categories are not interchangeable, and none closes downstream source, production, or governance obligations by itself.

The reports identify versions, limits and reproduction commands, but do not use stable claim IDs or uniformly bind each claim to confidence, falsifier/missing evidence and downstream draft impact. The JSON ledgers preserve case-level results; they are not substitutes for an adopted claim-register schema or independent technical review.

## Remaining dependencies

- Independent review of the pending claim cohort and technical claims remains external.
- Maintainer adoption of the evidence vocabulary and minimum claim-record policy remains pending.
- Reproduction of these and other results still depends on the pinned Git/LLVM/Alive2/Vellvm/Dafny/Z3 toolchains and compatible native environments; this crosswalk does not rerun them.
- Corpus-wide claim classification, source/model correspondence, and exact historical run provenance remain open.

**Conclusion:** these three studies keep their major result classes and decision boundaries distinguishable, while showing why “proof,” “experiment,” “assumption,” and “accepted decision” must not be collapsed into a single report status. This selected crosswalk does not close Stage 0.2.
