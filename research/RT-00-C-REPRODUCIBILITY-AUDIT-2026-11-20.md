# RT-00 C — Reproducibility audit: RT-16, CLI, LLVM, SQLite, Rust, benchmarks, and fuel

**Audit snapshot:** `dcbb3085bfc6fb45eaaf520ca27aef4e93a628ae`  
**Date:** 2026-11-20  
**Scope:** RT-16 authorization model, CLI reference workloads, RT-04 Python/native probes, LLVM preservation, SQLite source/runtime identity, generated Rust owned-results probe, binding/Package Provider/solver-path benchmarks, and Scenario 36 fuel models.  
**Method:** current Git tree and source-blob comparison, workflow inspection, current Required CI logs, historical Actions run/job logs, and result-document reconciliation. No new benchmark or native workflow was dispatched and no source files were changed during this audit.

## 1. Executive result

The evidence is mixed but now substantially better delimited:

- RT-04's Python regression suite is a Required CI gate: 45 test modules, 364 tests, all passing in run #44801357527. The 106-file RT-04 tree at that run is byte-for-byte identical by Git blob to the current main RT-04 tree.
- The optional native/LLVM reproduction run #44774296240 passed both jobs: 10/10 native commands and 2/2 LLVM preservation probes. All 114 relevant RT-04/LLVM source, workflow, and harness files compared against current main are identical except documentation-only README/protocol files.
- The Package Provider manual benchmark run #44799755164 passed 81 tests and 8 benchmark cases, all with `verified: true`. The benchmark scripts used in that run match current main, but the run predates the current profiling helper.
- CLI reference workloads have historical 34/34 Python and C reference results, but no Required CI invocation and no pinned runner revision for the historical run. The separate three-executable pilot had two known negative-division mismatches and is not a successful LLMLang compiler result.
- RT-16 authorization has 24 focused test methods but no recorded execution and no CI invocation.
- Scenario 36 fuel models remain exploratory standalone models: no dedicated fuel test modules, no Required CI execution, and no selected language policy.
- SQLite/Python/Rust/LLVM toolchain evidence is now recorded in Actions logs, but some archive and package identities are still not verified at the point of download.

No language-semantics or implementation decision follows from this audit.

## 2. RT-04 Required CI baseline

