# RT-00 — Research report structure recheck

**Research item:** `PLAN.md` §0.2 — consistent report structure  
**Date:** 2026-11-24  
**Baseline main:** `0aa0527b0df36b94ba3b4ec4a4bd06aca0db2915`  
**Evidence type:** bounded structural review of five implementation-relevant research reports  
**Status:** selected-report audit; no corpus-wide migration or policy adoption  
**Question:** Do recent studies provide the minimum information in the proposed research schema, even when they use different headings and combine sections?

## Method

I compared the minimum report structure in [Research Quality and Decision Rules](../RESEARCH-QUALITY-AND-DECISION-RULES-2026-11-20.md) with the RT-19 transaction/recovery comparison, RT-19 multi-file publication recheck, RT-25 workload-fit recheck, RT-32 Lean observation-binding report, and RT-13 LLVM checked-add report present in the pinned main tree. I mapped information by content rather than requiring exact heading names. The quality rules explicitly allow small scenario notes to combine sections if their information is preserved.

## Structural crosswalk

| Required information | RT-19 transaction | RT-19 multi-file | RT-25 workload fit | RT-32 Lean | RT-13 checked add |
|---|---|---|---|---|---|
| Metadata, research item, status/evidence boundary | Explicit | Explicit | Explicit | Date, areas, baseline, evidence; no status line | Date, areas, baseline, evidence; no status line |
| One answerable question and scope | Explicit question plus API/recovery scope | Explicit question plus publication scope | Explicit question and workload scope | Scope/profile is clear from admitted fragment and body, but no explicit one-line question | Research scope and admitted IR/source model are clear; no question/status heading |
| Prior evidence and sources | Links current prototypes, ADRs, previous boundary report | Links ADR-014 and RT-19 comparison in body | Links RT-01, benchmark, compatibility probe | Links Scenario 96A, SPG reader, generated ledger | Links Scenario 96A, exact IR, solver ledger, replay |
| Alternatives and assumptions/model | Three protocols and state machine | Three publication mechanisms and visibility model | Workload/candidate coverage; assumptions are mostly in scope and limits | Admitted profile and three encodings | Source formula, reader grammar, ABI assumptions |
| Method, tools, commands, configuration | Explicit command pair and CPython version | Method/test result present; the exact command is not present in this pinned main version | Explicit method and statistic-reproduction snippet; benchmark rerun is unavailable | Exact replay command and Lean/Python versions | Exact replay command and compiler/solver versions |
| Results, limits, decision boundary | Separate result, failure table, reproduction, dependencies | Separate candidate analysis, checks, reproduction and dependencies | Findings, coverage table, environment, bounded conclusion | Checked observations, proof limits and trust boundary | SAT/UNSAT/unsupported results, native witnesses and trust boundary |
| Downstream traceability | PLAN item and related RT links | PLAN item and related RT links | RT-01/RT-25 links | RT/PLAN IDs and source artifacts | RT/PLAN IDs and source artifacts |

## Findings

The five reports preserve the core research information, but not through one fixed heading sequence. The first three have an explicit status/question structure; the two formal-verification reports use evidence/date/baseline headers and put the question or status in their subject, scope, and result prose. Each provides a model or workload boundary, results, limitations, and links to the originating research area. The exact depth of reproduction varies with the evidence type and available tools.

The practical gap is metadata and claim-level traceability consistency, rather than absence of every schema section: two reports omit a dedicated question/status field, and none uses a stable per-claim record throughout. In the selected set, the report headings still let a reviewer locate assumptions, alternatives, results, falsifiers or missing correspondence, and decision limits. A mandatory fixed heading template would add little unless it also normalizes those claim fields.

## Stage 0.2 implication

This crosswalk supports a bounded statement that recent implementation-oriented reports contain the minimum information in the proposed schema, sometimes under combined or differently named sections. It does not establish that the entire corpus follows the structure. Keep the full checklist and policy adoption open; apply the report schema prospectively and continue claim-level review where results affect architecture choices.

## Remaining dependencies

- Corpus-wide structural audit, including older scenarios, copied reference snapshots, and prototype reports.
- Stable claim IDs, confidence, falsifier/missing-evidence, and downstream-impact fields for major decision-relevant claims.
- Independent human review and maintainer approval of the proposed Stage 0.2 schema.

**Conclusion:** selected recent studies preserve the important report information without uniform headings. The remaining consistency work is claim-level and corpus-wide; this sample does not close Stage 0.2.
