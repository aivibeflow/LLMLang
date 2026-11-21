# RT-00 E — Current-corpus local link and anchor audit

**Date:** 2026-11-21  
**Baseline main:** `b0142c27f5632a859c379b78a10cb22f500ebfd8`  
**Workflow PR head:** `93260d37252f6a69690b2dbcee01f29433af9ea9`  
**Exact scan checkout:** `94f459d4facfde50ca0eae62d5b801e1d1f6ff96` (PR #160 merge ref)  
**Workflow run:** [#44942627405](https://github.com/aivibeflow/LLMLang/actions/runs/44942627405)  
**Tool:** Lychee 0.24.2, container digest `sha256:e2d19e57cf6ab037026f20b8e449a1f30d9d7f81eef4194763aab2eab20bd28d`

## 1. Scope and method

Scanned every tracked research Markdown/MDX file in the PR merge checkout:

- 253 `.md` files;
- 3 `.mdx` files;
- 256 documents total.

Lychee ran in offline mode with anchor-fragment checking enabled, using the repository root as the root for absolute local paths. External HTTP(S) availability was deliberately not tested. The scan covered `research/**/*.md` and `research/**/*.mdx`, including partial verbatim external snapshots. No auto-fix or content change was performed.

The scan checkout is merge commit `9b780f67b3e4a33cee32e3e0c0200ea395be1848`, combining PR #160 head `8ce8653fa159cdb63edf8939589c49c6ed732314` with current main `b0142c27f5632a859c379b78a10cb22f500ebfd8`. It includes the RT-23 report/test, merged B4 report, and this E report. This is the exact PR merge ref, not a later main commit.

## 2. Aggregate result

| Metric | Result |
|---|---:|
| Link occurrences processed | 2,891 |
| Unique links | 1,318 |
| Resolved/accepted | 1,641 |
| Error occurrences | 82 |
| Excluded (principally external links in offline mode) | 1,168 |

The audit process itself completed and uploaded its evidence. Lychee returned exit code 2 because it found 82 unresolved occurrences. This refreshed run includes the current main baseline, RT-23 and B4 merged reports, the E report itself, and the corpus-audit addendum. The workflow intentionally records that non-zero result without failing the workflow job or Required CI.

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

Artifact [14721939022](https://github.com/aivibeflow/LLMLang/actions/runs/44942627405/artifacts/14721939022) contains:

- the exact checkout and file counts;
- Lychee version and resolved container digest;
- the raw link/anchor report;
- the recorded exit code.

Artifact ZIP SHA-256: `a7b505492b4d54e786bb7cf6bc08725f6c4eaef7a3b0c88fcba07feb91de0804`. The artifact is retained for 30 days, expiring 2026-12-21.

## 6. Disposition

**Current-corpus local link/anchor scan: complete for the pinned PR merge checkout (256 Markdown/MDX documents).** The scan processed 2,890 occurrences (1,318 unique): 1,641 accepted, 82 errors, and 1,167 excluded. All 82 errors remain confined to the copied upstream MCP/OCI/Alive2 snapshots.

No LLMLang-authored broken local link or anchor was found in this pass. The remaining 82 errors are known upstream snapshot path/closure limitations and must not be “fixed” by rewriting verbatim source files. If self-contained snapshots are later required, add missing upstream files/assets only with their own pinned revisions, blob IDs, and license provenance.

External URL availability, full non-Markdown resource link validation, and index completeness against every research artifact remain separate tasks. This report does not claim RT-00 or PLAN.md §0.1 complete.