Required CI run [#44801357527](https://github.com/aivibeflow/LLMLang/actions/runs/44801357527) completed successfully. Its repository-structure job ran:

`python -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_*.py' -v`

The log reports **364 tests**, all passing, in 8.962 seconds. The environment recorded by the job includes Python 3.12.16, SymPy 1.14.0, and mpmath 1.3.0. The current RT-04 directory has 106 tracked files and 45 `test_*.py` modules.

The exact path/blob comparison between the run's head tree (the CI run used main SHA `c35ba93c031684100dcdbc06a34b0e14696c37ab`) and the current main snapshot found 106/106 RT-04 files identical, with no missing or changed blobs. The subsequent main change was documentation-only.

Important boundary: this is the Python model/test suite. It does not execute the native SQLite/Rust probes, LLVM toolchain probes, CLI reference harness, RT-16 authorization tests, or standalone fuel scripts.

## 3. RT-16 authorization

Relevant artifacts:
- `research/RT-16-THREAT-MODEL-01.md`;
- `research/PROTOTYPES/RT-16-AUTHORIZATION-01/policy.py`;
- `research/PROTOTYPES/RT-16-AUTHORIZATION-01/test_policy.py`;
- the captured MCP authorization reference snapshot.

Findings:
- The test module contains 24 `test_*` methods.
- The implementation and test blobs are unchanged from commit `b0638a1b69a3f7d233194097032cde9209b672db`.
- The threat-model document provides a direct `python -m unittest` command and states that the model is standard-library-only.
- No workflow under `.github/workflows/` invokes this test module, and no recorded Actions or local test run is attached to the result.
- The historical record does not pin a Python patch version, OS image, or exact test-run commit/environment.

The policy model is a finite authorization decision model, not a production authentication/authorization service. A 24-method test file with no recorded run must not be reported as 24 passing tests.

**Disposition:** source/test identity is stable; execution evidence is absent. Add an explicit test run and environment record or a separately scoped CI job before treating this prototype as reproduced.

## 4. CLI reference workloads

Relevant artifacts:
- `research/RT-01-REFERENCE-WORKLOADS.md`;
- `research/PROTOTYPES/CLI-WORKLOADS-01/run.py`;
- `reference.py`;
- `reference.c`.

Findings:
- The runner defines 34 reference workload cases.
- The historical record reports 34/34 passing against the Python reference and 34/34 against the C reference.
- The historical environment is Python 3.9.6 and Apple Clang 21.0.0 on Darwin arm64.
- The separate three-executable pilot reports 32/34; the two mismatches concern negative integer division/rounding. This is a known pilot failure, not a passing LLMLang compiler implementation.
- The current runner and both reference files have exactly the same Git blob SHAs as commit `b0638a1b69a3f7d233194097032cde9209b672db`.
- The historical result does not pin the exact runner commit used at execution; it pins the workload baseline and records tool versions.
- No current Required CI workflow invokes `CLI-WORKLOADS-01/run.py`.

The 34/34 results validate the host reference pair for those cases. They do not demonstrate a compiled LLMLang executable, target ABI compatibility, or end-to-end language conformance.

**Disposition:** historical reference evidence exists and current source is unchanged from its introduction commit; repeatable CI evidence and exact historical runner provenance remain open.

## 5. Native SQLite and Rust reproduction

### 5.1 Run identity and source-tree applicability

Native reproduction run [#44774296240](https://github.com/aivibeflow/LLMLang/actions/runs/44774296240) was triggered by a pull request on head SHA `0496ad43783bc86105dd617fdc4d679cdf4637b8`, not by the current main commit.

A current-main comparison of the RT-04/LLVM reproduction scope found 114 relevant files. No implementation or workflow file changed; the differences are documentation-only README/protocol files. The run therefore exercises the same current probe code, while its commit identity must still be reported as the PR head rather than current main.

The workflow is optional: it has pull-request path filters and `workflow_dispatch`; it is not a Required CI gate.

### 5.2 Native job results

The `native-reproduction` job passed 10/10 commands:
- eight C SQLite probes;
- one durable Python SQLite receipt probe;
- one generated Rust owned-results probe.

Recorded environment:
- Python 3.12.14, built from source;
- C SQLite 3.46.1, package version `3.46.1-9ubuntu0.3`;
- C SQLite source ID `2024-08-13 09:16:08 c9c2ab54ba1f5f46360f1b4f35d849cd3f080e6fc2b6c60e91b16c63f69aalt1`;
- Python SQLite 3.53.1, source ID `2026-05-05 10:34:17 c88b22011a54b4f6fbd149e9f8e4de77658ce58143a1af0e3785e4e6475127e9`;
- Rust `1.85.1 (4eb161250 2025-03-15)`, commit hash `4eb161250e340c8f48f66e2b929ef4a5bed7c181`, host `x86_64-unknown-linux-gnu`, LLVM 19.1.7.

Native results include:
- SQLite recovery matrix: 356 admitted traces compared and 154 rejected plans skipped;
- SQLite close-call boundary: 114 call boundaries compared, with 30 plans rejected before execution;
- generated Rust owned results: 125,952 native observations match the reference.

The native artifact is 6,975 bytes, SHA-256 `c6c042c2458b0b98fa0d1ed07eb476d75fa59d6192997215080941237a8f4d8b`, artifact ID 14650095720.

### 5.3 SQLite reproducibility gaps

The C SQLite preflight checks both version and exact `sqlite3_sourceid()`. However:
- `apt-get install libsqlite3-0` does not pin the Debian/Ubuntu package version or package archive hash;
- the run log records the actual package version `3.46.1-9ubuntu0.3`, but the workflow does not require that package version;
- the source ID ends in `alt1`, which is not the stock upstream release-log source ID. This is a distribution build identity and should not be described as a pristine upstream SQLite build.

For Python SQLite:
- the runner checks version 3.53.1 and records the source ID, but it does not compare the source ID with an expected value;
- the summary field `durable_python_sqlite_matches_historical_baseline` therefore means version match, not exact source identity match;
- the Python 3.12.14 and SQLite 3.53.1 source archives are downloaded over HTTPS but no SHA-256 verification is performed in the workflow.

The historical Scenario 130 report did not preserve its source ID. The current run now records one, but does not yet make it an enforced expected identity.

### 5.4 Rust reproducibility

Rust 1.85.1 is pinned as a toolchain version and the run records the full `rustc -vV` output, including commit hash. The native runner checks the version string and preserves verbose metadata. The Rust experiment is a generated probe with no third-party crate dependency, not a complete LLMLang Rust backend or production build.

The rustup installer itself is fetched from `sh.rustup.rs` at run time; the toolchain version is fixed, but the bootstrap installer is not pinned by digest.

## 6. LLVM preservation

The `llvm-preservation` job in run #44774296240 passed both probes:
- integer preservation;
- byte-view preservation.

Recorded toolchain:
- Debian LLVM 19.1.7;
- package `llvm-19=1:19.1.7-3+b1`;
- package archive SHA-256 `0b1b7263f4f45e261099240fdbf00fc14b42b88410fd829e041bf83ea45866cb`;
- GCC 14.2.0;
- GNU ld 2.44;
- Python 3.12.14;
- target `x86_64-pc-linux-gnu`.

The probe runner checks the exact LLVM package archive SHA and checks executable versions. Input IR hashes are recorded:
- integer: `c46111f6b77eb621a5c154b17645044e1d76c7cb2808fe80189a63f447dc173d`;
- byte-view: `ddb41ceb866c77e957df865cd2102f7a02d3a468150fc82f79c7a7fb2bf782d0`.

The result report records 20,978 integer comparisons at each optimization level (O0/O3) and 9,800 byte-view comparisons at each optimization level, with zero mismatches.

The LLVM artifact is 3,245 bytes, SHA-256 `e36739481ea3b57ec7e58265f1e4b378ac4248a9b74d03e4711900a9d775eced`, artifact ID 14650040345.

The LLVM job uses a floating `debian:trixie` container image, but it verifies the exact LLVM package archive SHA and the observed GCC/ld versions. The probe establishes preservation for the supplied LLVM IR fixtures; it is not evidence of LLMLang-to-LLVM lowering correctness.

Both native and LLVM artifacts have 30-day retention. Their archive hashes are documented, but the uploaded artifacts are not permanent repository snapshots.

## 7. Benchmarks

### 7.1 Package Provider benchmark

Manual workflow run [#44799755164](https://github.com/aivibeflow/LLMLang/actions/runs/44799755164) ran on branch `diagnostics/package-index-performance`, head SHA `8f340cf26da02f7b436ffed7c504d02d3eaa15a3`.

Results:
- 81 Package Index tests passed;
- 8 benchmark cases ran: chain, diamond, fanout, and many-dependencies shapes at 1,000 and 5,000 objects;
- all eight emitted `verified: true`.

Selected 5,000-object results:

| Shape | Dependency edges | Provider build time | Objects/second | Archive bytes |
|---|---:|---:|---:|---:|
| Chain | 4,999 | 4.110 s | 1,216.65 | 3,018,670 |
| Diamond | 6,249 | 4.204 s | 1,189.39 | 3,310,893 |
| Fanout | 4,999 | 3.782 s | 1,321.93 | 3,018,670 |
| Many dependencies | 79,864 | 38.126 s | 131.14 | 20,520,814 |

The current main `benchmark_package_provider.py` and `run_tests_with_timings.py` blobs match the files used in that run. The workflow file changed afterward, and the current `profile_package_provider.py` was not present in the run's source tree. The current workflow syntax-compiles that profiler but does not execute it.

The run did not upload a benchmark artifact; results are present in the Actions log. The benchmark workflow is separate from Required CI, with `run_benchmark` defaulting to false and enabled only for a manual run or explicit workflow input. No performance threshold is imposed by Required CI.

### 7.2 RT-11 binding invalidation benchmark

`binding_build_benchmark.py` is a synthetic C call-site workload, not an LLMLang compiler benchmark. Its result document records Python 3.12.14 and Apple Clang 21.0.0 on Darwin arm64. It compares compile-action counts under interface versus implementation changes; it explicitly does not estimate wall-clock LLMLang build or verification time.

The report uses a base revision plus a working-tree experiment and does not identify an exact source commit/blob set for the measured run. There is no CI invocation or archived raw result artifact.

### 7.3 Scenario 101 predicate-path benchmark

`benchmark_rt03_predicate_paths.py` is an exploratory synthetic comparison between a truth-table path and a DPLL2 path. It uses pinned SymPy 1.14.0 and mpmath 1.3.0, with repeated measurements/median reporting. The current Required CI installs the solver requirements and runs the RT-04 unit suite, but it does not run the benchmark script as a performance gate. The result is not an end-to-end LLMLang compiler benchmark and has no regression threshold.

## 8. Fuel models and Scenario 36

Scenario 36 and the related RT-04 files contain standalone exploratory models:
- `rt03_recursion_fuel.py`;
- `rt03_fuel_cleanup.py`;
- `rt03_fuel_owned_return.py`;
- `rt03_fuel_owned_return_audit.py`;
- `rt03_cleanup_fuel_stack.py`.

No `test_*fuel*.py` module exists in the RT-04 family, and the Required CI suite has no dedicated fuel-model test module. The current 45-module suite does test resource cleanup and related protocol models, but that is not execution coverage for these fuel scripts.

Scenario 36 leaves the policy comparison open and selects no normative fuel vector. The scripts are finite design models; they do not execute compiled LLMLang code, establish resource cleanup behavior of a production runtime, or prove a fuel/termination theorem.

**Disposition:** fuel remains research-only and unreproduced by a dedicated test suite.

## 9. Documentation freshness

- `RT-04-NATIVE-REPRODUCTION.md` has an early status line saying workflow execution is still required, although later sections record successful run #44774296240. The status header should be updated or explicitly marked historical.
- The previous corpus audit records 44 test modules/360 tests at an earlier snapshot. Current Required CI records 45 modules/364 tests.
- Scenario 130 should be updated with the current Python SQLite source ID and the qualification that it was recorded but not enforced.
- The CLI result should retain the negative-division pilot failures and the missing runner-commit provenance.
- RT-16 should not be described as tested until the 24-method suite has an execution record.

## 10. Recommended follow-up

1. Pin and verify SHA-256 digests for Python and SQLite source archives before extraction.
2. Pin the Ubuntu SQLite package version/archive, or preserve a verified package digest in the workflow.
3. Add an expected Python SQLite source ID and make the `durable_python_sqlite_matches_historical_baseline` flag require both version and source-ID equality.
4. Keep the LLVM archive hash check; consider pinning the Debian container image digest.
5. Preserve the manual-only Package Provider benchmark behavior; do not enable it in Required CI. Add a durable result artifact and explicitly decide whether the profiler script is part of the manual run.
6. Add a reproducible execution record for RT-16's 24 tests and CLI's 34 reference cases; consider separate non-required workflows if the tests should remain outside Required CI.
7. Add dedicated tests for the Scenario 36 fuel models before treating them as reproducible evidence.
8. Update the stale RT-04 status header and current test/toolchain references without deleting historical run records.

## 11. Conclusion

**Disposition: C reproducibility evidence audit complete; several experiments are reproduced, but the corpus is not uniformly reproducible.**

Strongest current evidence: RT-04 Required CI (364 tests), native SQLite/Rust run (10/10), LLVM preservation (2/2), and Package Provider manual benchmark (8/8 verified cases). Main gaps: RT-16 and CLI execution coverage, Python SQLite source identity enforcement, download/package checksum pinning, non-persistent benchmark output, and untested fuel models.

No source code, tests, workflows, or benchmark settings were changed by this audit.


## 12. Follow-up reproduction closure — RT-16 and CLI host references (2026-11-21)

A bounded, non-required workflow was added in PR [#136](https://github.com/aivibeflow/LLMLang/pull/136): [Research Reproducibility Smoke](../.github/workflows/research-reproducibility-smoke.yml). It runs on relevant pull requests and supports manual dispatch. It does not enter Required CI.

Run [#44937172020](https://github.com/aivibeflow/LLMLang/actions/runs/44937172020) completed successfully. The workflow checked out merge commit `784f3ad263ec2d0b244ee1f2c938901c5245aa3e`, which combines PR #136 head `ef928af8f72fc77142cb50986c4101962d945df6` with baseline main `017e64b87c87371309197a392165258b8b088dd1`. This exact distinction matters: the workflow's `GITHUB_SHA` and recorded input hashes refer to the merge checkout, not to a later main commit.

Results:

- RT-16 authorization decision suite: **24/24 tests passed**.
- CLI Python host reference: **34/34 cases passed**.
- CLI C host reference: **34/34 cases passed**.
- Workflow job: success; no failed or skipped step.

Recorded environment: Ubuntu 24.04.5 LTS, Linux x86_64, Python 3.12.16, GCC 13.3.0, runner image `ubuntu-24.04` version `20261116.133.1`. The artifact records the repository checkout and SHA-256 for all five exercised source files:

| Input | SHA-256 |
|---|---|
| RT-16 `policy.py` | `9bde40efd58f19ff9fbd79d3bef49bfba4d13e887aff04a283e9ca03cad12b86` |
| RT-16 `test_policy.py` | `5a4850fe8b867deff1d2c2e7ca38df77a2f359129367720a9c8ee1b53c0770e2` |
| CLI `run.py` | `c9586d209c2ab0caef35dc071f6e482427851e8669fe7c55d80425835b632881` |
| CLI `reference.py` | `04a357c8ff550e661ba31bb5ba3403a8ed76cbe49e865314856570e6388f9ce7` |
| CLI `reference.c` | `93c5aedc291cc5fcabb7ff0defe64da140769cf71bde2531d7088f268150d1b4` |

Artifact [14720410382](https://github.com/aivibeflow/LLMLang/actions/runs/44937172020/artifacts/14720410382) contains the environment/input manifest and three execution logs. Its ZIP SHA-256 is `3c116f61342d2669fa0fe6764d2c02a8af6bd4cfa488ec7bc4afb72663feb885`; configured retention expires 2026-12-21.

Interpretation boundaries:

- RT-16 now has an actual execution record for its finite in-memory decision model. It still does not test persistent multi-client nonce storage, authenticated human approvals, cryptographic evidence provenance, or production authorization enforcement.
- CLI host-reference modes now have a fresh, revision-bound 34/34 result for both Python and C implementations. This does not repair or supersede the historical three-executable pilot's negative-division mismatch and does not demonstrate a compiled LLMLang implementation.
- The workflow is a non-required reproduction gate; passing it does not imply Required CI coverage.

The separate documentation correction for the stale RT-04 opening status is proposed in PR [#137](https://github.com/aivibeflow/LLMLang/pull/137). That PR records the already-existing bounded run #44774296240 and does not alter its evidence.

Remaining C gaps are unchanged unless explicitly closed above: Python SQLite source-ID equality is recorded but not enforced against a historical expected value; Python/SQLite source archive checksums and the distro SQLite package identity are not fully pinned; Package Provider benchmark results remain log-only and its profiler remains outside execution; Scenario 36 fuel models still lack dedicated tests; and the broader prototype corpus is not uniformly reproduced.
