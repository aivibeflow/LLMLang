# RT-00 E-02 — Curated external reference reachability check

**Date:** 2026-11-21  
**Baseline:** `b0142c27f5632a859c379b78a10cb22f500ebfd8`  
**Scope:** all external URLs in `research/references/README.md` §2, excluding local snapshot links.  
**Disposition:** 16 references returned page/PDF content; the POSIX publication endpoint returned HTTP 403 to the checker. This is a one-time reachability observation, not a permanent availability or content-integrity guarantee.

## 1. Result

| Result | Count | Interpretation |
|---|---:|---|
| Content retrieved | 16 | URL resolved and returned page/PDF content during this check |
| Access denied | 1 | POSIX site returned 403; availability is indeterminate, not classified as broken |
| Broken/404 confirmed | 0 | No definitive missing-resource response observed |
| **Total checked** | **17** | Every external URL in the curated §2 table |

## 2. Per-reference observations

| Reference | Result | Versioning / freshness note |
|---|---|---|
| SMT-LIB 2.7 standard PDF | Content retrieved | Versioned release dated 2026-09-09; document itself permits verbatim redistribution under retained notices |
| cvc5 1.4.2 proof production | Content retrieved | Versioned documentation path |
| Lean Language Reference `latest` | Content retrieved | Page identifies its covered version as 4.37.0-rc1 |
| Lean releases | Content retrieved | v4.37.0-rc1 is listed as a pre-release; v4.36.0 is marked latest stable |
| LLVM Language Reference | Content retrieved | Live documentation; no release/commit is encoded in the URL |
| LLVM Undefined Behavior Manual | Content retrieved | Live documentation; no release/commit is encoded in the URL |
| Rust Reference — destructors | Content retrieved | Live documentation; no toolchain/reference revision is encoded in the URL |
| Go Memory Model | Content retrieved | Live documentation; no Go release is encoded in the URL |
| C++ working draft — data races | Content retrieved | Living working draft; no frozen draft revision is encoded in the URL |
| SQLite `sqlite3_close` reference | Content retrieved | Live documentation; experiment build identity must remain separately pinned |
| SQLite Online Backup API | Content retrieved | Live documentation; experiment build identity must remain separately pinned |
| SQLite threading modes | Content retrieved | Live documentation; experiment build identity must remain separately pinned |
| Git pack format | Content retrieved | Live documentation; record Git version/object format in experiments |
| Git protocol v2 | Content retrieved | Live documentation; record Git version/protocol negotiation in experiments |
| Nix content-addressed store objects 2.35 | Content retrieved | Versioned manual path |
| Nix store path specification 2.35 | Content retrieved | Versioned manual path |
| POSIX Issue 8 online specifications | HTTP 403 | Checker could not retrieve content; do not classify as deleted or broken without an alternate authorized check |

## 3. Interpretation

The check establishes only that 16 URLs returned content and one endpoint denied this checker access at the observation time. It does not validate the technical correctness of any reference, confirm that the linked content is the edition intended by a research claim, or prove long-term availability.

The curated references divide into two groups:

- **Version-addressed material:** SMT-LIB 2.7, cvc5 1.4.2, Nix 2.35. These URLs identify an explicit release/version.
- **Moving references:** Lean `latest`, LLVM docs, Rust Reference, Go Memory Model, C++ working draft, SQLite docs, Git docs, and POSIX. Their version/revision must be recorded at the point of use. The Lean release page currently distinguishes 4.37.0-rc1 from stable 4.36.0.

The POSIX 403 is a retrieval limitation. The link remains unresolved for reachability purposes; a 403 does not prove the resource is absent.

## 4. Relationship to the broader E audit

The current-main offline local-link scan in [PR #160](https://github.com/aivibeflow/LLMLang/pull/160) checks relative paths and anchors across the Markdown/MDX corpus. This report complements it by checking the curated external-reference table only. It is not a corpus-wide scan of every external URL occurrence.

The local snapshot provenance result remains separate: 13/13 local snapshot blobs match the pinned upstream blob IDs. Local blob integrity does not imply that every external reference is live or that partial snapshots are self-contained.

## 5. Reproduction

The 17 URLs listed in `research/references/README.md` §2 were opened individually on 2026-11-21. The result classification is based on whether content was returned, not on an inferred status from a search snippet. POSIX returned 403. No retry, alternate mirror, authentication, or content substitution was used.

No source snapshots, links, licenses, or research claims were changed by this check.
