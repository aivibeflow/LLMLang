# RT-00 E — Current-corpus local link and anchor audit

**Date:** 2026-11-21  
**Baseline main:** `017e64b87c87371309197a392165258b8b088dd1`  
**Workflow PR head:** `9ebb171b0e2134dd48d25ebf7241a1952492a522`  
**Exact scan checkout:** `60f3613b5196deee915011765fa6fdcd0920f6fe` (PR #142 merge ref)  
**Workflow run:** [#44937660874](https://github.com/aivibeflow/LLMLang/actions/runs/44937660874)  
**Tool:** Lychee 0.24.2, container digest `sha256:e2d19e57cf6ab037026f20b8e449a1f30d9d7f81eef4194763aab2eab20bd28d`

## 1. Scope and method

Scanned every tracked research Markdown/MDX file in the PR merge checkout:

- 250 `.md` files;
- 3 `.mdx` files;
- 253 documents total.

Lychee ran in offline mode with anchor-fragment checking enabled, using the repository root as the root for absolute local paths. External HTTP(S) availability was deliberately not tested. The scan covered `research/**/*.md` and `research/**/*.mdx`, including partial verbatim external snapshots. No auto-fix or content change was performed.

The scan's exact checkout is the merge commit `60f3613b5196deee915011765fa6fdcd0920f6fe`, which combines PR #142 head `9ebb171b0e2134dd48d25ebf7241a1952492a522` with main baseline `017e64b87c87371309197a392165258b8b088dd1`. Do not describe it as a later main commit.

## 2. Aggregate result

| Metric | Result |
|---|---:|
| Link occurrences processed | 2,871 |
| Unique links | 1,309 |
| Resolved/accepted | 1,629 |
| Error occurrences | 82 |
| Excluded (principally external links in offline mode) | 1,160 |

The audit process itself completed and uploaded its evidence. Lychee returned exit code 2 because it found 82 unresolved occurrences. The workflow intentionally records that non-zero result without failing the workflow job or Required CI.

## 3. Classification of all unresolved occurrences

All 82 errors are confined to the copied upstream MCP, OCI, and Alive2 snapshots. No unresolved project-authored relative link or anchor was reported.

| Snapshot group | Error occurrences | Classification |
|---|---:|---|
| MCP | 44 | Root-absolute paths from the upstream documentation site, such as `/specification/2026-07-28/...` and `/docs/draft/...`. These are site-root references in copied upstream content, not paths relative to the LLMLang repository. The prior corpus audit explicitly excluded root-absolute paths from local resolution. |
| OCI image-spec | 32 | Relative links to seven documents omitted from the deliberately partial snapshot: `media-types.md`, `annotations.md`, `image-index.md`, `considerations.md`, `conversion.md`, `config.md`, and `layer.md`. |
| Alive2 | 6 | Five image assets and `BugList.md` omitted from the README-only snapshot. |
| **Total** | **82** | **All errors are attributable to the three intentionally partial upstream snapshots.** |

The 32 OCI and six Alive2 occurrences reproduce the previously recorded 38 partial-snapshot misses. The 44 MCP entries are a newly explicit scanner classification of root-absolute upstream-site paths; they are not newly identified LLMLang-authored broken links.

## 4. Anchor coverage and limits

- Lychee checked anchor fragments for local Markdown targets where the target file was available.
- No broken anchor in a project-authored document was reported.
- A fragment on a missing target cannot be validated; those cases remain part of the snapshot-completeness limitations above.
- External URLs were excluded by offline mode. This audit does not establish their current availability, redirect behavior, or correctness.
- The tool's parsing and fragment behavior are bounded by Lychee 0.24.2; this is not a formal proof that every custom Markdown/MDX extension or generated runtime anchor is understood.

## 5. Evidence

Artifact [14719958917](https://github.com/aivibeflow/LLMLang/actions/runs/44937660874/artifacts/14719958917) contains:

- the exact checkout and file counts;
- Lychee version and resolved container digest;
- the raw link/anchor report;
- the recorded exit code.

Artifact ZIP SHA-256: `0bb655d299156a23be5f22aa74bce8a156383672f6d120a8f62768cd38110526`. The artifact is retained for 30 days, expiring 2026-12-21.

## 6. Disposition

**Current-corpus local link/anchor scan: completed for the 253 Markdown/MDX files at the pinned checkout.**

No LLMLang-authored broken local link or anchor was found in this pass. The remaining 82 errors are known upstream snapshot path/closure limitations and must not be “fixed” by rewriting verbatim source files. If self-contained snapshots are later required, add missing upstream files/assets only with their own pinned revisions, blob IDs, and license provenance.

External URL availability, full non-Markdown resource link validation, and index completeness against every research artifact remain separate tasks. This report does not claim RT-00 or PLAN.md §0.1 complete.
