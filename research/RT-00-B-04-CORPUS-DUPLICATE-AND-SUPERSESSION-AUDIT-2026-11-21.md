# RT-00-B4 — Corpus-wide Duplicate and Supersession Audit — 2026-11-21

**Status:** repository-wide exact-content scan complete; semantic overlap and supersession review completed for identified candidate families; remaining unreviewed content-level pairs are explicitly bounded  
**Baseline:** `main` at `f09047a65bc77e8756d9d36def836c193a500dfa`  
**Inventory:** 488 research artifacts, inventory manifest excluded  
**Normative boundary:** this audit classifies documentation relationships only. It does not delete artifacts, accept architecture, or turn historical evidence into current validation.

## 1. Executive result

The recursive Git tree contains 488 tracked research artifacts. Comparing Git blob SHA across **all 488 files** found exactly one repeated blob group:

- `research/references/snapshots/OCI/LICENSE-APACHE-2.0.txt`
- `research/references/snapshots/REAPI/LICENSE-APACHE-2.0.txt`

Both contain the same 11,358-byte Apache-2.0 licence text. This is expected shared licence material, not duplicated research evidence. No other exact-content duplicate exists in the audited research tree.

The content-level review of likely overlap/supersession candidates found:
- no confirmed duplicate research result or duplicate prototype implementation;
- several intentional progression chains in which later studies add a new input, proof boundary, execution layer, or falsifier;
- one explicit historical/current-document relationship for Git semantic repository research;
- one explicit applicability decision that deactivates a proposed LLMLang internal wire-compatibility implementation matrix while retaining its prior-art value;
- a number of cross-document overlaps that are complementary, not supersession.

This audit extends B-02b.3 beyond its prior bounded scope (Scenarios 15 and 17–34; Prototype results 16–24 and 26–29). It does not claim a byte-level fuzzy duplicate analysis of every possible pair of text fragments or a full paragraph-by-paragraph review of all 488 artifacts.

## 2. Exact-content method and result

1. Retrieved the recursive Git tree at the pinned baseline.
2. Selected every tracked blob under `research/`, excluding the inventory manifest itself: 488 files.
3. Grouped all files by Git blob SHA; Git's blob identity covers exact file content.
4. Checked the sole repeated group by path and byte size.
5. Used inventory category, title/path, scenario/RT mappings, explicit cross-references, status declarations, and targeted content inspection to select semantic-overlap candidates.
6. Compared the candidate documents' research questions, input models, outputs, validation methods, stated limits, and explicit historical/supersession language.

**Exact duplicate result:** 1 repeated blob group / 2 files / 0 duplicated research reports or prototype implementations.

The exact scan is exhaustive for the pinned Git tree. Semantic duplicate classification is evidence-bounded and is not inferred from similar names, common headings, shared prototypes, or repeated prior-art citations alone.

## 3. Scenario report numbering and inventory

The inventory contains **136 scenario report files**. Their identifiers comprise 135 distinct labels when alphabetic suffixes are treated as part of the identifier:
- Scenario 95 has a main study and a separately dated execution follow-up.
- Scenario 96, Scenario 96A, and Scenario 96B are three distinct identifiers/experiments, not three copies of Scenario 96.
- Scenario 16 has no report in the current corpus. Its absence remains unresolved (reserved number versus missing artifact); no renumbering is recommended.

Do not count 96A/96B as duplicate numeric Scenario 96 reports. The earlier statement of 135 distinct scenario identifiers is correct when the suffixes are retained.

## 4. Reviewed scenario families

### 4.1 Diagnostics and LLVM preservation

| Artifacts | Relationship | Disposition |
|---|---|---|
| Scenario 95 main study → Scenario 95 Execution | Execution report narrows the broad comparison into diagnostic fact, presentation, transport, repair proposal, and authority/acceptance. It explicitly inspects the original study and Scenario 87. | Companion execution report; not duplicate and not supersession. Both should remain linked. |
| Scenario 96 → 96A → 96B | Scenario 96 defines LLVM poison/UB hazards and a preservation corpus. 96A executes the integer subset at O0/O3. 96B tests byte-view bounds and origin identity, including verifier-accepted negative controls. | Distinct evidence layers and different semantic discriminators; 96A/96B do not supersede the broader Scenario 96 comparison. |
| Scenario 96A ↔ 96B | Both use LLVM preservation tooling but validate different contracts (integer/error/effect behavior versus view-bound/origin checks). | Shared harness family is not evidence duplication. Keep separate result records. |

### 4.2 Path feasibility, mutation, and alias analysis

