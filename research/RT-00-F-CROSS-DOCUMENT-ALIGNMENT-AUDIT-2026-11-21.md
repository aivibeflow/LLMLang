# RT-00 F — Current cross-document alignment audit

**Date:** 2026-11-21  
**Baseline main:** b0142c27f5632a859c379b78a10cb22f500ebfd8  
**Inventory revision:** b118346ecd499d7962a6ac546fb1031bc7e2bc26  
**Scope:** Research Taxonomy, Research Dependency Map, Research Option Matrix, Semantic Dependency Index, Draft Glossary, PLAN.md, and existing cross-cutting alignment review.

## 1. Current corpus and register counts

The inventory manifest at revision b118346ecd499d7962a6ac546fb1031bc7e2bc26 records 488 artifacts and 248 prototype paths; it is stale relative to current main at b0142c27f5632a859c379b78a10cb22f500ebfd8:

| Measure | Current value |
|---|---:|
| Research artifacts in manifest | 488 |
| Markdown | 251 |
| MDX | 3 |
| Python | 203 |
| Lean source files | 23 |
| Prototype-tree files in manifest | 248 |
| Scenario-named reports | 136 |
| Preparation/reference files | 24 |
| Research areas | 26 (RT-01–RT-26) |
| Dependency edges | 108 (DEP-001–DEP-108) |

The recursive inventory audit in PR #146 scanned main at 017e64b and measured 490 research artifacts excluding the manifest, 250 Markdown files, 3 MDX files, 202 Python files, 23 Lean files, 249 prototype files, and 136 Scenario-named documents. Exact comparison to b52ba2f adds two RT-23 paths; comparison from b52ba2f to b0142c2 adds the B4 report, yielding 493 research artifacts, 252 Markdown, 3 MDX, 203 Python, 23 Lean, and 250 prototype files. The current manifest has five missing paths (RT-24 report/test, RT-23 report/test, and B4 audit report), zero extras, and five stale SHA/size records (Dependency Graph README, research README, dependency map, RT-24 canonical report, RT-23 worktree contract). PR #149 proposes the correction and remains unmerged. The earlier cross-cutting alignment review's 24 RT / 94 DEP counts are historical. The current research README already states that those figures are superseded by the current taxonomy and dependency map. The old review's §1 and conclusion should be read as a first-pass result at its own baseline, not as a current count.

## 2. Structural dependency-map validation

The current taxonomy and dependency map were read directly from main and checked structurally:

- 26 unique RT rows;
- 108 unique DEP rows;
- every edge endpoint resolves to one of the 26 RT identifiers;
- zero duplicate DEP IDs;
- zero self-loops;
- two non-trivial strongly connected components:
  - RT-05 ↔ RT-12;
  - RT-14 ↔ RT-19 ↔ RT-20.

Both feedback components are already described in the dependency-map prose. No additional hidden SCC was found. The high-level Mermaid diagram is explicitly described as simplified and depicts only the earlier RT-01–RT-20 subset; RT-21–RT-26 are present in the detailed taxonomy and edge register. This is a visualization-scope limitation, not a conflict in the register.

## 3. Candidate and normative-status alignment

The following statuses are consistent across the inspected documents:

| Artifact | Current status | Alignment result |
|---|---|---|
| Research Taxonomy | Working research-management document | Register only; not specification/architecture |
| Research Dependency Map | Initial dependency hypothesis | Edges remain hypotheses with stated confidence/evidence |
| Research Option Matrix 01 | Initial evidence-linked comparison; no vector selected | Candidate bundles, not selected architecture |
| Semantic Dependency Index | Research proposal | Not canonical SPG schema or accepted language rule |
| Draft Glossary | Terminology proposal | Definitions and hash envelopes remain provisional |
| RT-24 | Research proposal | Candidate representation/merge contract remains non-normative |
| ADR-014 | Proposed | Not accepted |

The ImpHash/ImplHash spelling discrepancy remains explicitly unresolved in PLAN.md and the prior B3/B6 audits. It is not normalized here. The distinct ContractHash, OpHash, ImplHash, CCHash, and optional CandidateSetHash roles in the glossary are not collapsed into one identity. The bridge from contract refinement to operation/implementation conformance remains open.

No semantic, hash, identity, backend, or architecture decision is made by this audit.

## 4. Stale and inconsistent inventory/plan metadata

Three different counts currently describe prototype-family role coverage:

1. The previous inventory manifest contains **248** prototype paths and per-artifact traceability records for all 248. Current main contains **250** prototype paths; the RT-23 and RT-24 Dependency Graph tests are the two prototype paths absent from the manifest.
2. The inventory's prototype_family_review.individually_mapped_files aggregate still reports **242**, with family counts 3/103/3/7/17/104/2/3.
3. PLAN.md's previous first-pass role-mapping statement reports **245**, with family counts 3/103/4/7/17/106/2/3.

The previous manifest family counts are 3/106/4/7/17/106/2/3 (total 248). Current main has 108 Dependency Graph paths and 250 prototype paths total. The aggregate review metadata and the PLAN statement therefore do not agree with the current tree or with each other. The 248 per-file traceability records establish that mappings are present; they do not prove equivalent depth of content review for every added artifact. The eight-file delta from the inventory aggregate (242 to 250 current prototype paths) must be reconciled at the family/file level before declaring the content-role review complete.

This finding is kept open rather than silently replacing 242 or 245 with 248. A path/traceability record is not itself a claim-level audit or reproduction result.

## 5. PLAN.md reconciliation

The current PLAN still contains historical figures as if they were current in several places: 462/474 artifacts, 245 prototype files, and 24/94 RT/DEP counts. The current-main status paragraph records 493 research artifacts, 250 prototype paths, 26 RT areas, and 108 DEP edges, while explicitly noting that the main manifest remains at 488/248 until PR #149 is integrated. It also records that the B4 PR #152 is merged; B5/B6 audit reports remain branch-only in #151/#154.

The previous first-pass supersession cases remain scoped: Scenario 31 query representation; Scenario 32 parser-state bridge sketch; and the embedded ADR-0001 proposal. No whole-document supersession is inferred from those cases.

## 6. Remaining alignment gaps

- Reconcile the 242/245/248/250 prototype-family counts and identify the eight-file delta from the inventory aggregate.
- Update inventory/index references after PR #149 and B5 #151 are integrated; B4 #152 is already merged.
- Keep the ImpHash/ImplHash issue unresolved until an explicit decision.
- Complete index coverage review: current link existence does not prove every relevant artifact is discoverable from the intended index.
- Complete claim-level and reproducibility validation; file-role mapping does not prove claims.
- Preserve RT-24 and the option matrix as non-normative until explicit decisions are accepted.

**Disposition:** current taxonomy/dependency structure and candidate/non-normative statuses are aligned. Current taxonomy/dependency counts are 26/108. The inventory manifest's 488/248 counts are stale; current main has 493 research artifacts and 250 prototype files, derived from PR #146's recursive-tree audit plus the exact PR #126 and #152 commit deltas. Prototype-family role-review aggregate remains inconsistent and open. No architecture decision or RT-00 completion is claimed.

**Validation evidence:** PR #146 inventory audit run [44938305811](https://github.com/aivibeflow/LLMLang/actions/runs/44938305811) completed successfully and preserved artifact [14720512241](https://github.com/aivibeflow/LLMLang/actions/runs/44938305811/artifacts/14720512241). The original F PR #145 Required CI attempt was cancelled during successive branch updates; this replacement PR is based on b52ba2f and now targets current main b0142c2.
