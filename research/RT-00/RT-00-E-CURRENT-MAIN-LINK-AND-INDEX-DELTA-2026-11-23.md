# RT-00 E — Current-main link and index delta

**Date:** 2026-11-23  
**Repository:** aivibeflow/LLMLang  
**Current main baseline:** 9eba7eac2097983f31b5f2ca5274bc7926ed7f99  
**Baseline report:** [RT-00-E-GLOBAL-LINK-AND-ANCHOR-AUDIT-2026-11-21.md](RT-00-E-GLOBAL-LINK-AND-ANCHOR-AUDIT-2026-11-21.md)  
**Disposition:** four internal path typos corrected; intentionally incomplete external-snapshot references remain unresolved; navigation gaps are recorded without automatic orphan classification.

## 1. Scope and method

This delta reconciles the prior E audit with the latest full-corpus link/anchor and index-coverage runs. It covers Markdown/MDX paths, anchors, cross-RT references, README/index navigation, scenarios, prototypes, tests, fixtures, workflows, external snapshots, glossary, PLAN, and RT-00 reports.

The audit distinguishes:
- an actually broken repository-local path;
- a root-absolute upstream-site path that is not part of a deliberately partial snapshot;
- a missing relative file inside an intentionally partial external snapshot;
- a document with no inbound link from a designated index;
- an artifact with no inbound link at all.

These categories are not interchangeable. Missing index inbound is a discoverability observation, not proof that a document is an orphan or duplicate.

## 2. Latest pre-fix audit results

### 2.1 Research Link and Anchor Audit

