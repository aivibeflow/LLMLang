# RT-00 — Root research document structural census and reproducible review queue

**Issue:** [#285](https://github.com/aivibeflow/LLMLang/issues/285), PLAN §0.2  
**Date:** 2026-11-23  
**Status:** Source-pinned root-document structural census executed successfully; complete report artifact, permanent summary and unreviewed queue recorded  
**Baseline:** `627c70878863b519a358815f8a96ddbae1303136` (post-orthogonal source-oracle PR #384)  
**Evidence class:** Repository/Git object inventory and warning-only heading/metadata heuristic, **not a technical result or corpus-wide claim validation**  
**Relevant earlier work:** [Ten-document warning pilot](RT-00-QUALITY-RULES-REAL-REPORT-PILOT-2026-11-23.md), [12-report/24-claim second-cohort study](RT-00-QUALITY-RULES-CLAIM-COHORT2-2026-11-23.md), [orthogonal oracle observations](quality-audit/2026-11-23-orthogonal-oracle-results.json)  
**Draft impact:** None; no new accepted rule, implementation or model is implied.

## Question, assumptions and alternatives

Until now the Stage 0.2 quality pilot closely examined two purposive cohorts (10 + 12 reports), which does **not** describe the distribution of superficial missing fields in the wider research document tree. Can the same explicitly non-normative checker be applied to *every root research Markdown document* at one immutable commit, and can a follow-on human-review queue be chosen without selecting only files that emitted warnings?

- **H1, testable as Git/census bookkeeping:** enumerate the baseline's root-level `research/*.md` and `research/*.mdx` document blobs, classify into three filename strata, run exactly the existing `inspect()` checker, and preserve every warning string and individual Git blob identity.
- **H2, testable as sampler reproducibility:** choose eight review candidates per stratum by a SHA-256 rank seeded with the full Git commit, without examining the warning counts during selection.
- **H3, not tested by software:** every finding is a genuine evidence-quality defect and the sample reliably estimates claim validity across the research corpus. **Not asserted.** The earlier 65-warning pilot established substantial legacy-header false alarms; a zero-warning file can still contain incorrect science.

**Alternatives rejected:** (a) promote heading warnings to blocking CI or scientific quality scores; (b) sample only warning-rich files (selection bias, misses false negatives); (c) assess the moving main tree and attribute totals to an older baseline. The chosen approach freezes Git objects and reports *warning frequency only*.

## Enumerated scope and method

An independent read of the pinned Git tree before this PR showed **309** root `research/` Markdown/MDX documents: **136** named `RESEARCH-SCENARIO-...`, **127** named `RT-...`, and **46** other root research documents. A further **42** nested Markdown/MDX files are **out of this deliberately bounded scope**. The census workflow will verify those totals from exact source objects before this report calls them an independently reproduced output. No inference is made about prototype source files, external URLs, or the correctness of the report contents.

The [census script](../.github/scripts/research_quality_corpus_census.py) reads each selected `commit:path` through Git (rather than trusting a possibly modified working tree), computes a Git blob hash, calls the existing `inspect()` scanner, and records warning strings and two clearly named *textual indicators*: an explicit `Evidence type` field and a status-line executable hint. Neither indicator checks the executed experiment or its tool versions.

The reproducible review queue selects **8 Scenario + 8 RT + 8 other root documents** using SHA-256 of `stage-0.2-reviewed-after:<baseline>:<path>`, ascending within each filename stratum. This is *warning-independent within the three strata* but **not an unbiased, statistically representative sample of the entire corpus**: the strata are filename categories, the counts are equal despite different populations, and non-root evidence remains excluded. All 24 human-review statuses start as `NOT REVIEWED`. No individual is credited with reviewing them.

## Reproduction, fixtures and expected output

From a full checkout containing the pinned baseline and the new census scripts:

```sh
python3 -B -m unittest discover \
  -s .github/scripts -p 'test_research_quality_corpus_census.py' -v

python3 -B .github/scripts/research_quality_corpus_census.py \
  --repo ./archival \
  --baseline 627c70878863b519a358815f8a96ddbae1303136 \
  --json-out /tmp/llmlang-root-research-census.json
```

The example assumes `./archival` is a clean checkout of the specified baseline (the [dedicated workflow](../.github/workflows/research-quality-root-census.yml) prepares it automatically). The census returns `CORPUS_CENSUS_SUMMARY` and `CORPUS_CENSUS_SAMPLE` log lines and a full machine-readable `reports` array with 309 exact source blobs and their heuristic warnings.

**Observed fixed-baseline results:** [GitHub Actions run #45263179285](https://github.com/aivibeflow/LLMLang/actions/runs/45263179285) completed successfully: **five** census/sampling unit tests passed, all **309** exact root report blobs were inspected, and **24** queue items retained the `NOT REVIEWED` status. Environment was CPython **3.12.14**, Git **2.56.1**, Linux `7.0.0-1017-azure x86_64` (Ubuntu 24.04). The full per-file [warning corpus artifact](https://github.com/aivibeflow/LLMLang/actions/runs/45263179285/artifacts/14862435235) is retained by GitHub Actions; the [permanent machine-readable summary and 24 source-pinned reviewer candidates](quality-audit/2026-11-23-root-census-observations.json) are tracked in this repository.

| Observed baseline metric | Count | Meaning |
| --- | ---: | --- |
| Root research Markdown/MDX docs at fixed Git commit | **309** | 136 Scenario, 127 RT, 46 heterogeneous other root documents |
| Documents with at least one surface warning | **308** | No scientific correctness or error verdict follows |
| Documents with no surface warnings | **1** | **Not** a certificate of adequate scientific evidence |
| Total warning instances across 309 files | **2,035** | Keyword/heading heuristic findings, **not** 2,035 technical defects |
| Missing exact `Baseline` metadata | **238** | Literal formatting check, not proof that no revision provenance exists elsewhere |
| Missing literal `draft impact`/traceability heading | **285** | May be covered under other headings or explicitly in prose |
| Missing literal alternatives/hypotheses heading | **259** | May be a short experiment or source-only comparison |
| Exact `Evidence type` metadata found | **7** | Explicit field presence only, no evidence validity |
| Status-line heuristic suggests an executable/probe | **67** | Non-authoritative hint; cannot be equated with an authenticated executable evidence class |
| SHA-256 sampled human review queue | **24** | 8 per stratum, **0 reviewed by a second human** |

**Critical interpretation:** **308/309** files produced warnings, so this scanner currently has almost no power to separate legacy documentation from genuinely defective science without a reviewer. This does *not* measure its precision, sensitivity or error rate; neither warned nor unwarned reports were independently labeled across this whole corpus. In particular, **7 exact evidence-type fields vs 67 executable status hints** is a coverage signal for metadata migration, not proof that exactly 60 experiments are missing evidence.

**Reproduction notes:** all warning totals belong to the immutable `627c70878863b519a358815f8a96ddbae1303136` source state, not to moving `main`. The full JSON artifact includes every selected root path, Git blob hash, warning list and the 24 preselected reviewer source identities.

## Negative results and decision boundaries

- The earlier ten-report sample found 45 layout-only warning instances and three corrected metadata punctuation variants; those findings already invalidate treating an unreviewed warning as a research defect.
- The checker identifies an `Evidence type` keyword only when literally formatted as expected; the historical eight baseline gaps showed why lack of that marker can bypass executable-specific subchecks. A successful census is **not** evidence that 309 reports meet the Q1–Q5 gates.
- The stratified sample is a **review queue, not completed independent human review**. To classify genuine defects or false negatives, a second human must inspect warned and unwarned claims, negative evidence and corresponding executable code.
- The eight original-execution source/host attestations remain unverified; a new Git run at a published tree cannot reconstruct original uncommitted input.
- A proposed candidate spec change needs its own research-to-`draft/` map and explicit maintainer/ADR approval; the corpus structure cannot authorize one.

**Proposed action:** preserve warning-first reporting, recruit an independent reviewer for the 24 selected documents and record source-bound claim results. Continue #285 for broader scientific validity, full original-run provenance and formal adoption. None of the global exit criteria are closed by this census.
