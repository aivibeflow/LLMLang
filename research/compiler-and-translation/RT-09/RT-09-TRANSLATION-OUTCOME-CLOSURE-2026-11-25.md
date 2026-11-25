# RT-09 — Compose translation outcomes over required regions

When can a translation result cover a requested entry point if its implementation calls other regions? This fixture applies the [RT-30 candidate outcomes](../RT-30/RT-30-WRAPPING-TRANSLATION-MATRIX-2026-11-25.md#candidate-outcome-contract) to a declared dependency graph with one dependent entry and one independent preview. The branch baseline is `138f84e6833e59ae1df86cfdfcb85ee3971c7dc3`. [Translation architecture issue](https://github.com/aivibeflow/LLMLang/issues/327)

The model records local status and evidence for the exact source region, selected artifact, target profile and observation model. A checked edge binds both endpoints with those scopes. A runtime-supported region requires its selected runtime identity. A restricted region requires approval for its exact revision, artifact, scope and restriction. Unsupported and unverified reasons remain visible. The evaluator traverses the declared required closure of each requested root.

A root is exact when every required region is exact and every edge is checked. A root is conditional when its closure also depends on a resolved runtime or approved restriction. The result retains both obligations if they apply together. Unresolved or stale evidence withholds that root. Known unsupported dependencies remain explicit. Complete coverage means every requested root is admitted under its recorded conditions. Partial coverage lists the exact admitted roots and the reasons for each omitted root. [Model and controls](TRANSLATION-OUTCOME-CLOSURE-01/run.py)

| Test family | Outcome |
|---|---|
| All exact, runtime required and present, approved restriction, or both satisfied | Four complete results with exact or conditional entries |
| Missing runtime, stale scope, unapproved restriction, missing edge, unsupported or unverified dependency | Thirteen partial results retain the independent preview only |
| Unverified dependent entry and unsupported preview | Zero admitted roots, with both dispositions preserved |

All 18 controls match the declared expectations. A gate that checks only whether each region has an emitted artifact would falsely report complete coverage in ten cases. One such case has locally exact receipts everywhere but no evidence for the edge carrying the dependent call. Another has a stale selected artifact revision for the codec while still reporting successful emission. [Exact dispositions and blockers](TRANSLATION-OUTCOME-CLOSURE-01/evidence.json)

The model takes the dependency inventory, local semantic evidence, runtime identity and approval as inputs. It verifies exact composition within a three-region fixture. Source-derived edge completeness, independently checked correspondence, authenticated receipts, recursive contracts and implementation integration remain open. [Translation and target backends](../RT-13/TRANSLATION-AND-TARGET-BACKENDS.md)

## Reproduction

Run with CPython 3.12.14. Hash seeds 1 and 2 produced identical outcomes and blocker ordering.

```bash
fixture=research/compiler-and-translation/RT-09/TRANSLATION-OUTCOME-CLOSURE-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > /tmp/llmlang-rt09-translation-closure.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt09-translation-closure.json
```
