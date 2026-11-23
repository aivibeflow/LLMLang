# RT-00 B8 — Zero-inbound candidate content review

**Date:** 2026-11-23  
**Baseline:** `9f0e3a097d6b559310730a4df4885cdaeb121590`  
**Scope:** Content and navigation review of the exact 23 research Markdown/MDX paths reported as having zero inbound local links by the current index-coverage auditor. This is an orphan-candidate review, not a claim-level semantic duplicate audit or experiment reproduction.

## Method

Ran `.github/scripts/audit_research_index_coverage.py` against the exact main tree. It scanned 331 documents (330 research Markdown/MDX plus `PLAN.md`), 19 designated indexes, and 2,092 local-link occurrences. It returned 23 research documents with zero inbound links, six of which are numbered Scenario reports. For each candidate, inspected the document role/title, nearby report links and family/index structure, and whether it is retained external snapshot content or an executable result. Open PRs were checked before review; none were open. Recent merged PR titles and current-main source/index state were checked for supersession signals. The report itself is the 24th research document with no inbound link in the PR tree; the final index-coverage run confirms 24 for that tree.

No research claim or implementation was classified by link count alone. This pass is intentionally limited: the document-level review did not compare every claim with all related reports and did not execute every experiment.

## Candidate disposition matrix

| Candidate path | Content role and observed relationship | Disposition |
|---|---|---|
| `research/PROTOTYPE-01-RESULTS.md` | Historical results for the dependency-graph prototype; overlaps later RT-05/RT-11/RT-24 evidence but records an early finite experiment. | Retain; add a curated historical-results index link after the archive index policy is chosen. |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-21-RESULTS.md` | Result note paired with Prototype 21 implementation/tests; describes paired-run counterfactual analysis and its limits. | Retain with family-local link; the exact-main 13-test suite was rerun below. |
| `research/REPOSITORY-AUDIT-2026-11-17.md` | Dated broad repository audit. Historical snapshot rather than current status source. | Retain as audit history; mark its baseline date/revision visibly in the archive index. |
| `research/RESEARCH-DEEP-COMPARISON.md` | Comparative landscape report of four named adjacent projects. | Retain as dated prior art; current external project state requires a fresh source review before implementation decisions. |
| `research/RESEARCH-RELATED-PROJECTS.md` | Initial related-project landscape, explicitly exploratory and maintainer-claim limited. | Retain as historical scan; link from prior-art index and do not use as current maturity evidence. |
| `research/RESEARCH-SCENARIO-01-RENAME-IDENTITY.md` | Numbered Scenario 01 on rename identity; corresponds to RT-05 identity and Git/rename studies. | Retain; linked from the non-index synthesis `RESEARCH-SYNTHESIS-01-CROSS-SCENARIO.md`, so it is not literally unreferenced. Add a direct scenario-index link if discoverability policy requires it. Reconcile claim overlap in the full semantic audit. |
| `research/RESEARCH-SCENARIO-02-CONCURRENT-CHANGES.md` | Numbered Scenario 02 on concurrent change/merge and atomic acceptance; corresponds to RT-20/RT-24. | Retain; linked from the non-index synthesis `RESEARCH-SYNTHESIS-01-CROSS-SCENARIO.md`, so it is not literally unreferenced. Add a direct scenario-index link if discoverability policy requires it. Keep conflict/lifecycle comparison open. |
| `research/RESEARCH-SCENARIO-03-REQUIREMENT-IMPACT.md` | Numbered Scenario 03 on requirement traceability and change impact. | Retain; directly link from the scenario index; dependency closure and source freshness remain implementation questions. |
| `research/RESEARCH-SCENARIO-04-VERIFICATION-REUSE.md` | Numbered Scenario 04 on verification identity and reuse; later cache-identity rechecks provide bounded updates. | Retain; linked from the non-index synthesis `RESEARCH-SYNTHESIS-01-CROSS-SCENARIO.md`, so it is not literally unreferenced. Add a direct index link if useful and cross-link newer RT-11/DEP-012 evidence. |
| `research/RESEARCH-SCENARIO-09-DEPENDENCY-DRIVEN-EVOLUTION.md` | Scenario 09 on selective dependency-driven evolution. | Retain; linked from `RESEARCH-SCENARIO-05-NAME-FREE-SEMANTIC-CORE.md`, so it is not literally unreferenced. Add a direct index link if useful; compare claims against Prototype 01 and later SPG evidence. |
| `research/RESEARCH-SCENARIO-21-COUNTERFACTUAL-DEPENDENCY-DETECTION.md` | Scenario 21 describes counterfactual dependency detection; Prototype 21 result is a partial paired-input analyzer, not a full detector. | Retain; the Scenario 21 source file itself is in the 23-path zero-inbound set. Add its direct scenario-index link and pair it with the result report; no claim of automatic dependency discovery. |
| `research/RESEARCH-SYNTHESIS-01-CROSS-SCENARIO.md` | Synthesis of Scenarios 01–04; proposed directions, dated before later identity/cache evidence. | Retain as historical synthesis; link from synthesis index and re-review recommendations against current evidence. |
| `research/RFC-REQUEST-CHANGE.md` | Proposed workflow RFC for requests/change sets, content addressing, and review. | Retain as proposal; cross-reference current RT-19/RT-20 design work before adopting any normative text. |
| `research/RT-00-B-02B-2-PYTHON-PROTOTYPE-AND-TEST-AUDIT-2026-11-20.md` | Audit report in the RT-00 B chain; companion reports provide the chain context. | Retain; this file is in the 23-path zero-inbound set. Link from the RT-00 audit index. |
| `research/RT-00-B-02B-3-SCENARIO-OVERLAP-AND-SUPERSESSION-AUDIT-2026-11-20.md` | First bounded scenario overlap/supersession review. | Retain; this file is in the 23-path zero-inbound set. Later review extends rather than silently replaces it; link from RT-00 index. |
| `research/RT-00-B-02B-4-ORPHAN-AND-TRACEABILITY-AUDIT-2026-11-20.md` | Earlier orphan/traceability audit, whose candidate set and totals have since changed. | Retain as historical; this file is in the 23-path zero-inbound set. Link from RT-00 index and point to this current delta. |
| `research/RT-00-C-02-SQLITE-IDENTITY-AND-SOURCE-ARCHIVE-INTEGRITY-2026-11-21.md` | Focused provenance subreport in the RT-00 C chain; newer C delta preserves its unresolved historical-source identity limits. | Retain; this file is in the 23-path zero-inbound set. Link from C audit and current RT-00 index. |
| `research/TOKEN_EFFICIENCY.md` | Broad exploratory authoring/context efficiency ideas, without current comparative measurements. | Retain as idea collection; exclude from architecture choice until workload evidence exists. |
| `research/references/snapshots/MCP/LICENSE.md` | Licence accompanying a pinned partial external MCP snapshot. | Retain with snapshot; no designated-index link is needed if the snapshot register links the directory/licence as one unit. |
| `research/references/snapshots/MCP/authorization.mdx` | Selected upstream MCP documentation page; partial snapshot with unresolved upstream-site paths. | Retain unchanged; zero-inbound indicates a snapshot-register/index gap. Register through references README, not as LLMLang-authored research. |
| `research/references/snapshots/MCP/basic-index.mdx` | Selected upstream MCP documentation page; partial snapshot. | Retain unchanged; zero-inbound indicates a snapshot-register/index gap. Register through references README. |
| `research/references/snapshots/MCP/transports.mdx` | Selected upstream MCP documentation page; partial snapshot. | Retain unchanged; zero-inbound indicates a snapshot-register/index gap. Register through references README. |
| `research/references/snapshots/OCI/image-layout.md` | Selected upstream OCI specification page; partial snapshot with unresolved links. | Retain unchanged; zero-inbound indicates a snapshot-register/index gap. Register through references README. |

## Comparison and implementation implications

The original 23 candidates split into four useful dispositions: 11 historical research/results that should remain discoverable; four numbered scenario reports that have no incoming links, suitable for the Scenario index and cross-link updates; three audit-chain reports that need a curated RT-00 landing page; and five externally sourced files that belong to the snapshot register rather than the LLMLang research index. The remaining candidates include two additional scenario reports and three historical/proposal/idea documents, retained with contextual links and explicit status. **No candidate is recommended for deletion.** The index audit is a navigation signal, not evidence that a result is false, redundant, or obsolete.

The audit's `zero-inbound` measure means no inbound Markdown link at all; its `without-index-inbound` measure means no direct inbound link from its fixed list of designated indexes. A non-index synthesis can provide navigation without satisfying the latter. This review supports a small, curated index strategy over treating every file as a top-level research result: scenario and prototype families should link their own result files, the RT-00 audit chain needs one landing page, dated prior-art/synthesis documents need an archive/prior-art entry, and upstream snapshot files should remain grouped under their source register. A future full semantic audit should examine claims and supersession edges before declaring duplicates or superseded versions.

## Focused reproduction: Scenario 21 result

The historical result names 13 focused unit tests but originally reported a local run from checkout `e0cd4055db77c02611be505d8ba34bbe819f932d`. To validate the exact current-main source rather than infer continuity from its prior statement, reran:

```sh
cd research/PROTOTYPES/DEPENDENCY-GRAPH-01
python3 -B -m unittest discover -s tests -p 'test_counterfactual_analysis.py' -v
```

Environment: CPython 3.12.14, Linux x86_64, standard-library `unittest`; repository baseline `9f0e3a097d6b559310730a4df4885cdaeb121590`. Result: **13 tests passed**. The tests validate the analyzer's behavior on supplied paired-run records, including outcome/trace distinctions, missing or malformed pairs, unstable observations, identity mismatch, and evidence-digest sensitivity.

This does not execute a candidate LLMLang program, verify that the declared changed factor is accurate, provide independent digests, infer dependencies, or measure false-positive/negative rates. It reproduces the finite analyzer contract only.

## Limits and remaining dependencies

- The review checked document-level role and context, not paragraph/claim-level semantic equivalence or contradiction.
- The 57 files without a designated-index inbound link are a larger population; this report covers only the 23 zero-inbound candidates.
- Only Prototype 21 was rerun (13/13 focused tests); the other candidate experiments were not rerun. Remaining claim-level commands/toolchain provenance still require the Stage 0.1 reproducibility audit.
- External snapshot reachability and completeness remain upstream dependencies: MCP documentation omits linked pages, OCI and Alive2 snapshots contain unresolved links, and REAPI imports are incomplete. This review makes no request to fetch or vendor those files.
- Scenario 16 intent remains unknown.

**Conclusion:** all 23 zero-inbound paths have a bounded content-role disposition and a proposed navigation route. None is a proven semantic orphan. This closes only the zero-inbound candidate classification slice; Stage 0.1 remains open for the 57 no-designated-index candidates, paragraph-level duplicate/supersession/contradiction review, claim/toolchain reproduction, external snapshot completeness, and Scenario 16.
