# Replacement and conflict cues in the research corpus

**Scope.** PLAN §0.1 and [issue #284](https://github.com/aivibeflow/LLMLang/issues/284). This review adjudicates replacement and conflict cues on the pinned 1,187-document corpus screen at research/all `9847850c12cda140e0bdb396d611c2ec96b85c33`.

## Method

Start with the complete 535-pair candidate ledger from the [corpus relationship screen](RT-00-CURRENT-CORPUS-RELATIONSHIPS-2026-11-25.md). For each line-based source, resolve the exact Git blob and line number. Select replacement and conflict terms from the exact line. Read the surrounding claim and use an explicit scope comparison where a cue could update or conflict with an earlier report. The [review ledger](RELATIONSHIP-CUE-ADJUDICATION-01/evidence.json) preserves all 95 affected pairs, their two target blob identities, the triggering cues and the disposition. Excerpt hashes bind individual cue lines to the pinned tree. Candidate numbers are positions within the pinned input ledger.

| Disposition | Pairs |
| --- | ---: |
| Section-level supersession | 6 |
| Scoped update to execution status | 1 |
| Related subject with a distinct scope | 48 |
| Index, crosswalk, or contextual citation | 40 |

The input contained 66 replacement and 55 conflict cue occurrences among these 95 pairs. One cue line can contribute multiple times through distinct candidate-source signals. A statement that a cache operation replaces a pathname or that a solver found incompatible guard values frequently co-occurs with documents that make no competing historical claim.

## Scope of the adjudicated changes

| Candidate | Earlier scope and later evidence |
| --- | --- |
| 300 | Scenario 30's no-wrapper status describes a source design. Scenario 33 supplies a compiled wrapper and exact CPC-assumption checking in the pinned Logos integration. Scenario 30's source audit and binding options remain historical background. [Scenario 30](../../formal-verification/RT-07/RESEARCH-SCENARIO-30-CPC-ASSUMPTION-BINDING.md) · [Scenario 33 §10](../../formal-verification/RT-07/RESEARCH-SCENARIO-33-CPC-PARSER-STATE-BINDING.md#10-current-ci-result-and-remaining-binding-gap) |
| 302 | Scenario 31's text-first route is superseded by Scenario 32's canonical typed query representation. Scenario 31's own introduction also understates its later implementation evidence. The profile restrictions remain relevant. [Scenario 31](../../formal-verification/RT-07/RESEARCH-SCENARIO-31-STRICT-QF-LIA-PROFILE.md) · [Scenario 32 §4](../../formal-verification/RT-07/RESEARCH-SCENARIO-32-CANONICAL-TYPED-RELATIONAL-QUERY-IR.md#4-why-this-is-better-than-a-text-first-representation) |
| 308 | Scenario 33 supersedes the parser-bridge sketch and pending CI status in Scenario 32 for the bounded prototype. Both retain the source-to-query limit. [Scenario 32 §9](../../formal-verification/RT-07/RESEARCH-SCENARIO-32-CANONICAL-TYPED-RELATIONAL-QUERY-IR.md#9-parser-state-bridge-sketch-superseded-by-compiled-prototype) · [Scenario 33 §11](../../formal-verification/RT-07/RESEARCH-SCENARIO-33-CPC-PARSER-STATE-BINDING.md#11-version-2-relational-factor-binding) |
| 371 | The deep comparison supersedes the shallower study only for overlapping coverage of the four examined systems. The earlier survey retains separate system coverage. [Known relationship controls](RT-00-B-13-KNOWN-RELATIONSHIP-CONTROLS-2026-11-25.md) |
| 423 | The pinned Lychee scan supersedes the prior RCA-03 pending status for its 256-document revision and link types. External URL coverage and copied snapshot completeness remain open. [Original finding and update](../RESEARCH-CORPUS-AUDIT-2026-11-20.md#13-current-corpus-local-link-and-anchor-audit--2026-11-21) · [Offline scan](RT-00-E-GLOBAL-LINK-AND-ANCHOR-AUDIT-2026-11-21.md) |
| 520 | The newer Git representation proposal supersedes the embedded ADR-0001's external-KV authority in its proposed architecture. This update is proposal-level. [Known relationship controls](RT-00-B-13-KNOWN-RELATIONSHIP-CONTROLS-2026-11-25.md) |
| 472 | The two-repository fixture supplies native crash and recovery observations for DEP-263's earlier untested coordination boundary. The evidence narrows what is known at the tested local boundary. [Dependency review](RT-00-TOOLCHAIN-PUBLICATION-DEPENDENCIES-2026-11-25.md) |

The remaining cues were compatible with the report scopes or merely mentioned another document alongside the relevant claim. For example, the FFI package studies compare different cache decisions, target identity versus complete cross-build closure. The RT-04 ordered-effects studies discuss conflicts among path guards, while their cross-profile comparison varies handler semantics. The RT-05 requirements studies extend coverage to multiple requirement instances and retain the single-requirement model as a scoped predecessor.

## Reproduction and limits

Run with Git 2.56.1 and CPython 3.12.14. The test reads the old screen and archive, verifies blob identities for source lines, and reproduces the disposition ledger. The semantic disposition itself records a reading of the cue evidence. A score or keyword match cannot establish logical compatibility. Retain whole reports, including the historical status claims in their original scope. Translation-only cues, newly added reports outside this pin, uncued claim pairs and exhaustive contradiction proof remain outside this adjudication.

```sh
study=research/research-management/RT-00/RELATIONSHIP-CUE-ADJUDICATION-01
PYTHONHASHSEED=81 python3 -B "$study/check.py" > /tmp/llmlang-relationship-cues.json
cmp "$study/evidence.json" /tmp/llmlang-relationship-cues.json
```
