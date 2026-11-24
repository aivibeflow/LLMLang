# RT-00 C — Current-main reproducibility delta

**Date:** 2026-11-23  
**Repository:** `aivibeflow/LLMLang`  
**Current main baseline:** `a65239db82ecf446fcadb9f81caa86537e528df5`  
**Baseline report:** [RT-00-C-REPRODUCIBILITY-AUDIT-2026-11-20.md](RT-00-C-REPRODUCIBILITY-AUDIT-2026-11-20.md)  
**Disposition:** bounded status/provenance reconciliation. No successful native or LLVM experiments were rerun.

## 1. Scope

This delta uses the existing C audit and later retained workflow evidence. It rechecks PR state, workflow integration, exact tested revisions, and current Git blob identity for the test inputs that materially affect the unresolved C findings. It does not repeat successful RT-04 native/LLVM, RT-16, CLI, RT-06/RT-09, or RT-26 executions.

## 2. PR #136/#137 supersession and current-main workflow state

The original C follow-up refers to PR #136 as the source of the RT-16/CLI smoke workflow and PR #137 as the pending RT-04 status correction. Both older PRs are closed without merge.

Their replacements are integrated:
- PR #165 merged the non-required `research-reproducibility-smoke.yml` workflow as `088664b51ea285025133338fd1ce3a0e8be5d0a6`. The workflow file's current-main Git blob is identical to the version on the earlier PR #136 checkout.
- PR #166 merged the RT-04 reproduction-status correction as `47520bae555640d8282efd0ccb2f70804c415689`. The current [RT-04 native reproduction protocol](RT-04-NATIVE-REPRODUCTION.md) has the corrected bounded status and current toolchain/source-identity instructions.

Therefore the old C report's PR #136/#137 attribution is historical. Current main contains the RT-16/CLI non-required workflow and the corrected RT-04 protocol. The RT-16/CLI workflow remains outside Required CI.

## 3. RT-16 authorization and CLI host references

