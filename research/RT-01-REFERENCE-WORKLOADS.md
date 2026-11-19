# RT-01 — Reference workloads for comparing LLMLang designs

**Status:** Initial workload set. The CLI acceptance corpus has been calibrated with two host implementations. Candidate toolchain and authoring measurements remain open.

## 1. What the workloads must distinguish

The [LLMLang concept](LLMLang-CONCEPT.md) and [Development Engine RFC](RFC-DEVELOPMENT-ENGINE.md) motivate different kinds of work. Someone writing a small utility needs a short path from specification to executable. An author changing a shared library needs to know which consumers and evidence are affected. A maintainer accepting an agent-generated change needs to reproduce the checks and decide whether to authorize it. The [option matrix](RESEARCH-OPTION-MATRIX-01.md) evaluates these outcomes alongside the feasibility of interpreter/VM and native targets.

| Representative task | Acceptance evidence | Current evidence and next comparison |
|---|---|---|
| Build an ordinary CLI from a task description | Exact output bytes, diagnostics and exit status. Source uses the profile's declared I/O, error and integer facilities. Record source constructs, tool invocations and unsupported primitives. | §2 supplies runnable observations for Hello, Echo and Calculator. Exercise the same cases through a LLMLang reference runtime and a second backend. |
| Implement a resource-owning worker with cancel and failure paths | Match the declared value/error and ordered acquire/release trace. Report the final resource set. For message-based profiles, enumerate allowed schedules and state any progress bound. | The [RT-03/04 corpus](RT-03-04-SHARED-SEMANTICS-CORPUS.md) provides scalar, cleanup and actor cases. Add a shared multi-party protocol with blocking or failure before comparing concurrency support. |
| Move or split a shared function while preserving selected clients | Map old and new call sites and show which clients keep behavior or need migration. Reject an apparently compatible replacement whose guard changes requested behavior. | The [RT-05/20 experiment](RT-05-RT-20-CALL-SITE-REFACTOR-EXPERIMENT.md) has concrete identity and behavior witnesses. Apply the changes through an import/refactor pipeline and check the resulting selection and executable behavior. |
| Replace one provider implementation and rebuild affected executables | Clean and incremental outputs agree. Count compilation, linking and verification separately, and reject stale evidence when an input it depends on changes. | The [RT-11 benchmark](RT-11-BINDING-INVALIDATION-BENCHMARK.md) instruments these actions in a C build. Repeat on the selected LLMLang backends and record checker inputs and resource use. |
| Have an agent repair a cross-module defect | Hidden checks for the requested behavior and prior behavior pass. The proposed scope, tool calls, evidence inputs and maintainer's approval are attributable to the change. | Use the [Development Engine RFC](RFC-DEVELOPMENT-ENGINE.md) and a frozen pre-change snapshot from the refactor workload. Record human intervention and total cost per accepted change as described below. |
| Rebuild a toolchain component authored in LLMLang | Build it from declared inputs, compare it with an independent implementation on the same fixtures, and review a source change through the normal toolchain. | The [RT-21 roadmap](RT-21-LLMLANG-SELF-DEVELOPMENT-AND-BOOTSTRAP-ROADMAP.md) describes a validator or dependency analyzer as an initial target. Measure only once there is executable LLMLang source. |

## 2. Executable CLI pilot

The [runner](PROTOTYPES/CLI-WORKLOADS-01/run.py) encodes all 22 numbered cases in [Hello](../examples/0001-hello-world.md), [Echo](../examples/0002-echo.md), and [Calculator](../examples/0003-calculator.md). Twelve additional cases exercise UTF-8 argument bytes, empty argument positions, CR as a separator, EOF termination, signed bounds, signed arithmetic overflow, missing and malformed tokens, and invalid separators. Each result checks the raw stdout and stderr bytes and the process exit status wherever specified. A timeout or failure to start is a failed case. Observations come from subprocesses without shell argument parsing.

