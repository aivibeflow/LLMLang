# RT-00 — Recent evidence-class boundary recheck

**Research item:** `PLAN.md` §0.2 — research quality and decision rules  
**Date:** 2026-11-24  
**Baseline main:** `690ccbbb00ac2a93b5b54871f6d19a2e710eedd6`  
**Evidence type:** bounded document and source crosswalk against proposed quality rules  
**Status:** selected-document audit; no policy adoption or whole-corpus claim review  
**Question:** Do recent implementation-relevant reports distinguish observations, model/proof results, assumptions, recommendations, and accepted decisions well enough to avoid overstating the implementation evidence?

## Scope and method

I compared the evidence vocabulary and minimum claim-record fields in [Research Quality and Decision Rules](../RESEARCH-QUALITY-AND-DECISION-RULES-2026-11-20.md) with four current-main artifacts: the RT-19 transaction/recovery comparison, the RT-19 multi-file publication recheck, the RT-25 workload-fit recheck, and the RT-32 Lean observation-binding report. I checked their headers, results, reproduction/limitations sections, recommendations and any linked raw sources. This is a document-level audit; it does not independently rerun the historical results or establish that source semantics correspond to the models.

## Claim-class crosswalk

| Claim | Evidence class | What the report supports | What it does not support |
|---|---|---|---|
| **C-19-1:** The adjacent in-memory Toolchain and SQLite Content Store focused suites each passed 9/9 in the named recheck environment. | Observation / experimental result | The named test suites passed on the recorded CPython environment and checked component behaviors. | Shared durable acceptance, crash recovery, process concurrency, or production persistence. |
| **C-19-2:** Separate logical object/workspace contracts coordinated in one local DB transaction are the most discriminating next experiment among the compared RT-19 protocols. | Recommendation based on source observations and analytical comparison | It is a scoped next experiment consistent with the current API boundaries and Git reconstruction premise. | A tested recovery guarantee, production backend choice, or accepted ADR. The report explicitly says no crash injection was performed. |
| **C-19-MF-1:** Prototype 01 implements one-file temp-write, `fsync`, and replacement; its suite passed 9/9. | Source observation / experimental result | Single-file replacement and the named tests. | Atomic visibility of a multi-file generation, cross-platform durability, or Git ref recovery. |
| **C-19-MF-2:** Validate a private complete tree before Git ref publication as the next experiment. | Recommendation | A discriminating experiment that fits the stated Git-reconstruction boundary. | A selected repository format or implemented publication backend. |
| **C-25-1:** The archived graph comparison has 16 processes, eight per allocator, matching checksums and the listed timing/RSS values. | Experimental result / observation | A two-provider synthetic graph comparison on one pinned Linux configuration; raw results are linked. | Representative cache/package/concurrent Toolchain performance, confidence in tails, or allocator selection. |
| **C-25-2:** Keep the platform allocator as the baseline while expanding coverage. | Recommendation | A conservative next-step recommendation given the narrow workload and overlapping timing ranges. | A finding that the platform allocator is generally superior or an accepted runtime policy. |
| **C-32-1:** Lean checks the stated lowering theorem and exact scalar body/contract witnesses in the fixture. | Proof / model result | The propositions represented by the generated Lean terms for the declared integer profile and exact recorded bodies/contracts. | That Python extraction matches all LLMLang source semantics, all language profiles, backends, or production programs. The report names that source correspondence boundary. |
| **C-32-2:** The source-bound hybrid is the strongest of the tested proof representations for this fixture. | Bounded comparison / recommendation | A comparison among the fixture's shallow, deep and hybrid encodings. | General proof architecture selection or acceptance of a language/backend design. |

All four reports distinguish a bounded result from an implementation-wide conclusion in their scope/limitation language. The RT-19 and RT-25 artifacts also mark recommendations and state that they do not select a backend or allocator. RT-32 distinguishes kernel-checked propositions from the unproved source-to-extractor correspondence. These are useful practices for these documents.

## Quality-rule coverage and gap

The proposed quality rules require one primary evidence class per material claim, plus scope, an evidence pointer, confidence, a falsifier/missing-evidence statement, and downstream impact. In this four-document sample:

- **Present consistently:** evidence type/scope, a named method or reproduction route, limitations, and a conclusion boundary.
- **Present unevenly:** exact source revision is recorded, but some documents pin an older main baseline rather than the merge base/current-main snapshot on which later navigation was reviewed; the underlying experiments remain pinned separately.
- **Not present as a uniform structure:** stable claim IDs and claim-by-claim confidence/falsifier/downstream-impact fields. The crosswalk above supplies these labels for review only; it does not retrofit the source reports or certify the empirical runs.
- **No accepted decision evidenced:** each recommendation remains a research recommendation or proposed experiment. None of these four results records an authorized decision selecting an RT-19 backend, an RT-25 allocator, or the full RT-32 proof architecture.

The top-level `Evidence type` field is therefore a helpful scope hint, but it cannot substitute for a claim-level record when a document combines runs, assumptions, proofs and recommendations. The current evidence supports retaining the proposed distinction between **evidence class** and **recommendation/decision status**.

## Reproduction-boundary crosswalk

| Study | Recorded reproduction route | Exactness and practical limit |
|---|---|---|
| RT-19 transaction/recovery | Two explicit `unittest discover` commands; expected 9/9 each; CPython 3.12.14 recorded. | Repeats adjacent prototype suites, not the comparative state-machine reasoning, crash recovery, or a shared coordinator. |
| RT-19 multi-file publication | The first report version recorded 9/9 without the command. This recheck reran the suite on Python 3.12.14 and the report now contains the exact command and expected 9/9. | Reproduces one-file/in-memory tests only; none of the multi-file candidates or failure points are implemented. |
| RT-25 workload fit | A Python snippet computes median/min/max from the linked archived raw JSON; the environment check records Debian 13 x86-64, Linux 6.18.57, missing `rustc`, TCMalloc, and mimalloc. | Reproduces the summary statistics, not a fresh allocator run. The benchmark runner still needs a pinned Rust/allocator environment. |
| RT-32 Lean observations | Exact replay command compares regenerated JSON with the pinned ledger; Lean 4.36.0, Python 3.12.14, and source hashes are recorded. | Repeats bounded proof/model artifacts; the report explicitly leaves Python-to-source semantics and broad profiles outside the Lean proof. |

The recheck found and corrected one documentation gap in the RT-19 publication report. For this sample, commands and tools suffice to reproduce listed component checks or transform archived raw measurements, but they do not turn those checks into evidence for the unimplemented design alternatives.

## Reproduction and limits

This recheck reads the four linked reports and their declared boundaries. It reran the RT-19 Toolchain focused suite (9/9, Python 3.12.14) to verify the newly documented command; it did not rerun the other studies. A reviewer should rerun each experiment before relying on its empirical claim for a final architecture decision. This audit did not inspect every root, RT, scenario, prototype, or external-source snapshot in the repository.

## Remaining external dependencies

- Independent human adjudication of the Stage 0.2 review queue and the separate quality-rule handoff remains pending in the referenced quality-audit reports.
- Maintainer approval is still required before the proposed evidence vocabulary and quality gates become project policy.
- Claim-level audit, historical run attestation/reproduction, and source-to-model correspondence remain report- and corpus-specific.

**Conclusion:** the sampled current-main studies keep observations, bounded results, proofs, recommendations, and decisions materially distinct, while lacking a consistent claim-level record. This supports a bounded Stage 0.2 progress entry; it does not close Stage 0.2 or validate the full research corpus.
