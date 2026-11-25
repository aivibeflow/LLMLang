# RT-00 A — Current-main local link and anchor audit

**Date:** 2026-11-25
**Baseline:** `c06ad1b9c30c806dea0fddb8c362322f8587a5b3` (`main`)
**Scope:** repository-local links and anchors in all tracked research Markdown and MDX files, using the pinned Lychee workflow.
**Status:** complete for local targets at this revision; external URL reachability and omitted upstream snapshot targets remain open.

## Question and method

Does the workflow's previously recorded 256-file scan still describe the much larger current research tree, and are any current authored research links broken? The baseline was checked out in a detached worktree. I ran the same offline command used by `.github/workflows/research-link-anchor-audit.yml`, using Lychee 0.24.2 from Docker image digest `sha256:e2d19e57cf6ab037026f20b8e449a1f30d9d7f81eef4194763aab2eab20bd28d`.

```sh
docker run --rm \
  -v "$PWD:/input" -w /input \
  lycheeverse/lychee@sha256:e2d19e57cf6ab037026f20b8e449a1f30d9d7f81eef4194763aab2eab20bd28d \
  --offline --include-fragments --root-dir /input --no-progress --verbose \
  'research/**/*.md' 'research/**/*.mdx'
```

Environment: Linux 6.18.57 x86_64; 600 Markdown files and 3 MDX files. The scanner ran offline, so external URLs were not checked. The complete raw output was captured; its SHA-256 and summary are recorded in [the machine-readable result](RT-00-A-CURRENT-MAIN-LINK-ANCHOR-AUDIT-2026-11-25.json).

## Results

Lychee reported **5,580** links: **2,671** unique targets, **3,878** accepted, **82** errors, and **1,620** excluded. Its exit code was **2** because of the missing local targets. The workflow treats this as evidence-gathering and preserves the findings rather than failing Required CI.

All 82 errors originate in seven copied upstream snapshot documents: MCP (44), OCI (32), and Alive2 (6). No LLMLang-authored source was an error origin. The source files and per-file counts are listed in the JSON result. The same 82 errors persisted after new material entered `main`; this scan covers all 603 current Markdown/MDX documents at its pinned revision.

## Disposition and limits

- The earlier claim that the full current-corpus local scan remained open is closed for this exact revision and the workflow's local-path/available-anchor scope.
- Keep the 82 copied-snapshot errors visible; they are evidence of incomplete checked-in upstream snapshots, not proof that the upstream documents themselves are invalid.
- External HTTP availability, fragments on the missing pages, and completeness of MCP/OCI/Alive2 snapshot sources remain unverified. Resolving those requires authoritative upstream revisions or source documents; the offline workflow cannot supply them.
- This is a corpus evidence audit, not an architecture or language-semantics decision.