| Sequence | Incremental contribution | Disposition |
|---|---|---|
| 98 → 99 | Generated finite AST-to-path coverage; then repeated identical predicate-marker correlation. | Complementary; 99 adds a constraint absent from 98. |
| 100 → 101 | Exhaustive Boolean predicate feasibility; then differential solver-backed route checking and a limited timing comparison against truth-table enumeration. | 101 is not a replacement for the exact finite oracle in 100. |
| 102 → 103 | Conservative result contract for SAT/UNSAT/UNKNOWN and pruning; then a real process-isolated solver timeout experiment. | 103 supplies one missing execution test for 102; it does not validate solver trust or general SAT behavior. |
| 104 → 106 | Mutable predicate versioning; call mutation summaries; then call-site alias sets and field-sensitive invalidation. | Progressive models with different state/alias assumptions. |
| 107 → 108 | Source-derived bounded AST summaries and may-alias sets; then path-sensitive correlation to recover precision lost by unioning aliases. | 108 is a targeted follow-up to 107, not a duplicate; both retain their restricted Python-shaped fixture boundary. |

These reports form a deliberate research progression. The later documents explicitly refer to earlier gaps and change the model or evidence source. They should not be collapsed into one “path analysis result.”

### 4.3 Serialization and wire compatibility

| Artifacts | Relationship | Disposition |
|---|---|---|
| Scenarios 109–111 | Separate tests for absent/null/value round-trip, producer/consumer schema evolution and defaults, and unknown sum-variant rejection/fallback/opaque relay. | Different semantic dimensions; not duplicates. |
| Scenario 134 | Official-format/prior-art comparison (Protobuf, Avro, CBOR) and expanded compatibility dimensions. It explicitly says it does not repeat the finite JSON fixtures in 109–111. | Complementary research; not duplicate. |
| Scenario 134 applicability decision | The report records an architecture decision that immutable LLMLang components require compatibility only within one coherent build/toolchain version; cross-version internal wire compatibility/schema negotiation is not a current implementation requirement. | Deactivates the proposed internal runtime conformance matrix unless a reconsideration trigger is met. Does not invalidate 109–111 as finite evidence or remove external/persistent data boundary questions. |

### 4.4 Memory model and atomic lowering

| Sequence | Incremental contribution | Disposition |
|---|---|---|
| 113 → 114 | Baseline litmus and per-object observations; then release-sequence relay and the C++20 rule change. | Complementary. |
| 115 → 116 | Fence synchronization and limits of the SC total order; then LLVM lowering and target atomic-width constraints. | Complementary source-contract/backend layers. |
| 117 → 118 | Remaining three per-object coherence fixtures under explicit premises; then joint derivation of execution relations for a bounded program fragment. | 118 integrates rather than duplicates the isolated fixtures. |

### 4.5 Ownership, FFI, cleanup, and invocation lifecycle

| Sequence | Incremental contribution | Disposition |
|---|---|---|
| 119 → 120 | Derives caller obligations from a bounded owned-result contract; then observes concrete SQLite close/finalize behavior. | Abstract contract model and native API evidence are distinct. |
| 120 → 125 | Close dependencies; local recovery; completeness/freshness of observations; shared call boundary; cross-thread synchronization; callback reentry and native dependency coverage. | Sequentially adds dependency, freshness, concurrency, and reentry cases. No duplicate study found. |
| 126 → 130 | Multi-resource roles/reservations; source-level role correlation; foreign error dispositions; invocation-specific cancellation evidence; durable result recovery after interruption. | Distinct lifecycle and evidence dimensions, each extending the prior model. |
| 131 → 133 | Shared owned-result workload; typed caller recovery; generated Rust conformance against the bounded reference. | Source/checker and target-conformance layers. Scenario 133 does not supersede the Python reference or prove arbitrary Rust lowering. |

The family is highly overlapping in domain vocabulary and shares a prototype directory, but each report has a different question, input assumptions, or observation boundary. Treating them as duplicates would discard incremental evidence.

## 5. Non-scenario document relationships

### 5.1 Git semantic repository and merge architecture

- `research/GIT-SEMANTIC-REPOSITORY.md` identifies itself as historical/background research and points readers to `research/GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md`, ADR-014, RT-20, RT-22, and RT-23 for the current focused direction.
- The newer focused document has a narrower responsibility boundary: Git as collaboration/history, a semantic object store, import/export, merge driver/mergetool, and staged integration.
- The earlier report contains a historical ADR-0001 and broader source discussion.

**Disposition:** partial supersession of current-architecture guidance, not deletion or total replacement. Keep the older report as historical rationale and alternatives; direct current design questions to the focused document and accepted ADRs.

### 5.2 Related-project landscape and deep comparison

- `RESEARCH-RELATED-PROJECTS.md` is an initial broad landscape scan across more projects and explicitly calls itself preliminary.
- `RESEARCH-DEEP-COMPARISON.md` deepens source-level review of linkly, Edict, DSP CodeGen, and agent-spec, and explicitly supersedes an earlier RFC in the external project's own lineage where applicable.

**Disposition:** the deep comparison supersedes the initial scan only for the four deeply reviewed projects and their inspected claims. The initial scan remains broader in project coverage and is not wholly redundant.

### 5.3 Backend architecture and translation

- `LLVM-BACKEND-ARCHITECTURE.md` studies LLVM as one replaceable backend and states that LLVM IR is not the canonical LLMLang semantic representation.
- `TRANSLATION-AND-TARGET-BACKENDS.md` studies translation into multiple target languages and cross-backend semantic preservation.