For output failure cases, the runner supplies a pipe with no reader as stdout. A positive exit status or termination by SIGPIPE satisfies the failure requirement. Other signal terminations fail the fixture so an unrelated crash cannot pass the output check. The output-failure diagnostic is left unspecified by the two examples.

The calculator examples describe LF both as a record terminator and as possible token whitespace. The pilot uses a single expression per input, ending at LF or EOF, with space, tab or CR between tokens. The behavior of tokens spanning LF and trailing records needs a specification decision before it can be included in backend acceptance.

Run from the repository root on POSIX. The C reference requires Clang or GCC with checked arithmetic built-ins.

```sh
python3 -B research/PROTOTYPES/CLI-WORKLOADS-01/run.py --reference python
python3 -B research/PROTOTYPES/CLI-WORKLOADS-01/run.py --reference c
python3 -B research/PROTOTYPES/CLI-WORKLOADS-01/run.py \
  --hello ./hello --echo ./echo-args --calculator ./calculator
```

### Pilot results

The input specs come from repository baseline `72822973f7cc9fd33ede66aad05e844bf25d5bd3`. The two reference commands were run with Python 3.9.6 and Apple Clang 21.0.0 on Darwin arm64. The runner prints a result for each case and exits nonzero on any failure.

| Implementation | Hello | Echo | Calculator | Total |
|---|---:|---:|---:|---:|
| [Python host reference](PROTOTYPES/CLI-WORKLOADS-01/reference.py) | 3/3 | 7/7 | 24/24 | 34/34 |
| [C17 host reference](PROTOTYPES/CLI-WORKLOADS-01/reference.c) | 3/3 | 7/7 | 24/24 | 34/34 |
| Python host reference with division changed to floor division | 3/3 | 7/7 | 22/24 | 32/34 |

The last run used the three-executable interface. It returned status 1 after `T-0003-05` and `RT-01-calc-eof` observed `-4\n` where the contract requires `-3\n`. Both reference implementations passed the two broken-pipe cases. The pilot validates the harness on this platform. The LLMLang source examples remain illustrative, and the study has no measured syntax overhead, backend performance, or LLMLang portability results.

## 3. Controls for design comparison

For each candidate, record the version of the profile, toolchain and target along with the fixture and starting repository revision. Require the same observations across backends, with explicitly recorded unsupported cases. A disagreement with a fixture, an unsupported required feature, or missing evidence for a mandatory claim blocks acceptance for that workload. Two candidates that pass the same cases can still differ in source complexity, diagnostics or the work needed to check a change.

For the authoring experiment, fix task descriptions, starting snapshots, disclosed checks, held-out checks, model and tool versions, and time and tool permissions per run. Keep the requested new behavior and regression checks fixed across profiles, and record differing tool capabilities. Use paired tasks and vary candidate order when the same author sees both. Include human-authored runs to assess effects that could come from the agent or its tooling. Evaluate exact behavior with independent checks. A human reviewer adjudicates scope and requirement ambiguities, reviews residual proof assumptions, and approves the change. Record first-pass acceptance, final acceptance, token use, repair attempts, elapsed time, human review time, and attempted changes outside scope. Report work spent on unsuccessful runs when calculating cost per accepted change. Pinning a starting snapshot and distinguishing new-behavior checks from regression checks follow the evaluation pattern in the [SWE-bench paper](https://proceedings.iclr.cc/paper_files/paper/2024/file/edac78c3e300629acfe6cbe9ca88fb84-Paper-Conference.pdf).

Before ranking candidates, agree on which workloads must pass and which populations of tasks the weights represent. Record the intended importance and prevalence of each task family for utility authors, application maintainers, and toolchain maintainers. Score only criteria with evidence at the appropriate scope, using the option matrix's confidence scale. Keep unresolved criteria visible and report which changes in stakeholder weights reverse a ranking. The pilot establishes neither task prevalence nor numerical weights.
