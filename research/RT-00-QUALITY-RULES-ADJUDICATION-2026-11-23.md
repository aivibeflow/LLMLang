# RT-00 — Adjudicating the 33 outstanding Stage 0.2 pilot warnings

**Research item:** [PLAN §0.2](../PLAN.md#02-establish-research-quality-and-decision-rules); [issue #285](https://github.com/aivibeflow/LLMLang/issues/285)  
**Status:** Scoped documentation-gap triage and three claim-provenance spot checks; *not* a reproduced science audit or accepted research policy  
**Baseline:** `main` at `12c4f5cb36e3c0733fc5842894fea28fdd9e0f99`, after [PR #374](https://github.com/aivibeflow/LLMLang/pull/374)  
**Date:** 2026-11-23  
**Evidence type:** Human review of immutable repository text and recorded prior CI, plus machine-checkable adjudication accounting  
**Reproduction inputs:** [Original ten-report manifest](quality-audit/2026-11-23-sample.json), [33-row adjudication register](quality-audit/2026-11-23-adjudication.json), and [validator](../.github/scripts/validate_research_quality_adjudication.py)  
**Normative boundary:** Does not establish completeness of any LLMLang experiment, adopt mandatory quality rules, or alter `draft/`.

## 1. Problem, competing interpretations, and method

The [ten-document pilot](RT-00-QUALITY-RULES-REAL-REPORT-PILOT-2026-11-23.md) recorded 65 initial structural warnings. Three were removed by supporting alternative existing metadata delimiters. Of the remaining 62, the first pilot supplied source-line citations confirming 29 warnings as header/layout mismatches, leaving 33 unadjudicated. Are those 33 absent *scientific evidence*, or merely missing *metadata/navigation*?

Three alternative interpretations were tested against the exact document text:

1. **Missing research result:** a claimed experiment/proof lacks required inputs, outputs, independent checks or defined scope. This cannot be inferred from a heading warning and needs a claim-level examination.
2. **Documentation gap:** a desired evidence-navigation field, provenance pin or explicit N/A is absent or incomplete. This is not proof that the underlying experiment is incorrect.
3. **Layout-only warning:** the substantive information is present under another heading, in metadata or in a linked section; the heuristic misclassifies its location.

The review used the original ten Git blob SHAs and 33 previously unclassified strings exactly. Each warning receives one of `layout-only` or `documentation-gap`, a source-line range, reason and proposed follow-up. `Documentation-gap` here is a **process finding**, not the conclusion that a scientific claim is false. A machine validator checks unique, complete warning-set accounting and whether cited line numbers exist; it **cannot** validate the correctness of those human judgments. Full adjudications, including negative outcomes and follow-up actions, are in [the JSON register](quality-audit/2026-11-23-adjudication.json).

## 2. Results, exact scope

| Category | Count | What it establishes |
| --- | ---: | --- |
| Initial warnings from ten reports | 65 | Textual checker output before punctuation fix |
| Corrected historical metadata false alarms | 3 | Delimiter variants were already meaningful |
| First pilot's confirmed layout-only cases | 29 | Existing content under alternate sections, manually line-grounded |
| This follow-up's **additional** layout-only cases | 16 | Existing content also located for these warnings |
| This follow-up's **documentation gaps** | 17 | Missing/incomplete *recorded metadata, alternative/N/A or traceability*, not invalid technical results |
| Remaining warnings without a triage disposition | **0** | Every original warning now has a recorded *process* classification; no claim-validation guarantee |

The 17 recorded documentation gaps include **eight missing complete baseline/revision attestations** (Scenarios 98, 103, 118, 133, 29, 134; RT-04 and RT-11). Historical short bases, review dates, named libraries, or `base + working tree` descriptions may aid recovery but do not identify an immutable complete execution tree. **Do not fabricate** commits or tool versions while addressing them.

The other nine documentation gaps concern missing explicit hypothesis/alternative-or-N/A framing, precise prior-research navigation, draft/LL-question mapping, one proposal's bounded fake-runner reproduction route, and an explicit answerable question for the DEP-007 recheck. The presence of an open crosswalk request does not mean `draft/` should change or that any rule was accepted.

### File-by-file triage overview

| Report | Additional layout-only | Documentation gaps | Principal follow-up |
| --- | ---: | ---: | --- |
| [Scenario 98](RESEARCH-SCENARIO-98-FINITE-AST-PATH-COVERAGE.md) | 0 | 4 | Pin source revision; note alternatives/N/A, COR-06 source and no draft decision |
| [Scenario 103](RESEARCH-SCENARIO-103-REAL-SOLVER-TIMEOUT-ISOLATION.md) | 0 | 3 | Exact run revision, comparison scope and draft/open-question links |
| [Scenario 118](RESEARCH-SCENARIO-118-ATOMIC-EXECUTION-RELATIONS.md) | 1 | 2 | Preserve memory-model alternatives; pin full execution revision |
| [Scenario 133](RESEARCH-SCENARIO-133-GENERATED-RUST-OWNED-RESULTS.md) | 2 | 1 | Pin complete source/fixture state; do not generalize source-to-target result |
| [RT-05](RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md) | 0 | 0 | Prior review found its lone remaining warning layout-only |
| [RT-04](RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md) | 2 | 1 | Trace exact reviewed source and prototype revisions |
| [RT-11](RT-11-BINDING-INVALIDATION-BENCHMARK.md) | 4 | 1 | Reconstruct noncommitted working-tree experiment for clean reproduction |
| [Scenario 29](RESEARCH-SCENARIO-29-VERIFIED-PROOF-CHECKER-AND-ENCODER-VALIDATION.md) | 2 | 2 | Pin *fake-runner* tests and complete evidence; no Logos proof claimed |
| [Scenario 134](RESEARCH-SCENARIO-134-WIRE-SCHEMA-EVOLUTION-INTEROPERABILITY.md) | 1 | 1 | Pin repository baseline, keep source-only format analysis |
| [DEP-007 recheck](RT-00-DEP-007-OBSERVATION-MODEL-RECHECK-2026-11-23.md) | 4 | 2 | State exact question and non-normative draft impact |

**Classification limits:** This is an exhaustive classification of the **33 named warnings**, *not* an exhaustive test of the ten studies. The other 45 layout/metadata findings still refer to report structure, and the checker can miss absent scientific evidence. Findings were adjudicated in a single review, not independently double-reviewed; inter-rater reliability, precision, recall and full-corpus prevalence remain unknown.

## 3. Claim/evidence/proof spot checks (three contrasting cases)

| Claim, primary evidence class | Exact source and recorded route | Scope, negative result and missing bridge | Decision and draft impact |
| --- | --- | --- | --- |
| **A: RT-11 distinct compilation/verification invalidations — Experimental result** | [RT-11 §2–5](RT-11-BINDING-INVALIDATION-BENCHMARK.md) ([pinned historical blob in manifest](quality-audit/2026-11-23-sample.json)); generated C source and `src.binding_build_benchmark`; source run reports Apple Clang 21.0, Python 3.12.14, 12 exact/separate change phases and a stale verification-key witness. The separate [quality evidence-shape recheck](RT-00-QUALITY-RULES-EVIDENCE-SHAPE-RECHECK-2026-11-23.md) records a Linux/GCC-host rerun of the 12 cases. | Synthetic graph of two providers and 16 callers with a fixed toolchain. The observed caller action counts and changed outputs falsify a *fixture-local* compile-input-only verification key. The primary report's `base 7282297… + working tree` is not a complete immutable source revision; backend/compiler behavior and general dependency completeness are not established. This follow-up did not rerun it. | Recommends evaluation of stable ABI separation; **no LLMLang ABI or cache rule accepted**. If it informs `draft/`, provide full commit/fixture, claim ID and approved decision link first. |
| **B: Scenario 118 atomic relations — Model result with independent oracle on the global-order side** | [Scenario 118 model/results](RESEARCH-SCENARIO-118-ATOMIC-EXECUTION-RELATIONS.md), 4,096 bounded layouts, C++20/Go primary source links, Python 3.12.14 historical run and 7 reported tests; script `rt04_atomic_execution.py` plus `test_rt04_atomic_execution.py` linked. | The independent interleaving oracle corroborates the **global** order projection; the weak direct-release/acquire side **still lacks independent full-memory-model comparison**. RMW, fences, non-atomics and source/backend preservation are excluded. The report identifies a historical base plus scenario files, not an exact full tree. No new tests executed here. | Discriminates two model candidates only. **No memory model selected**, no direct draft change authorized. |
| **C: DEP-007 observation-model rewrite preservation — Lean proof as reported by pinned CI, not local reproduction** | [DEP-007 recheck](RT-00-DEP-007-OBSERVATION-MODEL-RECHECK-2026-11-23.md) identifies proof source Git blob `98bd38f297e91840c56664ef00fbd5f28c3a81b8`, SHA-256 `039808b6adf5d5baa97f6498a15fd04843a4f4c6b1147c9dade68f4440252765`, theorem `rewrite_preserves` and [Required CI run #45151548187](https://github.com/aivibeflow/LLMLang/actions/runs/45151548187), using pinned Lean 4.36.0. | The checked theorem applies to a fixed expression grammar and ordered traces; counterexamples distinguish value-only observational equivalence. **Lean was not rerun locally in that recheck or this audit**. Parser, SPG lowering, backend, resource/cleanup and concurrency correspondence are unproved. | The edge remains a strong hypothesis with bounded witnesses; not an accepted full-language optimization guarantee. No new `draft/` rule. |

**Negative evidence retained:** Scenario 29's current adapter reports `CHECKER_REPORTED_CORRECT_UNBOUND` and uses 15 fake-executable tests, not a checked cvc5/Logos integration. This must never be counted as a completed machine-checked proof. Scenario 134 is an official-source comparison (not real serializer conformance) and has an existing *separate* accepted architecture decision referenced in `draft/`; the comparison itself does not create another.

## 4. Reproduction, tool versions and failure cases

**Review environment:** GitHub file contents at pinned commit `12c4f5c`; the validator uses Python 3.10+ standard library and GitHub-supplied file snapshots, not solver/Lean/real compilers. Commands from the repository root:

```sh
python3 -B -m unittest discover -s .github/scripts -p 'test_validate_research_quality_adjudication.py' -v
python3 -B .github/scripts/validate_research_quality_adjudication.py --root .
```

**Expected:** 5 tests; `OK`; `source_reports: 10`, `adjudicated: 33`, `layout_only: 16`, `documentation_gaps: 17`, `errors: []` and exit code 0. Tests intentionally reject missing/duplicate adjudications, invalid line references and unsupported verdicts. The validator does not prove that a cited line substantiates a verdict.

- **Not executable here:** no complete clean reproduction of the three underlying technical studies; no local Lean installation or actual solver/serialization run is claimed.
- **UNKNOWN:** the exact historical working-tree snapshots for some reports remain unidentified; rerunning current main would be a *new* result, not proof of the original run.
- **Rejected approach:** silently rewriting historical reports to add plausible versions, retroactively declaring missing fields a scientific failure, or treating zero outstanding *format* triage rows as closure of §0.2.

## 5. Recommendation, dependencies and draft impact

**Recommendation only:** review and merge the adjudication evidence as an *audit record*. Prioritize the eight provenance/revision gaps before any foundational reproduction claim; then repair the nine remaining crosswalk/method/question records with author review. Evaluate header aliases and executable-type detection on a stratified, independently reviewed set before making CI blocking. Track reviewer effort and false-negative rate; this one-person purposive review cannot estimate either.

**Open dependencies:** research-quality process adoption by maintainers; a true claim-level audit of all material reports, source/environment fidelity of selected foundational reruns, independent review of these manual classifications, and explicit research-to-`TODO.md`/candidate-`draft/` decision records where actual specification changes are proposed. `PLAN.md` §0.2 and issue #285 stay open.

**Draft impact: none.** This report changes no LLMLang syntax, semantics, ABI, model, runtime or accepted decision. `research/` is exploratory; `draft/` remains the candidate specification.