The existing run [#44937172020](https://github.com/aivibeflow/LLMLang/actions/runs/44937172020) completed on the PR #136 merge checkout `784f3ad263ec2d0b244ee1f2c938901c5245aa3e`, not on current main. The result remains applicable to current source because the Git blob identities of all five exercised files match current main:

- RT-16 `policy.py` and `test_policy.py`;
- CLI `run.py`, `reference.py`, and `reference.c`.

Recorded results remain:
- RT-16 authorization model: 24/24 tests;
- CLI Python host reference: 34/34 cases;
- CLI C host reference: 34/34 cases;
- Ubuntu 24.04.5, x86_64, Python 3.12.16, GCC 13.3.0.

Artifact [14720410382](https://github.com/aivibeflow/LLMLang/actions/runs/44937172020/artifacts/14720410382) retains the input manifest and logs. PR #165 subsequently integrated the same non-required workflow into main.

**Current status:** execution and environment evidence exists for the unchanged current-main test sources. There is still no Required CI coverage for RT-16 or CLI host references. The run does not test persistent multi-client nonce storage, production authorization enforcement, or a compiled LLMLang implementation. The historical three-executable CLI pilot's negative-division mismatch remains a separate unresolved result.

## 4. RT-04 native and LLVM reproduction

PR #166 integrated the RT-04 status correction and records the current-main reproduction:
- Required CI [#44942995298](https://github.com/aivibeflow/LLMLang/actions/runs/44942995298): success;
- native reproduction [#44942995286](https://github.com/aivibeflow/LLMLang/actions/runs/44942995286): 10/10 commands passed;
- LLVM preservation in the same run: 2/2 probes passed;
- native artifact [14722417949](https://github.com/aivibeflow/LLMLang/actions/runs/44942995286/artifacts/14722417949);
- LLVM artifact [14722227550](https://github.com/aivibeflow/LLMLang/actions/runs/44942995286/artifacts/14722227550).

The current RT-04 protocol pins the distribution C SQLite source ID used for Scenarios 120–128 and separately builds SQLite 3.53.1 for Scenario 130. These are bounded fixture/toolchain results; they are not general SQLite or backend conformance evidence. No rerun is justified while the probe sources and toolchain pins remain unchanged.

## 5. SQLite source identity — partially constrained, not fully closed

Current RT-04 native reproduction now verifies the exact C SQLite source ID for Scenarios 120–128, rather than relying only on the version string. Scenario 130 builds SQLite 3.53.1 separately and records the Python `sqlite_source_id()` observed in the child process.

The historical identity gap remains:
- the historical Scenario 130 report did not preserve the Python SQLite source ID;
- the current run can record the source ID but cannot reconstruct the missing historical value;
- Python/SQLite source archive checksums and the distribution package identity are not uniformly pinned.

Therefore exact historical source identity for the Python SQLite runtime is unresolved. Do not equate equal version numbers with identical source builds.

## 6. RT-24 Git reproduction — two different suites, two different conclusions

### 6.1 Call-target merge suite

Run [#44950912463](https://github.com/aivibeflow/LLMLang/actions/runs/44950912463) executed 18/18 tests from exact checkout `fa98a20c8ab5d3f28980b609c04aaec135dddde5`. The current-main Git blob for `test_rt24_call_target_merge.py` is unchanged from that checkout (`e517cca0355e27576404aa4affc28e640fb78cd0`).

The runner used Git 2.56.1, while the report declares Git 2.52.0. This is still an environment mismatch. The 18/18 behavioral result is real for the recorded environment, but it is not an exact reproduction under the declared toolchain.

### 6.2 Git replay/source-closure suite

PR #238 is closed without merge. Its final-head run [#45073046189](https://github.com/aivibeflow/LLMLang/actions/runs/45073046189) passed 11/11 tests under Git 2.52.0 and CPython 3.12.14. The current-main Git blob for `test_rt24_git_replay.py` is unchanged from the tested checkout (`52e8f8ece4e6086ee328c66a008504f179b53aab`).

The final report/workflow update and artifact are branch-only; the run artifact [14774146651](https://github.com/aivibeflow/LLMLang/actions/runs/45073046189/artifacts/14774146651) remains available. This is a distinct source-closure/replay suite. It does **not** resolve the Git 2.56.1 versus 2.52.0 mismatch for the separate 18-test call-target merge suite.

The 11/11 result is bounded to one explicit replay fixture and does not prove a general replay coordinator, multi-commit conflict handling, concurrent publication safety, or RT-20/RT-23 integration.

## 7. Fuel probes and benchmark provenance

- Scenario 36 fuel models still have no dedicated test modules or Required CI coverage. Their scripts and exploratory observations must not be described as reproduced test evidence.
- Package Provider's 8/8 verified cases remain a manual/log-based result. There is no durable benchmark result artifact, and the profiler is not part of the executed run.
- Other benchmark results remain exploratory or synthetic. They should not be promoted into Required CI solely to improve apparent coverage.
- The C audit's earlier package/index/identity test counts remain bounded to their recorded suites; they do not establish benchmark reproducibility.

## 8. Current C status

| Area | Current status |
|---|---|
| RT-04 Required CI/native/LLVM | Reproduced for recorded fixtures; no rerun needed |
| RT-16 authorization | 24/24 execution recorded; source unchanged; workflow is non-required |
| CLI host references | 34/34 Python and 34/34 C; source unchanged; not a compiled LLMLang implementation |
| RT-24 call-target merge | 18/18, but Git 2.56.1 differs from declared 2.52.0 |
| RT-24 Git replay/source closure | 11/11 under Git 2.52.0; branch-only report/workflow update |
| SQLite identity | C source ID pinned for selected scenarios; historical Python source ID/checksum gap remains |
| Fuel models | No dedicated tests; unresolved |
| Benchmarks | Manual/exploratory, incomplete durable provenance |
| External tool/source checksums | Unresolved; continue in Stage D |

The original C report's conclusion that RT-16 and CLI execution coverage were still missing is superseded by its §12 follow-up and this delta. The remaining gaps are SQLite historical source identity/checksum pinning, fuel test coverage, durable benchmark provenance, RT-24's declared-toolchain mismatch, and external dependency provenance.

## 9. Conclusion

C has stronger bounded reproduction evidence than the original summary states: RT-16 and CLI host references have exact run records for unchanged current-main source files, and the non-required workflow is integrated through PR #165. RT-04 native/LLVM status is corrected and reproduced through PR #166. These do not close the remaining SQLite, fuel, benchmark, RT-24 toolchain, or external dependency gaps.

No tests were rerun for this delta. No benchmark was promoted to Required CI, no expected result was edited, and no historical result was rewritten.
