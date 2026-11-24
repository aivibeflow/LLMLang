# RT-00 A — Current-main inventory reconciliation

**Date:** 2026-11-24  
**Exact main baseline:** `548182a67afac67c0403c7bef5a7cd84cff821f0` (PRs #421, #424, #426, #427, #428, and #430 merged)
**Prior manifest revision:** `9135dfbe7724e12f2bbd664b53d860ec2f428d8b`  
**Scope:** exact tracked research path/blob/size reconciliation and first-pass individual role triage for paths absent from the prior inventory.  
**Disposition:** metadata reconciliation complete for this pinned main; this is not claim-level validation, experiment reproduction, or completion of PLAN §0.1.

## Question and method

Did the corpus inventory still describe current `main`, and can newly added research files receive explicit, evidence-backed roles without guessing their research-area ownership? Checked the fresh `origin/main` head and open PRs before updating. Enumerated the exact Git tree with `git ls-tree -r --full-tree <revision> research`, excluded the inventory manifest itself, took sizes from `git cat-file -s`, and compared every path, blob SHA, and byte size with the prior manifest. Read family READMEs, file headers, direct PLAN/index links, and paired evidence for added paths; assigned categories and RT/Stage mappings only when those sources supported them. Existing semantic metadata was preserved for unchanged paths.

```mermaid
flowchart TD
    A[Pin main revision] --> B[Enumerate tracked research paths]
    B --> C[Compare path, blob SHA, and byte size]
    C --> D{Previously recorded?}
    D -->|No| E[Read family docs and direct cross-references]
    E --> F[Assign first-pass role and RT/Stage mapping]
    D -->|Yes, blob changed| G[Refresh exact Git metadata]
    G --> H[Revalidate prior semantic mapping]
    F --> I[Keep claim and reproduction checks separate]
    H --> I
```

## Exact inventory results

At main `548182a67afac67c0403c7bef5a7cd84cff821f0`, the tree contains **785 tracked research artifacts**, excluding its manifest. The prior manifest had 610 records. Exact comparison to that prior snapshot found **175 paths absent** and **24 existing paths with stale blob SHA and/or byte size**, with **zero manifest-only paths**. This PR adds its own reconciliation report, so its tree has 786 inventory records. All 176 new paths in the PR tree received a first-pass category, RT/stage mapping, and role basis. The 24 existing changed paths retain their prior semantic fields pending content-role revalidation; exact Git metadata does not validate those mappings.

Main counts at the pinned revision: 385 Markdown, three MDX, 261 Python, 70 JSON, 40 Lean, 12 text, three Rust, three C, three MJS, two CSV, one `SHA256SUMS`, one JSONL, one `lean-toolchain`, one TOML, and one Proto file; 302 prototype paths, 136 strict scenario-named documents, 29 registered taxonomy areas, and 136 dependency-map edges. The PR tree inventory has 786 records including this report. Its category counts sum to 786. Registration and inventory classification do not imply acceptance or correctness.

The 175 added paths include a 102-file RT-33 Proof Obligation Benchmark family, seven RT-02 contract corpus files, RT-25 allocator measurement assets and report, current RT-00 review/evidence files, and newly registered RT-29–RT-35 briefs. The POB README explicitly describes public development fixtures and bounded passes; the contract corpus distinguishes semantic-fidelity review from downstream proof; RT-25 records a single-host, eight-sample-per-provider synthetic comparison with overlapping time ranges. These are role assignments and evidence boundaries, not independent adjudications of every result.

## Link-coverage recheck

Ran:

```sh
python3 .github/scripts/audit_research_index_coverage.py --revision 1e7e4d99f266b6410742e1af1a9680d93231686f
```

The auditor scanned 388 documents (387 research Markdown/MDX plus `PLAN.md`), 21 designated indexes, and 2,560 local-link occurrences. It reported 23 research documents with zero inbound links, 57 without a designated-index inbound link, and 38 unresolved local targets; there are 660 non-Markdown targets and 364 uniquely linked research targets. This report is itself indexed by `research/README.md` in the PR tree; the counts above are pinned to the main baseline before this PR report is added. The target provenance behind those 38 is carried forward from earlier bounded audits and has not been independently reclassified at this revision. Link counts nominate review candidates; they do not establish orphan status.

## Open PR boundary

PRs #421, #424, #426, #427, #428, and #430 merged during this reconciliation and are included in the final main baseline. At the latest open-PR check, #431 and #423 remained open; their branch-only RT-33 paths are not included. Refresh the inventory again after any of them merges.

## Remaining work and decision relevance

The refreshed manifest closes the exact metadata and first-pass role gap for this pinned main. It does **not** close Stage 0.1: 24 changed existing paths need content-role revalidation; corpus-wide semantic duplicate/supersession/orphan/contradiction review remains incomplete; prototype claims, generated outputs, exact tool versions, and experiment environments still need validation; and external snapshot URL availability/completeness remains unverified. Consequently this study improves navigation and makes evidence scope explicit but does not itself select an LLMLang implementation option. The pending requirements are recorded in `PLAN.md` §0.1.
