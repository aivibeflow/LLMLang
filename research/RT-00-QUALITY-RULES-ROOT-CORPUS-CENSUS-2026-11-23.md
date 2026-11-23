# RT-00 — Root research document structural census and reproducible review queue

**Issue:** [#285](https://github.com/aivibeflow/LLMLang/issues/285), PLAN §0.2  
**Date:** 2026-11-23  
**Status:** Full root-document structural census at a fixed Git commit proposed; CI output must be inspected before treating totals as verified  
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

**Expected structural checks:** five new unit tests; root corpus 309, strata 136 / 127 / 46, reviewer queue 24 unreviewed records. The warning counts and evidence-field coverage will be reported **only after actual CI execution**, without interpreting a warning as falsity or promoting source metadata to peer review. The CI artifact retains the full warning register even if future Git edits change the corpus.

## Negative results and decision boundaries

- The earlier ten-report sample found 45 layout-only warning instances and three corrected metadata punctuation variants; those findings already invalidate treating an unreviewed warning as a research defect.
- The checker identifies an `Evidence type` keyword only when literally formatted as expected; the historical eight baseline gaps showed why lack of that marker can bypass executable-specific subchecks. A successful census is **not** evidence that 309 reports meet the Q1–Q5 gates.
- The stratified sample is a **review queue, not completed independent human review**. To classify genuine defects or false negatives, a second human must inspect warned and unwarned claims, negative evidence and corresponding executable code.
- The eight original-execution source/host attestations remain unverified; a new Git run at a published tree cannot reconstruct original uncommitted input.
- A proposed candidate spec change needs its own research-to-`draft/` map and explicit maintainer/ADR approval; the corpus structure cannot authorize one.

**Proposed action:** preserve warning-first reporting, recruit an independent reviewer for the 24 selected documents and record source-bound claim results. Continue #285 for broader scientific validity, full original-run provenance and formal adoption. None of the global exit criteria are closed by this census.
