# RT-00 C-02 — SQLite identity and source archive integrity follow-up

**Date:** 2026-11-21  
**Baseline:** `b52ba2fb32e2c315997c74d8924c2c9aaeb177dc`  
**Scope:** Scenario 130's Python SQLite reproduction identity; source-archive integrity for SQLite 3.53.1, Python 3.12.14, and the LLVM 19.1.7 package.  
**Disposition:** exact runtime identity and three archive digests are now enforced for future workflow runs. Historical Scenario 130 identity cannot be reconstructed retrospectively.

## 1. Scenario 130 Python SQLite identity

The successful native reproduction run [#44774296240](https://github.com/aivibeflow/LLMLang/actions/runs/44774296240) recorded the separately loaded Python SQLite runtime as version `3.53.1` with source ID:

```text
2026-05-05 10:34:17 c88b22011a54b4f6fbd149e9f8e4de77658ce58143a1af0e3785e4e6475127e9
```

The original Scenario 130 execution report did not preserve its source ID. The value above is therefore a newly established **future reproduction baseline**, not evidence that the original historical run used the same build.

The RT-04 native runner now requires both the expected version and exact source ID before it executes the durable-receipt probe. Its machine-readable field is renamed to `durable_python_sqlite_matches_reproduction_baseline`; version-only equality is no longer reported as full baseline equivalence. The expected identity is asserted by `test_rt04_native_probe_runner.py`.

## 2. Downloaded source and package integrity

The native reproduction workflow verifies these SHA-256 digests before extraction or use:

| Input | Expected SHA-256 | Basis |
|---|---|---|
| SQLite 3.53.1 source archive `sqlite-autoconf-3530100.tar.gz` | `83e6b2020a034e9a7ad4a72feea59e1ad52f162e09cbd26735a3ffb98359fc4f` | Buildroot package hash update; independently corroborated by the Fossies archive listing |
| Python 3.12.14 source archive `Python-3.12.14.tgz` | `6c6df908d2c3fd24e6d76869e92542abd0f33aec9dfc18df8875f89660286d43` | Official Python 3.12.14 release page |
| Debian LLVM 19 package `llvm-19_*.deb` | `0b1b7263f4f45e261099240fdbf00fc14b42b88410fd829e041bf83ea45866cb` | Exact package digest recorded by the prior LLVM preservation run |

The Python archive is checked in both jobs that download/build Python 3.12.14. The SQLite source archive is checked before extraction. The LLVM package check is now an enforcing comparison, rather than merely printing the downloaded package's digest.

References:
- [Python 3.12.14 official release page](https://www.python.org/downloads/release/python-31214/) publishes the Python source archive SHA-256.
- [Buildroot's SQLite 3.53.1 hash update](https://lists.buildroot.org/pipermail/buildroot/2026-May/801705.html) records the locally computed SQLite archive SHA-256.
- [Fossies SQLite 3.53.1 archive listing](https://fossies.org/linux/misc/sqlite-autoconf-3530100.tar.gz/index_tp.html) independently reports the same SQLite SHA-256.
- The LLVM digest is the one captured in the previous reproduction audit and artifact manifest.

## 3. Scenario 102 test-count reconciliation

The historical Scenario 102 result says that seven focused result-policy tests passed. The current test module `research/PROTOTYPES/RT-04-01/test_rt03_feasibility_outcomes.py` contains eight test methods, with blob SHA:

```text
7f18c604051076b86974adfd96ed79ea718075d4
```

The same path at the head of Required CI run [#44801357527](https://github.com/aivibeflow/LLMLang/actions/runs/44801357527), commit `c35ba93c031684100dcdbc06a34b0e14696c37ab`, has the identical blob SHA. That run's repository-structure workflow executes:

```sh
python -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_*.py' -v
```

The run reports 364 passing RT-04 tests. The eight-method Scenario 102 module was therefore present unchanged in that successful suite. This establishes execution evidence for the current eight-method source, while the historical seven-test focused-run count remains a separate record whose exact source revision was not preserved. No historical result has been rewritten.

## 4. Remaining reproducibility limits

- The original Scenario 130 Python SQLite source ID is still unavailable; the new pin applies prospectively.
- The Ubuntu distribution C SQLite package is selected by package name rather than a fixed package archive digest. The native runner nevertheless rejects it unless both its version and exact Scenario 120–128 source ID match.
- The `ubuntu-26.04` runner image and `debian:trixie` container tag are not pinned by immutable image digest.
- The rustup/setup action bootstrap is not independently digest-pinned.
- Archive digest verification proves the downloaded bytes match the recorded digest; it does not independently authenticate the provenance of the digest. The source basis for each digest is identified above.

## 5. Validation status

This PR changes the native runner, its focused version-gate tests, the manual reproduction workflow, and Scenario 130's reproduction notes. The workflow is intentionally non-required. The PR's Required CI and the manually dispatched native workflow must both be checked on the final PR head before this follow-up is considered reproduced.

No architecture or language-semantics decision is made.
