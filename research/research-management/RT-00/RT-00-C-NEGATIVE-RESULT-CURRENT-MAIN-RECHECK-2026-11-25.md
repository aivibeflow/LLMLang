# RT-00 C — Current-main negative-result recheck — 2026-11-25

**Research item:** PLAN §0.2 — record negative results and rejected alternatives
**Baseline:** `main` at `329f4c2082fe8dfd77f495128f3fa427111eeacd`
**Evidence type:** source-bound consistency recheck of three newly merged comparative studies and their committed JSON ledgers
**Status:** selected current-main evidence reviewed; no implementation or policy selected

## Question and method

Do the newest comparison reports preserve unsuccessful, unsupported, or conditional results in a way that distinguishes them from positive proof or project-wide rejection? I inspected the RT-23 indexed-journal recovery, RT-13 checked F64-to-I64 lowering, and RT-07 Dafny kernel-style foreign-boundary reports; parsed their exact current-main JSON ledgers; recomputed reported ledger outcome counts; and checked the source digests recorded for each executable fixture. This is an internal consistency check, not an independent replay of Git, LLVM/Alive2/Vellvm, Dafny, Z3, or native C.

## Findings

| Study | Negative or constrained result in the ledger | What the result supports | What it does not support |
|---|---|---|---|
| [RT-23 indexed journal recovery](../../toolchain-and-collaboration/RT-23/RT-23-INDEXED-JOURNAL-RECOVERY-2026-11-25.md) | Across 11 query/CAS cases, the full scan and indexed lookup agree on 7 `published`, 3 `undecided`, and 1 `request-conflict`. The eight-entry scan returns `history-window-exhausted` in 8 cases; the oldest receipt takes 65 inspections in a complete scan and 1 indexed lookup. | A bounded scan must fail closed when the history window cannot establish an outcome. The tested index can answer for a pinned generation when the append-only mapping and exact receipt checks hold. | No general decision that indexed storage is preferable. Index completeness, retention/compaction, writer authorization and fresh-head/CAS rules remain prerequisites; this fixture does not cover process interruption in the indexed layout. |
| [RT-13 LLVM F64-to-I64 lowering](../../compiler-and-translation/RT-13/RT-13-LLVM-F64-I64-LOWERING-2026-11-25.md) | The plain saturation route has 63 native mismatches. Alive2 reports both saturation variants as unsupported because the intrinsic is unknown. Two deliberate controls are refuted: an inclusive positive upper bound yields poison, and an unmasked failed value yields poison. | The bounded bit-guard, ordered-branch and ordered-select routes refine the reference at O0 and O3 in the recorded validator runs; guarded saturation matched the native observations in this fixture. | Native agreement does not repair the validator's unsupported intrinsic. Guarded saturation is therefore not formally validated by this run. The results do not establish source-to-IR correspondence, other widths/targets, FP status behavior, or machine-code semantics. |
| [RT-07 Dafny kernel-style foreign boundary](../../formal-verification/RT-07/RT-07-DAFNY-KERNEL-FOREIGN-BOUNDARY-2026-11-25.md) | Both Z3 versions warn when a Dafny proof depends on a foreign declaration. With warnings visible, the caller verifies conditionally; explicit external contracts suppress that warning but still leave the foreign implementation unproved. Dropping the local overflow guard produces a reported postcondition failure. Native controls show 376 mismatches for wrapping overflow, 738 for reversed refusal priority, and 286 when a correct unsigned result is reinterpreted as signed. | Source-level Dafny proof and foreign-provider/ABI conformance are separate obligations. The mismatches demonstrate concrete counterexamples in the specified C/ABI fixture. | A declaration's postcondition is not evidence that the native provider satisfies it. The test does not establish a kernel contract, hardware behavior, general FFI safety, or a selected trust policy. |

The classifications above preserve each failure, timeout/unsupported result, and counterexample at its tested scope. None is promoted into a global rejection of a language construct or backend. Likewise, a positive bounded result is not treated as a general guarantee.

## Ledger checks

- RT-23: recomputed the outcome counters over the nine query rows plus two CAS-boundary rows in `INDEXED-JOURNAL-RECOVERY-01/evidence.json`; verified the three `source_digests` against the exact Git blobs.
- RT-13: checked the recorded mismatch vector and O0/O3 refinement verdicts in `LLVM-F64-I64-LOWERING-01/evidence.json`; verified the digests for `lowerings.ll` and `run.py` against the exact Git blobs. Binary/toolchain hashes were read from the ledger, not independently reproduced here.
- RT-07: checked the proof warning/failure statuses and native mismatch counts in `DAFNY-KERNEL-FOREIGN-BOUNDARY-01/evidence.json`; verified the four declared source digests against exact Git blobs. Downloaded verifier archives and native shared objects were not rebuilt.

All three reports keep their baseline/toolchain and limitations in the source documents. This review does not attest original runs or independently reproduce their environments.

## Remaining dependencies

- Independent experiment replay and technical claim review across the wider corpus remain open.
- RT-13's validator lacks saturation-intrinsic support; a validator that models the operation or a different route is needed before using that proof path.
- RT-23's index requires an authorized append-only writer, complete retention or a checked compaction rule, and a fresh authorized journal head before it can support a definitive negative lookup.
- RT-07 requires an explicit project decision about trusted foreign contracts or independent native conformance evidence; target hardware and ABI scope are not covered.
- Maintainer adoption of the Stage 0.2 quality vocabulary and independent review of the claim-review cohort remain external gates.

## Decision boundary

This recheck supports comparison of the studied implementation routes and records their rejection conditions. It makes no normative change, selects no route, and does not close PLAN §0.2's corpus-wide negative-result, reproducibility, or independent-review obligations.