Run [#45077341892](https://github.com/aivibeflow/LLMLang/actions/runs/45077341892), on the 584-artifact PR #243 tree:

| Metric | Result |
|---|---:|
| Link occurrences | 3,334 |
| Unique links | 1,549 |
| Successful | 1,896 |
| Errors | 86 |
| Excluded | 1,352 |

The 86 errors were all unresolved file targets; no anchor-specific failure was reported.

| Source | Errors | Interpretation |
|---|---:|---|
| MCP selected documentation | 44 | Root-absolute upstream-site paths to pages omitted from the local snapshot |
| OCI snapshot | 32 | Relative paths to omitted snapshot files |
| Alive2 snapshot | 6 | Five image assets and BugList.md are absent from the partial copy |
| LLMLang-authored documents | 4 | Incorrect RT-09 filename prefix |
| **Total** | **86** | **82 external-snapshot references; 4 internal path errors** |

The 44 MCP errors are **root-absolute upstream-site references**, not relative Markdown links. Lychee resolves these as local file paths when scanning the repository, so it reports them as missing. This distinction is now corrected in the D delta report and research/references/README.md.

### 2.2 Four internal RT-09 path errors — corrected in this PR

All four errors pointed to the nonexistent path:

research/RESEARCH-RT-09-STRUCTURAL-TYPE-IDENTITY-LAYOUT-AND-C-ABI-PROPOSAL.md

The intended target exists at:

research/RT-09-STRUCTURAL-TYPE-IDENTITY-LAYOUT-AND-C-ABI-PROPOSAL.md

The target's title and the surrounding text confirm the same RT-09 structural type identity/layout/C-ABI proposal. The four link occurrences were corrected, without changing the target document:
- one in research/LLMLang-CONCEPT.md;
- one in research/README.md;
- two in research/RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md.

This is a path-prefix typo, not a semantic ambiguity.

### 2.3 External-snapshot references — intentionally retained

The remaining 82 errors are the documented snapshot boundaries:
- MCP: 44 root-absolute upstream-site paths; schema $ref closure is separate and remains 277/277 resolved;
- OCI: 32 unresolved relative references;
- Alive2: six unresolved references.

No external page, image, or snapshot file was added. The REAPI's eight missing proto imports remain a separate import-closure limitation and are not part of the Markdown link count.

## 3. Index-coverage audit

Run [#45077342144](https://github.com/aivibeflow/LLMLang/actions/runs/45077342144), on the same 584-artifact tree:

| Metric | Result |
|---|---:|
| Research Markdown/MDX documents | 307 |
| Designated index documents | 16 |
| Local link occurrences | 2,017 |
| Non-Markdown targets | 488 |
| Documents with zero inbound links | 24 |
| Documents without inbound links from a designated index | 59 |
| Scenario documents | 136 |
| Scenarios with zero inbound links | 6 |
| Scenarios without designated-index inbound links | 31 |
| Unique inbound targets | 282 |
| Unresolved local targets | 42 |

The 42 unresolved local targets are exactly:
- four RT-09 path occurrences fixed above;
- six Alive2 snapshot references;
- 32 OCI snapshot references.

The 44 MCP root-absolute upstream-site paths are not included in this local-target count.

### 3.1 Zero-inbound documents

The pre-fix 24-document list is:

- Historical/prototype/research material: PROTOTYPE-01-RESULTS.md, PROTOTYPE-21-RESULTS.md, REPOSITORY-AUDIT-2026-11-17.md, RESEARCH-DEEP-COMPARISON.md, RESEARCH-RELATED-PROJECTS.md, RESEARCH-SYNTHESIS-01-CROSS-SCENARIO.md, RFC-REQUEST-CHANGE.md, TOKEN_EFFICIENCY.md.
- RT-00 audit reports: B-02b.2, B-02b.3, B-02b.4, and C-02 SQLite identity/source-archive integrity.
- Scenarios with zero inbound links: 01–04, 09, and 21.
- Snapshot files: MCP LICENSE.md, authorization.mdx, basic-index.mdx, transports.mdx, and OCI image-layout.md.
- RT-09 proposal: its inbound links were broken by the filename prefix typo and are corrected in this PR.

The snapshot files are intentionally selected external material. The historical reports and RT-00 audits need an explicit indexing decision in Stage F; they must not be deleted or silently treated as irrelevant.

### 3.2 Scenario navigation gaps

The 31 scenario documents without designated-index inbound links are:
- Scenarios 01–09 and 21;
- Scenario 31;
- Scenarios 58–63;
- Scenarios 80–93.

Six of these (01–04, 09, 21) also have zero inbound links from any document. The other 25 have some inbound reference but are not discoverable from a designated index under the audit's rule.

These are navigation gaps, not confirmed orphan artifacts. Do not add links mechanically or infer supersession from the absence of an index link. Stage F should compare the list with the semantic traceability report and decide whether a dedicated scenario index with explicit RT/role/status columns is warranted.

## 4. Semantic review and scope boundaries

- The four RT-09 references are corrected because the target title and surrounding context establish an unambiguous destination.
- The 82 external-snapshot references remain unresolved by design and are now described accurately in the references README.
- No other missing repository-local path or broken anchor was reported by the current scan.
- The scan does not prove that every valid link is semantically appropriate; it verifies target resolution. Semantic destination review remains necessary for high-impact cross-RT links.
- External URL availability was not established by this local audit.

## 5. Stage F alignment queue

The following items require deliberate indexing decisions:
1. Add B-02b.2, B-02b.3, B-02b.4, and C-02 to the research index or another clearly designated audit index.
2. Ensure the E baseline and this E delta are discoverable from the research README.
3. Review the historical zero-inbound documents and assign explicit active/historical/reference roles.
4. Decide whether to create a dedicated scenario index for the 31 scenario navigation gaps, rather than expanding the README with an ad hoc list.
5. Preserve the intentional partial-snapshot boundaries and the unresolved ImpHash / ImplHash terminology issue.

## 6. Conclusion

The current audit identified four fixable internal path typos and 82 external-snapshot references that must remain unresolved under the current snapshot policy. The four RT-09 links are corrected in this PR. The external references remain documented limitations, not provenance-integrity failures.

The index audit exposes a finite set of discoverability gaps, especially in RT-00 audit reports and scenario navigation. These require semantic index decisions in Stage F; they do not justify deleting historical material or automatically classifying documents as orphans.
