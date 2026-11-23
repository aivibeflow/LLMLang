# RT-00 — Stage 0.2 pinned source provenance and historical-snapshot rechecks

**Issue:** [#285](https://github.com/aivibeflow/LLMLang/issues/285), PLAN §0.2  
**Status:** Publication/source snapshot discovery completed for eight reports; bounded historical-source CI rechecks proposed, not yet independently observed  
**Date:** 2026-11-23  
**Audit baseline:** `main` `1235911958f1fa3cf6f534e314d3dc59bc443ea2` (after PR #375)  
**Evidence type:** Git publication-history observation; Git blob/source identity; executable tests only when the new workflow publishes a passing run  
**Inputs:** [Eight-report machine-readable provenance manifest](quality-audit/2026-11-23-publication-provenance.json); [historical-snapshot workflow](../.github/workflows/research-historical-rechecks.yml).  
**Decision boundary:** A committed historical tree proves a *recoverable source snapshot*, not that it was the exact tree on the original experimenter's machine. No original environment fingerprint is recovered merely from repository history, and no research-quality policy is adopted here.

## Research question and competing claims

Can the eight remaining Stage 0.2 *baseline/provenance* documentation gaps be narrowed without inventing the exact unpublished historical working-tree state?

- **Observation to check:** the repository's commit history identifies the earliest published version of each report and a complete Git tree to which an independent checkout can be pinned.
- **Potentially invalid inference (rejected):** the report first appears in commit X, therefore its original observations were measured on commit X, on its GitHub Actions runner, or with the runner's modern toolchain.
- **Method candidate:** run exact in-tree test/benchmark sources on their published-commit snapshots with separately recorded OS/toolchain and compare the bounded outcomes, while explicitly reporting any differences from the original experimental host.
- **Alternative:** merely append today's `main` SHA to the historical report; rejected, because current `main` does not identify the original execution state.

The eight documents were selected by the [previous 33-warning triage](RT-00-QUALITY-RULES-ADJUDICATION-2026-11-23.md), not sampled randomly. Four have separately committed new executable test harnesses, one has a source-only comparative survey, and one is strictly a standards source analysis; the table below makes the evidence-type distinction explicit.

## Recoverable Git history: publication is not execution

The following abbreviated SHAs refer to full 40-character Git commits, recorded with their *exact* report-content Git blob IDs and associated source-file blobs in [the manifest](quality-audit/2026-11-23-publication-provenance.json).

| Report | Report publication snapshot (Git commit) | Git provenance found | Execution-evidence boundary |
| --- | --- | --- | --- |
| [Scenario 98](RESEARCH-SCENARIO-98-FINITE-AST-PATH-COVERAGE.md) | `d3fe3916db0b` | Report added alongside focused `test_rt03_path_model.py` | Current recheck can establish 128-valuation fixture consistency, not original run provenance or parser completeness |
| [Scenario 103](RESEARCH-SCENARIO-103-REAL-SOLVER-TIMEOUT-ISOLATION.md) | `08c8490e92b4` | Report, worker, four tests and `requirements-solver.txt` (SymPy 1.14.0) in same committed tree | Timeout behavior varies by host; UNSAT not accepted proof; do not infer historical timing reproduction |
| [Scenario 118](RESEARCH-SCENARIO-118-ATOMIC-EXECUTION-RELATIONS.md) | `e956d25bfa34` | Report, enumerator and seven-test independent global-order oracle in same committed tree | Global-order oracle only; weak-memory side not independently validated against language memory model |
| [Scenario 133](RESEARCH-SCENARIO-133-GENERATED-RUST-OWNED-RESULTS.md) | `cf96386b4060` | Report, Rust runtime and Python generator in same committed tree | Original Rust 1.85.1/Linux x86-64 result not repeated in this workflow; clean identical-host comparison still open |
| [RT-04 alternatives](RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md) | `d7caab2f4e0a` | Original comparative survey exists; **RT-04-01 prototype not present** in that publication commit | Later prototype evidence cannot be retroactively attributed to initial survey; each later addition needs its own provenance |
| [RT-11 benchmark](RT-11-BINDING-INVALIDATION-BENCHMARK.md) | `b0638a1b69a3` | Report and executable benchmark module in same committed tree | Original report measured Apple Clang 21.0/arm64, newer Linux/GCC result is cross-platform recheck, not exact original rerun |
| [Scenario 29](RESEARCH-SCENARIO-29-VERIFIED-PROOF-CHECKER-AND-ENCODER-VALIDATION.md) | first moved to `research/`: `1a0a5cfa24a5`; selected adapter snapshot `2c7f3d1035a8` | Source runner and 15 fake-executable tests exist at later pinned snapshot | **No real cvc5 or Logos proof**; this is only a process-runner fail-closed test corpus |
| [Scenario 134](RESEARCH-SCENARIO-134-WIRE-SCHEMA-EVOLUTION-INTEROPERABILITY.md) | `672cd833c00d` | Official Protobuf/Avro/CBOR documentary comparison; later architecture decision in a separate commit | No serializer/runtime execution and no unapproved wire policy should be inferred |

**Git observations:** for seven reports the first matching path-history entry marks the file as *added*; Scenario 29 was *renamed/moved*, and later changes affect it. RT-04 and Scenario 134 were amended after initial publication. The manifest identifies the initial content SHA separately from the selected checkout SHA where applicable. A Git tree is a fully defined set of committed bytes; it is not an attestation of the historical author's uncommitted workspace or physical machine.

## Proposed independent test protocol

The workflow `research-historical-rechecks.yml` runs on a PR and on manual dispatch. Each matrix case checks out a **40-character fixed Git commit**, checks the exact test source Git blob with `git hash-object`, pins CPython 3.12.14 on an Ubuntu 24.04 GitHub runner and captures `uname` and compiler version. The solver case installs `mpmath==1.3.0` and `sympy==1.14.0` from the source-pinned dependency file. None of these actions is a replay of the original developer's undocumented working directory.

| Case | Expected bounded check | Interpretation of a passing result |
| --- | --- | --- |
| `ast-98` | One named exhaustive AST-to-path regression test | A fresh interpreter/model agreement check for the fixed 128-input fixture |
| `solver-103` | Four isolated worker/solver tests | Bound worker outcomes on this host; deadline observations are non-portable |
| `atomic-118` | Seven model/independent global-order tests | Rechecked finite enumeration and interleaving-oracle counts |
| `fake-checker-29` | Fifteen fake executable/logos-runner tests | Fail-closed adapter behavior; **no trusted proof certificate checked** |
| `binding-rt11` | Synthetic C benchmark, twelve action-count phases and unsafe verification-key witness | Cross-platform action-count result with runner compiler; not an original Apple Clang comparison |

**Commands and exact inputs:** embedded, without interpolated caller arguments, in [the workflow](../.github/workflows/research-historical-rechecks.yml), which is the authoritative executable recipe for this report. Each job exposes its historical Git HEAD and source blob and uploads a per-case artifact with environment and test/benchmark output. The direct local equivalent is to check out each [manifest](quality-audit/2026-11-23-publication-provenance.json) commit in a fresh directory and run the corresponding report's documented command with Python 3.12.14 (plus pinned SymPy for Scenario 103). Expected suite counts are 1, 4, 7, 15, and 12 benchmark phases respectively. Any test mismatch is recorded as a negative result, not silently treated as a pass.

**CI result:** *pending; see the PR's GitHub Actions*. The workflow is non-required and is evidence collection rather than an adopted semantic gate. No passing run is claimed here prior to a completed GitHub Actions result.

## Evidence classification, negative results, and decision boundary

- **Published-source provenance:** recovered for eight reports as complete Git commit/tree identifiers. This resolves only the *locating source code* aspect of prior baseline warnings.
- **Original run provenance:** **unverified in all eight**. Historical command output, original CI job identifiers, or a full working-tree patch are needed to claim the exact run; a new CI run is evidence for a new run.
- **Independent experiment rechecks:** only selected finite tests/benchmark at historical *publication* commits, with new machine/toolchain metadata; broader original claims remain their authors' unvalidated results unless the CI evidence independently reproduces those exact outcomes.
- **Source-only evidence:** RT-04 at initial publication and Scenario 134 are correctly classified as comparative/documentary; do not require executable commands or forge a production benchmark.
- **Negative/non-decision:** first RT-04 report predates RT-04-01; Scenario 29 has no cvc5/Logos proof; Scenario 103 UNSAT cannot prune without a checked certificate; Scenario 118 lacks independent weak-memory model check; Scenario 133 needs Rust environment matching before a clean compiler-to-native result.
- **Draft impact:** none. These source identities and bounded tests do not select a language policy or authorize a candidate specification change.

## Follow-up review gates

1. Record exact outputs and CI run IDs of all five jobs (including failures and environment differences); never mark the historical run attested solely because a fresh test passes.
2. For the eight baseline warnings, add honest source-provenance pointers to the affected reports or track them here, distinguishing committed publication snapshot from historical execution snapshot.
3. Resolve the other nine documented traceability/method/question gaps in [issue #285](https://github.com/aivibeflow/LLMLang/issues/285) without inventing draft decisions.
4. Obtain maintainer approval for a shared metadata/evidence-type protocol; independently review claim-level evidence, false negatives and larger representative corpus samples before enforcing gates.

**Proposed action:** Retain Q1–Q5 as warning-first research review questions. Never treat this publication history as evidence that `research/` contents are normative or that Stage 0.2 is complete.
