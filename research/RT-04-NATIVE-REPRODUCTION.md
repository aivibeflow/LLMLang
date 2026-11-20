# RT-04 Native Reproduction Protocol

**Status:** reproducibility harness prepared; a workflow execution is still required before any native result is marked reproduced.

## Purpose

Keep three evidence layers distinct:

1. Python model and generator tests, run by Required CI.
2. Native SQLite observations from the C API and the durable-receipt process-interruption fixture.
3. Generated Rust compilation and execution compared with the Python reference.

A passing layer does not imply that another layer ran. The native workflow is deliberately manual and is not a Required CI gate.

## Reproduction entry point

Run **Actions → RT-04 Native Reproduction → Run workflow** on the target revision, or let the workflow run automatically on a pull request that changes the RT-04-01 prototype tree or this protocol. The workflow uses Ubuntu 26.04, Python 3.12.14, and Rust 1.85.1. It installs the distribution `libsqlite3-0` package rather than compiling the upstream SQLite archive: the scenario reports record the distribution build's `alt1` source ID, which is different from the upstream 3.46.1 autoconf archive even though the version number is identical. Before running the C-API probes, the runner checks both SQLite's version and the exact source ID recorded by Scenarios 120–128. The C library is selected explicitly through `LLMLANG_SQLITE_LIBRARY`, rather than relying on whichever shared library happens to be found first.

The workflow invokes the following commands:

| Evidence slice | Executable probe |
|---|---|
| Scenario 120 — base cleanup contracts | `sqlite_cleanup_probe.py` |
| Scenario 121 — admitted recovery plans | `sqlite_cleanup_probe.py --recovery-matrix` |
| Scenario 122 — snapshot freshness | `sqlite_cleanup_probe.py --snapshot-freshness` |
| Scenario 123 — close call boundary | `sqlite_close_call_probe.py` |
| Scenario 124 — close interleavings | `sqlite_close_interleavings_probe.py` |
| Scenario 125 — callback reentry and dependent coverage | `sqlite_close_reentry_probe.py` |
| Scenario 126 — backup resource roles | `sqlite_backup_roles_probe.py` |
| Scenario 128 — backup finish outcomes | `sqlite_backup_outcomes_probe.py` |
| Scenario 130 — durable invocation receipts | `sqlite_durable_receipts_probe.py` |
| Scenario 133 — generated Rust conformance | `rt04_rust_owned_probe.py --rustc rustc` |

Scenarios 127, 129, 131, and 132 are finite model/source-fixture studies whose tests are included in the RT-04-01 Required CI discovery step; they do not have a separate native command in the current corpus. Scenario 129's CancelIoEx evidence is API-documentation evidence, not a native Windows execution.

## Captured evidence

The [native runner](PROTOTYPES/RT-04-01/run_native_probes.py) and its [command-inventory/version-gate tests](PROTOTYPES/RT-04-01/test_rt04_native_probe_runner.py) are the checked-in entrypoints. The tests verify suite composition and toolchain pins; the workflow run supplies the native observations.


The runner's command inventory is checked by `test_rt04_native_probe_runner.py`, which is part of the normal RT-04-01 Python test-discovery step. The runner prints the pinned runtime identity and each probe's stdout to the workflow log, and writes `summary.json` plus separate stdout/stderr files for every command. Scenario 130 is run in a child process with the separately built SQLite 3.53.1 shared library selected through `LD_LIBRARY_PATH`; the runner verifies both `sqlite3.sqlite_version` and records `sqlite_source_id()` before invoking the durable-receipt probe. The summary records:

- repository commit, Python version, operating system and architecture;
- C SQLite version and source ID;
- Python's `sqlite3` runtime version;
- Rust compiler version and verbose target/build metadata;
- exact command, exit status, timeout status, and output-file names.

