# Prototype Evidence Graph Review — RT-04-01 — 2026-11-20

**Status:** first-pass implementation/test/workflow/evidence graph review  
**Baseline:** current main before this review, `05602dc32f7ced24fba0111dc643ade42029f210`  
**Scope:** `research/PROTOTYPES/RT-04-01/`, its family README, native reproduction protocol, Required CI test discovery, native workflow, and the linked Scenario 120–133 reports  
**Decision boundary:** evidence and navigation review only; no language or runtime policy is selected

## 1. Inventory and family structure

The RT-04-01 directory contains 106 files:

| File type | Count |
|---|---:|
| Python files | 103 |
| Family README | 1 |
| Rust source fixture | 1 |
| Solver requirements file | 1 |
| **Total** | **106** |

The Python files comprise 45 `test_*.py` modules and 58 non-test modules/runners. A static count of `def test_*` methods in the 45 test modules is 364. The Required CI workflow discovers the family with `python -B -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_*.py' -v`.

The older family README entry records 44 modules and 360 tests for its earlier source snapshot. That historical result is not rewritten. The current tree adds `test_rt04_native_probe_runner.py`, which contributes four test methods; the current count is 45 modules and 364 methods. Required CI run [44774552406](https://github.com/aivibeflow/LLMLang/actions/runs/44774552406) passed on main merge commit `b808c3a8f984bbc5c175ecf45d61e0e8db7a00bb`. The later main changes through `05602dc32f7ced24fba0111dc643ade42029f210` are documentation, inventory, and audit changes only; the RT-04-01 test/source tree is unchanged.

## 2. Implementation-to-test and runner graph

| Implementation or evidence entrypoint | Paired checks / consumers | Evidence boundary |
|---|---|---|
| SQLite cleanup, recovery, snapshot-freshness, close-boundary, interleaving, reentry, backup-role, and backup-outcome probes | Corresponding `test_*.py` model/probe checks; Scenario 120–128 reports | Eight selected native C-API commands are in the native reproduction suite. They do not cover every SQLite dependent type or all model states. |
| `sqlite_durable_receipts_probe.py` | `test_rt04_durable_receipts.py`; Scenario 130 | Runs in a child process using separately built SQLite 3.53.1. The test suite validates the model/probe code; the native workflow supplies process-crash observations. |
| `rt04_rust_owned_probe.py` | `rt04_owned_probe.rs`, `test_rt04_rust_owned_probe.py`; Scenario 133 | Generates/compiles a bounded Rust fixture and compares 125,952 native observations with the Python reference. It is not general source lowering or live FFI validation. |
| `run_native_probes.py` | `test_rt04_native_probe_runner.py`; `.github/workflows/rt04-native-reproduction.yml` | Orchestrates eight SQLite C-API commands, the SQLite 3.53.1 durable-receipt command, and the generated-Rust command. It captures environment, summary, stdout, and stderr. |
| `test_rt04_native_probe_runner.py` | Imports `run_native_probes.py`; Required CI unittest discovery | Four tests check the command inventory, the ten-command suite composition, tracked probe paths, and pinned toolchain baselines. They do not execute the ten native commands. |

The family README already provides a targeted semantic-overlap review. It correctly distinguishes the resource-return/cleanup, recursion/fuel, cancellation, fairness, path-analysis, wire-presence, and native lifecycle sequences rather than treating shared fixtures or adjacent Scenario IDs as duplicates. Its statement that no duplicate/supersession was found is scoped to those inspected clusters; it is not a corpus-wide negative proof.

## 3. Navigation gaps and orphan assessment

Two files introduced after the README's earlier file index are not linked from the family README:

- `run_native_probes.py`
- `test_rt04_native_probe_runner.py`

Neither is an orphan:

- the workflow invokes `run_native_probes.py` with `--suite all`;
- the native reproduction protocol describes the runner and names its test;
- the test imports the runner;
- Required CI discovers the test by filename.

The gap is one of family-index navigation, not missing implementation/test provenance. This review adds direct links to both files in the family README and protocol.

The `rt03_blocking_protocol.py` relationship to a scenario result remains explicitly unresolved in the family README. It is not reclassified as an orphan. Scenarios 127, 129, 131, and 132 remain model/process/source-fixture evidence, not additional native SQLite commands. Scenario 133 is the generated-Rust native comparison.

## 4. Native reproduction evidence

Research Native Reproduction run [44774296240](https://github.com/aivibeflow/LLMLang/actions/runs/44774296240) completed the RT-04 native job successfully:

| Result | Count |
|---|---:|
| Commands passed | 10 |
| Commands failed | 0 |
| Commands skipped | 0 |

Artifact [14650095720](https://github.com/aivibeflow/LLMLang/actions/runs/44774296240/artifacts/14650095720) contains `summary.json` and per-command stdout/stderr. Downloaded archive: 6,975 bytes; SHA-256 `c6c042c2458b0b98fa0d1ed07eb476d75fa59d6192997215080941237a8f4d8b`.

The manifest records:

- Python 3.12.14 on Linux x86-64;
- C SQLite 3.46.1 with source ID `2024-08-13 09:16:08 c9c2ab54ba1f5f46360f1b4f35d849cd3f080e6fc2b6c60e91b16c63f69aalt1`;
- Python `sqlite3` 3.53.1 for Scenario 130, source ID `2026-05-05 10:34:17 c88b22011a54b4f6fbd149e9f8e4de77658ce58143a1af0e3785e4e6475127e9`;
- Rust 1.85.1, LLVM 19.1.7.

The earlier Ubuntu 24.04 attempt used upstream SQLite 3.46.1 with source ID ending `a1e33`, which did not match the scenario's distro source ID; eight C-API probes were correctly skipped. The later successful run uses the exact `alt1` source ID and executes all eight C-API probes. This resolves the behavioral execution gap for the pinned fixture. It does not establish that the `alt1` library is the upstream SQLite 3.46.1 build; the workflow records the exact runtime source ID, but not a separately pinned distro package archive/version.

The durable-receipt subprocess uses SQLite 3.53.1 and records its source ID. Scenario 130's historical report did not preserve that source ID, so version-level equivalence is established but byte-identical historical build provenance is not.

The native artifact's `repository_commit` is merge-ref commit `8c4a82c91f039309bba769c49bd00515e3713feb`. Its Git tree SHA is identical to main merge commit `b808c3a8f984bbc5c175ecf45d61e0e8db7a00bb`. The current main commit `05602dc32f7ced24fba0111dc643ade42029f210` differs from that code tree only in documentation, inventory, and audit files. Therefore the run is tree-equivalent to the merged RT-04 implementation, but it was not literally executed with the current main commit SHA.

The eight C-API commands cover the bounded native probes associated with Scenarios 120–126 and 128. The remaining two commands are Scenario 130 durable receipts and Scenario 133 generated Rust. Scenario 127 and 129–132 are not thereby promoted to native probe coverage.

## 5. LLVM preservation runner relationship

The same Research Native Reproduction run [44774296240](https://github.com/aivibeflow/LLMLang/actions/runs/44774296240) also passed both LLVM preservation commands:

- integer preservation: 20,978 comparisons at each of O0 and O3;
- byte-view preservation: 9,800 comparisons at each of O0 and O3;
- zero mismatches in the checked fixtures; expected negative controls disagreed with the source reference.

Artifact [14650040345](https://github.com/aivibeflow/LLMLang/actions/runs/44774296240/artifacts/14650040345) contains the manifest and both command outputs. Downloaded archive: 3,245 bytes; SHA-256 `e36739481ea3b57ec7e58265f1e4b378ac4248a9b74d03e4711900a9d775eced`.

The manifest records Debian Trixie LLVM package `1:19.1.7-3+b1`, package SHA-256 `0b1b7263f4f45e261099240fdbf00fc14b42b88410fd829e041bf83ea45866cb`, Python 3.12.14, GCC 14.2.0, GNU ld 2.44, and x86-64. The runner `run_llvm_preservation_probes.py` is invoked by the same workflow but was not directly linked from the reproduction protocol or research index before this review.

The two LLVM commands are a bounded reproduction of Scenarios 96A/96B. They are not Required CI tests and do not establish whole-domain source-to-LLVM correctness, other targets, or general pointer provenance.

## 6. Workflow and CI boundary

- `.github/workflows/rt04-native-reproduction.yml` supports `workflow_dispatch` and focused pull-request path filters. It runs the native RT-04 and LLVM jobs and uploads 30-day artifacts.
- Required CI separately discovers the 45 RT-04-01 test modules. Its success is test-suite evidence, not proof that all native experiments ran.
- The native workflow is not a required CI gate. A successful native run is bounded by its pinned tools, host, fixtures, and command inventory.
- The artifact archives are time-limited. This review records their run IDs, artifact IDs, sizes, and SHA-256 hashes; it does not copy the raw archives into the repository.

## 7. Remaining gaps

1. The RT-04 family README and both reproduction protocols now need direct links to their runner/test entrypoints; this review updates those links.
2. The `alt1` C SQLite source ID is pinned, but the distro package version/archive is not separately recorded in the run manifest.
3. The Scenario 130 historical source ID is unavailable; only version-level equivalence is supported.
4. Workflow artifacts expire after the configured retention period. Long-term preservation of raw run outputs is not provided by the current repository snapshot.
5. This family review does not audit all 243 prototype files or establish that every prototype claim has a paired test, fixture, and report. Other prototype families remain separate work.

**Conclusion:** the new RT-04 runner and its tests have clear workflow/test provenance and are not orphan artifacts. The family README has a navigation gap and an outdated test-suite count, which this update corrects. The latest native artifacts establish successful execution of the ten-command RT-04 suite and two LLVM preservation probes on a code tree identical to the merged RT-04 implementation; the evidence remains bounded and the full prototype-family graph audit remains open.
