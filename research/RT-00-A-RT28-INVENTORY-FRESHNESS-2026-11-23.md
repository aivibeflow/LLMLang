# RT-00 A — RT-28 Inventory Freshness Reconciliation (2026-11-23)

**Research item:** `PLAN.md` §0.1 — Reconcile the research corpus  
**Baseline:** current `main` `f52b5d0580c589b4aaf8333a237e5bc4ec8df9b3` (after PR #251)  
**Question:** Does the research inventory represent the newly merged RT-28 registration and current taxonomy/dependency records?  
**Disposition:** The exact tree has 593 research files excluding the inventory. The 592-record manifest omits the RT-28 research brief and has stale blob/size identities for `research/README.md`, `research/RESEARCH-DEPENDENCY-MAP.md`, and `research/RESEARCH-TAXONOMY.md`. It has no extra paths.

## Exact tree and register counts

A recursive `git ls-tree -r --name-only origin/main research` audit found:

| Measure | Exact `main` value |
|---|---:|
| Research files, excluding the inventory | 593 |
| Markdown / MDX | 312 / 3 |
| Python / Lean | 226 / 33 |
| Prototype-tree paths | 289 |
| Broad Scenario-named paths | 137 |
| Taxonomy rows | 28 (RT-01–RT-28) |
| Dependency rows | 135 (DEP-001–DEP-135) |

Comparing every path, Git blob SHA-1, and byte length against the manifest gives **one missing record**, **zero extra records**, and **three stale existing identities**. The missing path is `research/RT-28-INCREMENTAL-POLYGLOT-MIGRATION-AND-SEMANTIC-MIRRORING.md`. The stale records are README (manifest SHA `36ae04660f609f2dbe9a703f1ca8f392c3ac341a`, current SHA `476ad29a663af2dcbfa410a205f8ae02852ae11b`, 35,711 → 36,185 bytes), dependency map (manifest SHA `7d90ad03d5f8164a4a0071c0d5b2cd0a42f53e97`, current SHA `cd49bfecfac3663d3ff2d9768d03db09e783501a`, 53,245 → 60,053 bytes), and taxonomy (manifest SHA `dcd5f0e79f9f4dd8c19323abd35a25e938f0736e`, current SHA `a398659414f0e3989e5f283a69f712c8ac6c0382`, 48,031 → 49,696 bytes).

The current-tree index scan also found one newly unresolved LLMLang-authored target: the RT-24 taxonomy row used `...DIFF-AND-THREE-WAY-MERGE.md`, while the tracked report is `...DIFF-AND-MERGE.md`. This PR corrects the link. After correction, the remaining 38 unresolved local targets are in the partial OCI and Alive2 snapshots.

The exact comparison reads each path with `git show origin/main:<path>`, hashes Git blob framing plus bytes with SHA-1, and compares byte lengths to the JSON records. This is a path/blob/size reconciliation, not semantic review of the new RT-28 brief or its 27 new dependency hypotheses.

## Plan and remaining dependencies

PR #251 registered RT-27 and RT-28 and added DEP-109–DEP-135; the updated registers contain 28 areas and 135 edges. Their presence does not validate the new edges. RT-27's physical storage format remains undecided, and RT-28's migration experiment still depends on stabilized identity, import/export, semantic merge, representative source workloads, and exact source-to-mirror correspondence. Those remain research dependencies, not evidence that any repository format or migration architecture has been selected.

This report closes only the inventory freshness delta after PR #251. Claim/reproducibility validation, corpus-wide semantic overlap review, and external snapshot/index completeness remain open under §0.1.
