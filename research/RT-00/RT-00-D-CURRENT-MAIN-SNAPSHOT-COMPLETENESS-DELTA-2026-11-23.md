# RT-00 D — Current-main external snapshot completeness delta

**Date:** 2026-11-23  
**Repository:** `aivibeflow/LLMLang`  
**Current main baseline:** `089b1ad108907b3f37124b9e4e6537338b84cd02`  
**Baseline report:** [RT-00-D-EXTERNAL-SNAPSHOT-PROVENANCE-AUDIT-2026-11-20.md](RT-00-D-EXTERNAL-SNAPSHOT-PROVENANCE-AUDIT-2026-11-20.md)  
**Disposition:** provenance integrity remains confirmed; current-main link scanning exposes an additional MCP documentation-completeness limit. No snapshot content was copied or modified.

## 1. Scope

This delta checks whether PR #119's provenance/completeness conclusions are accurately represented in `research/references/README.md`, and reconciles them with the current repository-local link audit. It does not refresh upstream snapshots or replace the pinned historical revisions.

The prior audit's 13/13 upstream/local Git blob identity result remains the provenance baseline. The current audit does not establish that the selected snapshots are self-contained documentation or compilation bundles.

## 2. PR #119 and README alignment

PR #119 is merged. The current reference register records all four pinned upstream revisions, local snapshot paths, licence files, and the upstream blob manifest. It explicitly documents:
- OCI's 32 unresolved relative-link occurrences;
- Alive2's six unresolved references (five image assets and `BugList.md`);
- REAPI's eight missing proto imports;
- the MCP JSON Schema's 155 top-level `$defs` and 277 local `$ref` references.

The README's statement that the MCP schema references resolve is accurate, but it covers JSON Schema references only. It does not describe the root-absolute upstream-site path references from the three selected MCP documentation pages to omitted specification pages. That is an additional completeness limitation discovered by the global link audit.

## 3. Current-main link audit evidence

Research Link and Anchor Audit [run #45077018569](https://github.com/aivibeflow/LLMLang/actions/runs/45077018569), on the 583-artifact PR #242 tree, reported:

- 3,330 link occurrences;
- 1,546 unique links;
- 1,893 successful;
- 86 errors;
- 1,351 excluded.

The 86 errors divide as follows:

| Source group | Unresolved occurrences | Breakdown |
|---|---:|---|
| MCP documentation snapshot | 44 | `authorization.mdx`: 11; `basic-index.mdx`: 23; `transports.mdx`: 10 |
| OCI snapshot | 32 | `descriptor.md`: 6; `image-layout.md`: 7; `manifest.md`: 19 |
| Alive2 snapshot | 6 | `BugList.md` plus five image assets |
| LLMLang-authored documents | 4 | One in `LLMLang-CONCEPT.md`, one in `research/README.md`, two in the RT-04 alternatives report |
| **Total** | **86** | **82 snapshot references and 4 internal references** |

### 3.1 MCP — additional partial-documentation finding

The 44 unresolved MCP root-absolute path references originate in the three selected documentation pages and target omitted paths under the pinned `specification/2026-07-28/` tree and `docs/draft/tutorials/`. The selected MCP snapshot therefore preserves its declared source files and licence, but it is not a closed documentation tree.

This is separate from the JSON Schema check: all 277 local `$ref` references in the copied schema still resolve. Schema reference closure does not establish Markdown/MDX documentation-link closure.

### 3.2 OCI and Alive2 — previously documented limitations corroborated

The current link audit independently reproduces the 32 OCI unresolved relative links and six Alive2 unresolved references already recorded by the D baseline and reference README. These do not indicate blob-provenance failure; the local copies are intentionally partial.

### 3.3 Internal LLMLang links — Stage E, not snapshot provenance

The four non-snapshot errors all point to the same nonexistent path:
`research/RESEARCH-RT-09-STRUCTURAL-TYPE-IDENTITY-LAYOUT-AND-C-ABI-PROPOSAL.md`.

The intended target exists at:
`research/RT-09-STRUCTURAL-TYPE-IDENTITY-LAYOUT-AND-C-ABI-PROPOSAL.md`.

The target title and the surrounding references in LLMLang Concept and RT-04 confirm that this is a path-prefix typo. Correct these four internal links in the separate Stage E PR. They are not external-snapshot defects.

## 4. Provenance integrity remains unchanged

The pinned sources remain:
- MCP stable specification 2026-07-28, commit `5f5440bb26a62e2cf3440b92da5a667efa03b267`;
- OCI Image Specification, commit `4feed4a6674e59d301b9294f187ac46acb2de99f`;
- Alive2, commit `3bdd4f5e1cefa47057e93110e707acd11cfe08e4`;
- Bazel Remote Execution API, commit `e0c0554bfc8a37abf336c3e78070684367738e1d`.

The prior audit verified the upstream path/blob identities and the local Git blob identities for all 13 stored source/licence files. The newly observed missing relative links do not change those blob identities and do not indicate an unmanifested or modified snapshot file.

The REAPI import closure remains incomplete: eight imports are referenced, none is included locally; one is available in the pinned upstream repository and seven are external Google API/Protobuf dependencies. This is not represented in the Markdown link-error count.

## 5. Required reference-register clarification

The MCP entry in `research/references/README.md` now explicitly states:
- the documentation snapshot is selected and intentionally partial;
- 44 root-absolute upstream-site path occurrences lead to omitted documentation pages;
- the 277 resolved schema references are a separate result;
- no full documentation-link closure is claimed.

The existing OCI, Alive2, and REAPI limitations remain unchanged. No external pages, images, proto files, or licence files were copied to reduce the unresolved count.

## 6. Scope limits and next steps

1. Preserve the 13-file provenance manifest and all historical snapshots unchanged.
2. Do not copy omitted MCP/OCI/Alive2/REAPI content merely to make local links resolve.
3. Correct the four LLMLang-authored RT-09 links in Stage E, where global link and anchor repair is handled.
4. Keep REAPI's missing proto import closure unresolved until a separately justified dependency-closure study is performed.
5. If current upstream behavior is needed, perform a separate version-update comparison; do not silently move the pinned historical baseline.

## 7. Conclusion

PR #119's provenance-integrity result remains valid, and its README already describes the OCI, Alive2, and REAPI limitations. The global link audit exposed one missing statement: the selected MCP documentation pages have 44 unresolved root-absolute upstream-site path references even though the JSON Schema's 277 local references resolve. The reference README now records that distinction.

The external snapshots remain intentionally incomplete and provenance-verifiable. The correct response is to document the boundary, not to expand the snapshots without a research need.