**Disposition:** different scopes, not duplicates. LLVM is one possible backend within the broader translation problem. Scenarios 96/96A/96B provide focused LLVM evidence but do not replace either architecture study.

### 5.4 Cache, dependency, and package models

- `SEMANTIC-COMPILATION-CACHE.md` describes action/result identity, dependency closure, and cache reuse.
- `SEMANTIC-DEPENDENCY-INDEX.md` describes dependency facts and consumers, including planning/toolchain integrations.
- `PACKAGE-SYSTEM.md`, `PACKAGE-MANIFEST-AND-IDENTITY.md`, and `PACKAGE-INDEX-LOGICAL-SCHEMA.md` address distribution, manifest identity, and index representation respectively.

**Disposition:** overlapping interfaces, distinct responsibilities. The documents need cross-reference and interface reconciliation, not deduplication. In particular, package identity is not package trust; an index is not a package resolver; and cache identity is not dependency discovery.

### 5.5 Research management and historical audit reports

The older corpus audit, semantic traceability report, B-02b reports, B3 report, and current inventory are snapshots or bounded audit outputs with different dates and scopes. Their repeated counts and conclusions must be read against their pinned revisions.

**Disposition:** preserve historical snapshots. A later audit may supersede a specific current-state claim, but it does not erase the historical record or convert a previous check into a current check.

## 6. Supersession register

| Source | Superseded/limited content | Current successor or constraint | Treatment |
|---|---|---|---|
| `GIT-SEMANTIC-REPOSITORY.md` | Earlier broad current-architecture proposal and embedded ADR-0001 | `GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md`, ADR-014, RT-20/22/23 | Retain as historical background; current design references should point to successor set. |
| `RESEARCH-RELATED-PROJECTS.md` | Initial claims for four deeply reviewed projects | `RESEARCH-DEEP-COMPARISON.md` | Partial supersession only for overlapping project claims; retain broader scan. |
| Proposed Scenario 134 wire conformance matrix | Cross-version internal component compatibility as a presumed LLMLang implementation requirement | Architecture decision cited in Scenario 134 | Inactive unless reconsideration trigger occurs; preserve prior-art research. |
| Scenario 31 initial text-oriented QF_LIA query path | Original query serialization path | Scenario 32 typed canonical query IR; Scenario 33 parser-state binding; Scenario 34 source semantics/proof | Preserve history; distinguish each layer and do not imply end-to-end closure. |
| Scenario 30 original “no Lean wrapper” status | Status at the time of source audit | Scenario 33 parser-state bridge | Historical status only; proof-binding goal remains separately open. |
| Scenario 95 broad study | None | Scenario 95 Execution | Execution is a companion/follow-up, not replacement. |
| Scenario 96 broad preservation study | None | Scenario 96A/96B focused experiments | Focused experiments add evidence; no whole-study supersession. |

## 7. False-positive duplicate patterns to avoid

1. Same prototype directory does not mean same experiment: the RT-04-01 scenarios use shared helpers but test distinct transitions, states, and proof boundaries.
2. Same title vocabulary does not mean same question: “identity,” “dependency,” “cache,” “ownership,” and “semantic merge” appear across layers with different inputs and consumers.
3. A later experiment that adds one case does not automatically supersede the earlier study; both remain necessary when the earlier study defines the baseline or broader question.
4. A later architecture applicability decision may deactivate a future implementation requirement without invalidating the historical evidence that motivated it.
5. Historical documents should not be deleted solely because a newer document is more focused.

## 8. Known freshness and unresolved items

- The research index still says that the first-pass semantic traceability report covers “all 243 prototype-tree files.” This is a historical count from that review snapshot; the current inventory contains 248 prototype-tree files. The five-file difference must not be interpreted as proof that those files received the same content-level role review. The README should label 243 as the historical review scope.
- The exact duplicate licence pair is intentionally repeated in two external snapshot directories. No deduplication change is recommended because each snapshot directory preserves its own source bundle.
- Scenario 16 remains unresolved as a numbering gap.
- The full semantic duplicate question for arbitrary paragraphs/sections across all 488 files is not reducible to exact Git blob equality. This audit reviewed high-risk candidate families and existing overlap registers; unreviewed pairs remain possible and should be recorded as unresolved rather than declared absent.
- The audit did not run prototype tests, native probes, benchmarks, or external-source revalidation.

## 9. Reproduction and validation boundary

The exact-content result is reproducible from the pinned recursive Git tree by grouping every research blob by Git SHA. The only repeated SHA in the 488-file set is the Apache-2.0 licence pair listed in §2.

The semantic classifications are reproducible by reviewing the cited reports and their explicit cross-references/status sections. They are content-based classifications within the inspected candidate families, not a complete paragraph-level semantic embedding or all-pairs manual review.

**Conclusion:** the current corpus does not show duplicate research reports or duplicate prototype implementations under exact content identity. Most apparent overlaps are intentional layered evidence. Supersession exists at specific document/status boundaries and should be represented as partial, scoped relationships—not broad deletion or renaming.
