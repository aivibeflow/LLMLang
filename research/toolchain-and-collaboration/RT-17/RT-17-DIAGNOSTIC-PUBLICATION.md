# RT-17 — Publishing diagnostics from concurrent analyses

**Date** · 2026-11-21

**Baseline** · `1d0a407`

**Status** · Bounded executable experiment for [Plan §7.5](../../../PLAN.md#75-developer-experience-and-adoption) and Scenario 95 cases DIAG-006, DIAG-007 and DIAG-011

## Question and model

When two analyses overlap, under what conditions may a completed result replace the editor's visible diagnostics? [Diagnostic replay](RT-17-DIAGNOSTIC-REPLAY.md) verifies reports against a snapshot. Here an older result may arrive either before or after a replacement request. The fixture uses a source document, an imported type, an optional higher-priority override and configuration. It distinguishes a complete clean result from having no current result.

All three publication candidates require the latest issued request, a complete result, and no prior cancellation of that request. They differ in their change key. The key also controls when a previously visible result becomes stale.

| Key | Applicability |
|---|---|
| Entry document | Cheap and sufficient for the source text in this fixture. Omits dependency state used by semantic diagnostics. |
| Whole workspace | Retains a single broadly conservative validity boundary. A change with no diagnostic impact still discards current evidence. |
| Diagnostic read projection | Includes the entry, provider, configuration and negative lookup for the override. Requires complete read coverage for the published diagnostic family. |

The oracle independently rechecks the current workspace after each edit and delivery. The corpus chooses edits that either change the diagnostic codes or touch an unrelated file. Outcomes compare diagnostic codes, visibility and publication decisions, without assessing diagnostic wording or how an editor renders stale history. [Scenario 95 diagnostic protocol](RESEARCH-SCENARIO-95-EXECUTION-2026-11-20.md#6-discriminating-test-corpus) · [LSP 3.18 push diagnostics](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.18/specification/#textDocument_publishDiagnostics)

## Results

Each policy runs 50 schedules, covering 10 legal orderings and five edits. Both results may arrive despite cancellation. A previously visible complete result can remain visible while a newer analysis is pending, provided its observed inputs still match. An invalidated result is cleared to pending. A complete empty result is the only successful clear-to-clean in this fixture.

| Policy | Unsafe publications | Unnecessary rejections | Visible-state disagreements |
|---|---:|---:|---:|
| Entry document | 6 | 0 | 36 |
| Whole workspace | 0 | 2 | 12 |
| Diagnostic read projection | 0 | 0 | 0 |

Entry-only publication misses changes to an unopened dependency, a formerly absent override and configuration. Whole-workspace publication rejects otherwise usable results after an unrelated note changes. A separate sequence verifies that a partial empty result and a cancelled complete result cannot clear a current error. A fresh complete empty result can clear after the provider is fixed.

The projection is a candidate for a bounded diagnostic family with admitted, complete inputs. Whole-workspace validation is a conservative fallback where dependency coverage is unknown. This fixture assumes a serialized publication step, one editor document and fixed potential resolution reads. Multi-document batches, range remapping, untrusted analysis providers, scheduler and transport integration, and human or agent usability remain open.

## Reproduction

Run from `research/toolchain-and-collaboration/PROTOTYPES/DIAGNOSTIC-REPLAY-01` on CPython 3.12.14. Six tests passed, including the four baseline replay tests. [Publication experiment](../PROTOTYPES/DIAGNOSTIC-REPLAY-01/test_diagnostic_publication.py)

```sh
python -B -m unittest -v
```