The runner requires the C SQLite source ID used by Scenarios 120–128 and Rust 1.85.1. For Scenario 130 it builds SQLite 3.53.1 separately and launches the durable-receipt probe with that shared library first on `LD_LIBRARY_PATH`. The child preflight checks the actual Python `sqlite3` version and records the SQLite source ID; it skips the probe if the version is not 3.53.1.

The first attempt on Ubuntu 24.04 built upstream SQLite 3.46.1 and correctly rejected it: the library reported source ID ending `a1e33`, while the scenario reports pin the distribution build ending `alt1`. The C-API probes were skipped; the durable-receipt and Rust probes still passed. This is an environment mismatch, not a behavioral counterexample. The corrected Ubuntu 26.04 run selected the distribution library, matched the exact `alt1` source ID, and passed all ten commands. See workflow run 44770910183 and artifact 14648440097. Per-case output comparison confirmed Scenarios 120–128 and 133 against their reports. The first run's Python sqlite3 runtime was 3.46.1, not Scenario 130's 3.53.1. The follow-up run 44771268838 builds and loads 3.53.1 for the durable-receipt subprocess, verifies the version and records source ID, and passes all ten commands. The historical report did not preserve its Python SQLite source ID, so only version-level equivalence is claimed.

The workflow uploads all captured output as a 30-day Actions artifact, including partial output when a command fails. A successful workflow means every listed command completed successfully under the recorded environment; it does not prove general LLMLang semantics, source-to-CFG completeness, untested FFI contracts, or behavior on other platforms.

## Remaining work

- Completed for the merged RT-04 implementation by run 44774296240; its complete artifact, source-tree provenance, and archive hash are recorded below. Rerun if probe code or pinned tools change.
- The earlier per-case comparison is recorded in the corpus audit. The latest run re-executed the same ten commands; its summary and key observations were checked against the recorded scenario outputs. Future reruns must preserve mismatches as findings rather than editing expected values.
- Latest artifact 14650095720 is retained by Actions for the configured 30-day period; its SHA-256 is recorded below. The historical Scenario 130 report did not record the Python SQLite source ID, so exact historical build identity cannot be established retrospectively.
- The latest artifact reference and workflow run ID are recorded in the corpus audit and semantic traceability report.
- Keep the native workflow non-required until its runtime, timeout, and host assumptions are stable.



## Latest final-validation rerun — 2026-11-20

Research Native Reproduction run [44774296240](https://github.com/aivibeflow/LLMLang/actions/runs/44774296240) passed all ten RT-04 commands: 10 passed, 0 failed, 0 skipped. Artifact [14650095720](https://github.com/aivibeflow/LLMLang/actions/runs/44774296240/artifacts/14650095720) contains `summary.json` and per-command stdout/stderr. The downloaded archive is 6,975 bytes with SHA-256 `c6c042c2458b0b98fa0d1ed07eb476d75fa59d6192997215080941237a8f4d8b`.

The manifest records C SQLite 3.46.1 with source ID `2024-08-13 09:16:08 c9c2ab54ba1f5f46360f1b4f35d849cd3f080e6fc2b6c60e91b16c63f69aalt1`, Python 3.12.14 with the separately loaded SQLite 3.53.1 source ID `2026-05-05 10:34:17 c88b22011a54b4f6fbd149e9f8e4de77658ce58143a1af0e3785e4e6475127e9`, and Rust 1.85.1. The first Ubuntu 24.04 attempt using upstream SQLite 3.46.1 was correctly rejected because its source ID did not match the scenario distro build; the later `alt1` run executed all eight C-API probes. The source ID is pinned, but the distro package version/archive is not separately recorded.

The artifact's repository commit is merge-ref `8c4a82c91f039309bba769c49bd00515e3713feb`; its tree SHA is identical to main merge commit `b808c3a8f984bbc5c175ecf45d61e0e8db7a00bb`. Current main has only subsequent documentation/inventory/audit changes relative to that code tree. This is code-tree-equivalent reproduction, not execution with the latest main commit SHA.
