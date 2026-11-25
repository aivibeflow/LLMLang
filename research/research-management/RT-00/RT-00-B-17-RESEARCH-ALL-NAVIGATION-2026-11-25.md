# RT-00 B17 — Research navigation on the shared branch

**Scope:** PLAN §0.1, [issue #284](https://github.com/aivibeflow/LLMLang/issues/284). Exact Git tree at `d5b70342ca46de02d4310391850034167d64e621` and that same tree with four curated direction indexes and two research citation repairs.

## Question and method

Can a reader still reach each research artifact after the recent studies and thematic moves? The [B10 audit](RT-00-B-10-INDEX-REACHABILITY-2026-11-24.md) found full reachability after an earlier round of curated index links. We reused its two path models. Both start from `PLAN.md` and `research/README.md`. The document model follows parsed inline and declared reference paths. The directory model also allows browsing the tracked descendants of a linked research directory.

```mermaid
flowchart LR
    Roots["PLAN and research index"] --> Docs["Follow parsed local document links"]
    Docs --> Found["Reach the linked file"]
    Docs --> Browse["Browse an explicitly linked directory"]
    Browse --> Found
```

The two models differ when an artifact's page lacks its own link but a researcher can browse to it. In particular, copied upstream files can be grouped by source in the reference register, while direct links to historical first-party scenarios can make them easier to find.

## Results and disposition

| Measure | Pinned tree | Pinned tree with navigation fixes |
| --- | ---: | ---: |
| Tracked research artifacts | 1,793 | 1,793 |
| Markdown/MDX documents | 634 | 634 |
| Artifacts reached by document links | 1,483 | 1,496 |
| Documents reached by document links | 614 | 627 |
| Artifacts reached with directory browsing | 1,793 | 1,793 |
| Documents reached with directory browsing | 634 | 634 |
| Documents without a direct designated-index link | 52 | 39 |
| Documents without incoming parsed document links | 18 | 5 |
| Unresolved parsed local paths | 56 | 38 |

All files were already discoverable in the directory model. The [path ledger](RT-00-B-17-RESEARCH-ALL-NAVIGATION-2026-11-25.json) identifies exactly 20 documents that initially required directory browsing. Thirteen were first-party material from the [B8 candidate review](RT-00-B-08-ZERO-INBOUND-CANDIDATE-REVIEW-2026-11-23.md). We assigned them direct navigation in their direction indexes:

- Language design links two historical prior-art reports, Scenario 03, and the exploratory token-efficiency notes.
- Semantic representation links Scenarios 01 and 09 and the historical Prototype 01 result.
- Toolchain and collaboration links Scenario 02 and the historical Request and Change Set RFC proposal.
- Research management links the three prior RT-00 audit installments and the SQLite identity follow-up.

The seven remaining directory-only documents belong to the MCP and OCI snapshots. Two of those seven have incoming links from other snapshot pages that also require browsing. The [reference register](../../references/README.md) provides the upstream grouping. No copied snapshot page was edited. The baseline has 18 unresolved first-party path occurrences. Six links in the [Dafny comparison](../../COMPARISON-DAFNY-LLMLANG.md) use pre-relocation paths. Twelve in the [draft evidence crosswalk](RT-00-C-DRAFT-EVIDENCE-CROSSWALK-2026-11-25.md) use the wrong relative directory depth. That crosswalk also pointed the Scenario 109–111 fragment at the wrong index. The corrected index contains the named heading. After those repairs, all 38 unresolved path occurrences originate in copied upstream documentation. This scanner considers paths and applies its own Markdown extraction rules. The [separate Lychee audit](RT-00-A-CURRENT-MAIN-LINK-ANCHOR-AUDIT-2026-11-25.md) includes different path and fragment rules on a different tree, so its count is a separate observation.

A direct link from a designated index for every source and test would increase catalog size without changing directory reachability. We added links for the first-party documents requiring browsing and retained hierarchical navigation for executable siblings and snapshots. The 39 candidates without a direct designated-index link still have a transitive route. This check establishes structural discovery on the pinned tree. Semantic orphan classification, external URL and fragment validity, and cross-report supersession require additional evidence.

## Reproduce

Use CPython 3.12.14 and Git 2.56.1 from a checkout containing the baseline and this report's publication commit. The second archive overlays the four direction-index edits and the two citation repairs. This isolates the effect of the navigation changes from later tree growth.

```sh
set -eu
baseline=d5b70342ca46de02d4310391850034167d64e621
report=research/research-management/RT-00/RT-00-B-17-RESEARCH-ALL-NAVIGATION-2026-11-25
publication=$(git log --diff-filter=A -1 --format=%H -- "$report.md")
scratch=$(mktemp -d)
mkdir "$scratch/baseline" "$scratch/curated"
git archive "$baseline" | tar -x -C "$scratch/baseline"
git archive "$baseline" | tar -x -C "$scratch/curated"
git diff "$publication^" "$publication" -- \
  research/language-design/README.md research/semantic-representation/README.md \
  research/toolchain-and-collaboration/README.md research/research-management/README.md \
  research/COMPARISON-DAFNY-LLMLANG.md \
  research/research-management/RT-00/RT-00-C-DRAFT-EVIDENCE-CROSSWALK-2026-11-25.md \
  > "$scratch/navigation.diff"
(cd "$scratch/curated" && git apply "$scratch/navigation.diff")
python3 -B .github/scripts/audit_research_index_reachability.py \
  --baseline-dir "$scratch/baseline" --baseline-revision "$baseline" \
  --target-dir "$scratch/curated" --output "$scratch/comparison.json"
cmp "$scratch/comparison.json" "$report.json"
```

These are enumeration counts for the specified trees. Mermaid source was inspected directly.
