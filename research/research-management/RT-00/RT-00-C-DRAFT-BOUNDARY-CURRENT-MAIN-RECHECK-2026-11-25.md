# RT-00 C — Current-main research-to-draft boundary recheck — 2026-11-25

**Research item:** PLAN §0.2 — keep `research/` exploratory and `draft/` as the candidate specification
**Baseline:** `main` at `89ee7062adbd5fda372453ca47ac2e1b72ca7aec`
**Evidence type:** bounded Git draft-delta and decision-status crosswalk
**Status:** selected current-main boundary rechecked; no architecture decision proposed

## Question and method

Since the prior boundary audit, did research links or recent comparison results enter `draft/` in a way that silently promoted a recommendation to an accepted requirement? I compared `draft/` at the prior current-main baseline `738853e571b7e04915441b91075cae9046292cb8` with this exact tree, inspected the sole changed draft file, the accepted architecture decision, the draft directory index, and the latest RT-23, RT-13 and RT-07 comparison reports. This checks source status and traceability, not the truth of the linked research claims or the completeness of all future change reviews.

## Draft delta

The only changed path under `draft/` in the compared interval is `draft/GLOSSARY.md`, changed by PR #653. The addition introduces a “Supporting research (non-normative)” section with four research mappings: structural identity/ABI; Contract/Operation/conformance; public-interface refinement; and assumptions/trust. The section closes by stating that links establish traceability only and do not make proposals normative or validate every glossary claim. The linked material is labeled as proposal or bounded evidence, with remaining decisions and limitations stated. PR #672 added no further draft or ADR changes after the prior `d1d8cf23` check.

The current [draft README](../../../draft/README.md) still says research proposals and alternatives do not become normative by reference. The [accepted architecture decision](../../../draft/ARCHITECTURE-DECISIONS.md) remains scoped to immutable components and single-toolchain caller/callee compatibility; it expressly leaves behavioral Contract refinement, cross-version ABI, RPC, persistence and schema evolution unresolved. The glossary's supporting links do not broaden that accepted scope.

## Current research report boundary

| Report | Research contribution | Boundary recorded in source | Draft effect |
|---|---|---|---|
| [RT-23 indexed journal recovery](../../toolchain-and-collaboration/RT-23/RT-23-INDEXED-JOURNAL-RECOVERY-2026-11-25.md) | Compares complete scan, bounded scan and an indexed Git tree under a pinned protocol fixture. | Index conclusions depend on append-only writer, retention, receipt validation and authorized fresh-head/CAS conditions; no crash-recovery or production policy is selected. | No draft change or accepted repository decision. |
| [RT-13 LLVM checked conversion](../../compiler-and-translation/RT-13/RT-13-LLVM-F64-I64-LOWERING-2026-11-25.md) | Compares checked conversion IR forms under native observations and pinned validators. | Saturation is unsupported by the pinned validator; source-to-IR correspondence and other targets remain open. Results recommend scoped validation but do not select a project backend. | No draft change or accepted conversion semantics. |
| [RT-07 Dafny foreign boundary](../../formal-verification/RT-07/RT-07-DAFNY-KERNEL-FOREIGN-BOUNDARY-2026-11-25.md) | Separates a Dafny proof from foreign provider and ABI conformance evidence. | Caller proof is conditional on an external contract; native controls identify fixture-specific mismatches. It selects no trust policy or production FFI guarantee. | No draft change or accepted FFI contract. |

The current plan and option-matrix records keep these reports in research and label their candidate directions as bounded evidence. No new accepted ADR was added in this interval. The source delta and report wording support the narrow finding that these selected results have not been silently promoted into the candidate specification.

## Remaining dependencies

- The full corpus-wide audit of historical research-to-draft boundaries and future draft changes remains open.
- Independent review of the claim cohort and proposed quality protocol remains unavailable; maintainer approval is required before the protocol becomes project policy.
- Any future draft amendment needs exact source-bound claims and an explicit accepted decision. This recheck does not validate underlying technical claims or resolve external/runtime scope.

**Conclusion:** the one draft change in the compared interval is explicitly a non-normative research crosswalk. The three newest reports preserve their limits and decision boundaries. This bounded result does not close the corpus-wide Stage 0.2 gate.
