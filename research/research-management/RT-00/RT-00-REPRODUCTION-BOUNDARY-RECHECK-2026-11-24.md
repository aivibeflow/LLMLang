# RT-00 — Reproduction boundary recheck for implementation studies

**Research item:** `PLAN.md` §0.2 — reproducible commands, fixtures, tool versions, and expected outputs  
**Date:** 2026-11-24  
**Baseline main:** `48003c3cf284cc1a66693896172d56d7f8a3ce8f`  
**Evidence type:** bounded reproduction-route audit plus one focused suite rerun  
**Status:** four-report crosswalk; no claim that all historical experiments were reproduced  
**Question:** Can a reviewer follow each recent implementation study's recorded commands to reproduce the stated result, and do those commands reproduce the claimed design result or only its supporting fixture?

## Method

I examined the same four implementation-relevant studies: RT-19 transaction/recovery, RT-19 multi-file publication, RT-25 allocator workload fit, and RT-32 Lean observation binding. I checked their source revisions, commands, environment/tool versions, raw artifact links, and expected outputs. I reran the RT-19 Toolchain focused suite on this main checkout using Python 3.12.14. I did not rerun the allocator benchmark or Lean proof replay in this pass; the necessary `rustc`, `lean`, and `llvm-as` executables were not available in this shell.

## Reproduction crosswalk

| Study | Command and expected output | What is reproducible | What is not reproduced by that command |
|---|---|---|---|
| RT-19 transaction/recovery | Two `python3 -B -m unittest discover` commands are recorded for Prototype 01 and SQLite Content Store; expect 9/9 for each on CPython 3.12.14. | Adjacent in-memory workspace and SQLite object-store component tests. | The compared state machines, persistent coordination, crash recovery, Git publication, and inter-process races. |
| RT-19 multi-file publication | This recheck recorded and ran `python3 -B -m unittest discover -s research/toolchain-and-collaboration/PROTOTYPES/TOOLCHAIN-SERVER-01 -p 'test_toolchain.py' -v`; **9/9 passed** on Python 3.12.14. The source report now includes that exact command and expected output. | One-file temp-write/replace and in-memory workspace behavior covered by existing tests. | Multi-file generation/pointer/Git-tree publication, filesystem portability, or the failure points proposed in the report. |
| RT-25 workload fit | The report provides a Python snippet that reads `results-linux-x86_64.json` and computes medians/minima/maxima for each provider and metric. It states the archived runner's source/config evidence and the current recheck environment. | Summary statistics from the archived 16-process result file. | A fresh allocator measurement. This environment lacks `rustc`, TCMalloc and mimalloc, so re-running the statistics script cannot be represented as an allocator benchmark rerun. |
| RT-32 Lean observation binding | The report provides `python3 -B "$fixture/replay.py" --output "$replay"` followed by `cmp "$fixture/results.json" "$replay"`; it pins Lean 4.36.0, Python 3.12.14 and artifact hashes. | Exact fixture regeneration and equality with the pinned ledger, when its Lean toolchain is available. | General source-to-SPG correspondence or proof for profiles outside the admitted fixture. Lean was unavailable in this recheck environment, so the command was reviewed, not rerun. |

## Findings

1. The four reports identify bounded inputs and limitations. RT-19 transaction and RT-32 provide exact test/replay commands and expected outputs. RT-25's command recomputes summary statistics from archived raw data and is explicitly not a fresh benchmark.
2. The first RT-19 multi-file report stated that the focused suite passed but omitted the exact command and expected test count. This recheck reran the suite and amended the report with both. That closes a documentation gap for the existing component tests only.
3. Required executables are a practical external dependency for reproducing some results. In this shell, Python 3.12.14 was present; `lean`, `rustc`, and `llvm-as` were absent. This is an environment availability observation, not evidence that those tools are absent from CI or maintainers' systems.
4. Reproducing adjacent tests, archived statistics, or a formal fixture does not validate the unimplemented publication, allocator, transaction, or end-to-end proof choices. Their decision discriminators still require their own runner and fixtures.

## Stage 0.2 implication

The plan can mark a bounded four-report reproduction crosswalk complete and use the corrected RT-19 publication report as a concrete example. It must leave whole-corpus reproducibility and all design-level experiments open. The recorded outputs give reviewers a direct rerun path without implying that test-suite repetition establishes a backend decision.

## Remaining dependencies

- Reproduce the RT-25 benchmark on a pinned Rust host with glibc, jemalloc, TCMalloc, and mimalloc available.
- Reproduce RT-32 with its pinned Lean toolchain and verify CI/ledger provenance; separately close the Python/SPG source-correspondence obligation.
- Implement RT-19 persistent coordinator and multi-file publication candidates before crash, race, and recovery claims can be reproduced.
- Continue the corpus-wide historical run attestation, claim-level reproducibility, and independent human review in Stage 0.1/0.2.

**Conclusion:** reproduction instructions are sufficient for the component checks or archived-data transforms they name, but not for the unimplemented design alternatives. Stage 0.2 remains open for maintainer adoption and corpus-wide validation.
