# RT-00 B7 — Current-main exact-content and index recheck

**Date:** 2026-11-23  
**Main baseline:** `02d0c3d065e160277b498e106646e8a02f2a43fd`  
**Scope:** exact Git-blob grouping and the repository's index-coverage auditor; no broad semantic duplicate or claim review.

## Exact tree and blob result

Enumerated `git ls-tree -r` at the baseline and excluded only `research/RESEARCH-CORPUS-INVENTORY-2026-11-20.json`. The tree contains **607 research artifacts**: 324 Markdown, 3 MDX, 227 Python, 33 Lean, and 289 prototype paths. The 607 paths use **606 distinct Git blobs**. The only repeated group is SHA `d645695673349e3947e8e5ae42332d0ac3164cd7`, shared by:

- `research/references/snapshots/OCI/LICENSE-APACHE-2.0.txt`
- `research/references/snapshots/REAPI/LICENSE-APACHE-2.0.txt`

This is the same intentional Apache-2.0 license duplicate identified in the earlier corpus audit. No other byte-identical pair exists in this exact tree. This does not test semantic similarity between distinct blobs.

## Index coverage and correction

Ran `.github/scripts/audit_research_index_coverage.py` against the exact baseline checkout and repeated it against the same working tree after correcting one LLMLang-authored taxonomy link to the actual RT-24 report filename. The first pass reported 39 unresolved local targets; the corrected pass reported **38**, all within copied upstream snapshots (32 OCI, 6 Alive2). The only LLMLang-authored unresolved target was the stale RT-24 filename in `RESEARCH-TAXONOMY.md`, now corrected to `RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md`.

The post-correction audit scanned 327 Markdown/MDX research documents and the repository-level `PLAN.md` (328 documents total), 18 designated index documents, and 2,089 local-link occurrences. It recorded 495 non-Markdown targets, 304 unique research targets with inbound links, 57 documents without a link from a designated index, and 23 documents with zero inbound links. Those are **review candidates**, not proven semantic orphans: this conservative script counts links, not whether links are implied by a broader index or whether the document is obsolete. Six Scenario reports are among the zero-inbound candidates. The full content review is still required before any artifact is classified or removed.

## Reproduction and limits

```sh
python3 -B .github/scripts/audit_research_index_coverage.py \
  --root . \
  --output-json /tmp/rt00-index-coverage.json \
  --output-md /tmp/rt00-index-coverage.md \
  --revision 02d0c3d065e160277b498e106646e8a02f2a43fd
```

Exact-blob grouping used the same pinned Git tree. After the one-path correction, the coverage auditor was rerun with the `--revision` label `02d0c3d065e160277b498e106646e8a02f2a43fd+taxonomy-path-fix`; the path/blob result is revalidated by the PR inventory-freshness workflow on the final PR tree. This report does not perform paragraph/claim-level duplicate review, test reproduction, or full orphan/supersession/contradiction classification.

**Remaining dependencies:** content review of zero-inbound/no-index-link candidates; claim-level and tool-version reproduction across experiments; external snapshot completeness/URL reachability; Scenario 16 intent. The remaining 38 unresolved local targets belong to partial upstream snapshots (Alive2/OCI), whose missing files are outside the LLMLang corpus. Keep these findings explicit in PLAN §0.1; do not infer that every no-inbound result is an orphan.
