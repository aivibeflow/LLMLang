# RT-00 B13 — Known Relationship Controls Recheck — 2026-11-25

**Status:** four previously missed lexical-screen controls rechecked against current `main`; broad semantic review remains open
**Baseline:** `main` at `305bf66db5f93a0b6a4308f9c6099d2d888b75d2` (the exact main tree at the time of this correction)
**Scope:** recheck the four known relationship controls recorded by B12, the 2026-11-24 all-pairs text-overlap screen. This is a bounded falsification/reconciliation pass, not a new corpus-wide semantic scan.

## Result

B12 compared 87,990 unordered Markdown/MDX pairs and manually reviewed 18 candidates. Its four supplied control pairs had failed the lexical selection filter. This recheck looked up the exact current-main Git blobs, inspected the documents' stated scope and successor/companion context against the existing manual dispositions, and recorded where a relationship is section-specific or only partially superseding. All four controls remain present at exactly the blobs recorded by B12. The filter's misses are therefore confirmed, while the prior scoped classifications remain supported by current source text.

| Control pair | Current blob IDs (first; second) | Current relationship and bounded disposition |
|---|---|---|
| Scenario 31; Scenario 32 | `d9ed864000747071b81390972d4824683184cc63`; `b2ddc72dfedb36c2519a0344b0c720b0e3c9feae` | Section-level supersession: the earlier text-oriented query representation is replaced by canonical typed query IR. Do not mark the whole Scenario 31 report superseded; its profile and prior-art observations remain relevant. Scenario 32's typed IR and limits remain relevant; its parser-state bridge sketch is superseded by the compiled prototype. |
| `GIT-SEMANTIC-REPOSITORY.md`; `GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md` | `a079f82f102da12695d63bae80460885484e6227`; `f5961f5e42cee1f927467672071159a767571a83` | Partial supersession: use the focused document and accepted ADRs for current architecture. Preserve the older broad report as historical rationale/alternatives; only its embedded proposal and stale current-guidance portions are superseded. |
| `RESEARCH-RELATED-PROJECTS.md`; `RESEARCH-DEEP-COMPARISON.md` | `534108da6ad042ce3466be72f2507307f030b1ac`; `7194d2435ece2fb8cb3a3891d898dc142f37370e` | Scoped supersession: the deep comparison supersedes overlapping claims for the four projects it investigates. The initial scan covers a wider project set and remains complementary. |
| English and Russian `LLMLang-FORMAL-VERIFICATION` reports | `0deb6541cb0704681747b151d7415ac4cf0b2c0b`; `58a8bd7716130a86ddce7f1a91e3eb2c341248ae` | Maintained language companions with reciprocal navigation, not duplicates. Their headings have matching numbered sections through §11 plus two unnumbered additions; this structural correspondence does not establish translation parity or sentence-level equivalence. |

The relationship decisions align with B4's manual supersession register, B12's published control metadata, and the current text of the paired documents. Navigation links are treated as evidence of discoverability only, not as proof of semantic equivalence or supersession. No document is wholly discarded by these dispositions.

## Exact-blob context

An exact-blob scan of the complete `research/` tree at the pinned baseline found 1,722 paths and 1,711 distinct blobs, grouped as six repeated-blob groups. Five groups are repeated lockfiles, SAT solver output, or partition fixtures used under distinct query/experiment identities; the sixth is the expected shared Apache-2.0 license text in the OCI and REAPI snapshots. The 612 Markdown/MDX paths have 612 distinct blobs. These results bound exact identity only and say nothing about semantic duplication.

## What this closes and what remains

This recheck closes the four named B12 control cases by linking their missed lexical signals to explicit, scoped manual dispositions on current-main source. It does not close PLAN §0.1's corpus-wide review. Remaining work includes content-level comparison of all candidate and newly changed research families; claim/paragraph lineage; cross-cutting contradiction reconciliation; re-evaluation of the 58 documents without designated-index links as semantic orphan candidates; and exact scope/status refresh for other known supersession families. B8's bounded review of 24 zero-inbound candidates does not establish that the remaining files are or are not semantic orphans.

Scenario 16 remains an external evidence dependency: current repository history and the scenario crosswalk preserve the numbering gap, but only an author or archival record can establish whether it was reserved or omitted. Translation parity also remains unverified and requires a language-aware content review. The exact-blob and hyperlink checks cannot resolve either question.

## Sources and method

- [B4 manual duplicate/supersession audit](RT-00-B-04-CORPUS-DUPLICATE-AND-SUPERSESSION-AUDIT-2026-11-21.md), especially §§5.1–5.2.
- [B12 text-overlap screen](RT-00-B-12-TEXT-OVERLAP-2026-11-24.md) and its [machine-readable pair/control data](RT-00-B-12-TEXT-OVERLAP-2026-11-24.json).
- [Scenario crosswalk reconciliation](RT-00-A-SCENARIO-CROSSWALK-RECONCILIATION-2026-11-23.md).
- [B8 zero-inbound candidate review](RT-00-B-08-ZERO-INBOUND-CANDIDATE-REVIEW-2026-11-23.md).
- Current source documents listed in the control table, read from the pinned Git tree.

The recorded blob IDs use `git rev-parse <revision>:<path>`. Exact-tree duplicate groups were computed by grouping `git ls-tree -r -z` blob IDs for paths under `research/`; Markdown/MDX counts are suffix-filtered. No network or external document claims were used.
