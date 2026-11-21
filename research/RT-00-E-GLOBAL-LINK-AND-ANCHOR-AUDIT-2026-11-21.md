# RT-00 E — Current-corpus local link and anchor audit

**Date:** 2026-11-21  
**Baseline main:** `017e64b87c87371309197a392165258b8b088dd1`  
**Workflow PR head:** `46e3434a4495f398aaa3a91e445a0a2635845751`  
**Exact scan checkout:** `1051024f61d98dcc4c6a5c7d09b30de1adcf4e48` (PR #142 merge ref)  
**Workflow run:** [#44937753370](https://github.com/aivibeflow/LLMLang/actions/runs/44937753370)  
**Tool:** Lychee 0.24.2, container digest `sha256:e2d19e57cf6ab037026f20b8e449a1f30d9d7f81eef4194763aab2eab20bd28d`

## 1. Scope and method

Scanned every tracked research Markdown/MDX file in the PR merge checkout:

- 251 `.md` files;
- 3 `.mdx` files;
- 254 documents total.

Lychee ran in offline mode with anchor-fragment checking enabled, using the repository root as the root for absolute local paths. External HTTP(S) availability was deliberately not tested. The scan covered `research/**/*.md` and `research/**/*.mdx`, including partial verbatim external snapshots. No auto-fix or content change was performed.

The scan's exact checkout is the merge commit `60f3613b5196deee915011765fa6fdcd0920f6fe`, which combines PR #142 head `9ebb171b0e2134dd48d25ebf7241a1952492a522` with main baseline `017e64b87c87371309197a392165258b8b088dd1`. Do not describe it as a later main commit.

## 2. Aggregate result

| Metric | Result |
|---|---:|
| Link occurrences processed | 2,876 |
| Unique links | 1,312 |
| Resolved/accepted | 1,630 |
| Error occurrences | 82 |
| Excluded (principally external links in offline mode) | 1,164 |

The audit process itself completed and uploaded its evidence. Lychee returned exit code 2 because it found 82 unresolved occurrences. The initial run was refreshed after adding the E report itself; this final run includes that report and the corpus-audit addendum. The workflow intentionally records that non-zero result without failing the workflow job or Required CI.

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

Artifact [14719949418](https://github.com/aivibeflow/LLMLang/actions/runs/44937753370/artifacts/14719949418) contains:

- the exact checkout and file counts;
- Lychee version and resolved container digest;
- the raw link/anchor report;
- the recorded exit code.

Artifact ZIP SHA-256: `b71fd8822f47d5e3f509e5188318a578ac776c43a5ae93f1d3cfe2cf48599ad1`. The artifact is retained for 30 days, expiring 2026-12-21.

## 6. Disposition

**Current-corpus local link/anchor scan: completed for the 253 Markdown/MDX files at the pinned checkout.**

No LLMLang-authored broken local link or anchor was found in this pass. The remaining 82 errors are known upstream snapshot path/closure limitations and must not be “fixed” by rewriting verbatim source files. If self-contained snapshots are later required, add missing upstream files/assets only with their own pinned revisions, blob IDs, and license provenance.

External URL availability, full non-Markdown resource link validation, and index completeness against every research artifact remain separate tasks. This report does not claim RT-00 or PLAN.md §0.1 complete.
