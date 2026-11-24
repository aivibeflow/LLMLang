# RT-00 B-05-01 — Scenario 130 Claim-Level Traceability Pilot

**Date:** 2026-11-21  
**Baseline under test:** current main `b0142c27f5632a859c379b78a10cb22f500ebfd8` plus C-02 PR head `35d53b88db5a91276882467c66818a9570b5475e` for the source-identity enforcement and fresh reproduction run  
**Scope:** Scenario 130 only; local claim identifiers are scoped to this report and are not a proposed corpus-wide ID scheme.  
**Disposition:** four executable claims have source-to-test-to-evidence traces within the finite SQLite fixture. One implications claim remains conditional and not independently validated.

## 1. Why this pilot

B5 found that file-level classification does not provide claim-level traceability and that no corpus-wide stable Claim ID namespace exists. This pilot tests a narrower proposition: can the existing Scenario 130 report be decomposed into falsifiable local claims and linked to exact source, tests, execution, evidence, and PLAN stage without inferring edges from filenames?

The identifiers `S130-C01` through `S130-C05` are report-local labels only. They must not be interpreted as globally stable claim IDs.

## 2. Source and execution identity

| Item | Exact identity |
|---|---|
| Scenario report | `research/RESEARCH-SCENARIO-130-DURABLE-INVOCATION-RESULTS.md` |
| Scenario report at current main | blob `4f7ea7e07224d04eff2339afee29b4f36671118e` |
| Scenario report at C-02 run head | blob `9fdb7298597965299ab9add721e46650c798492c` (adds prospective SQLite source-ID baseline) |
| Model | `research/PROTOTYPES/RT-04-01/rt04_durable_receipts.py`, blob `9c58898e4d3b81b0fbe11aa2458596993e26924f` |
| Process probe | `research/PROTOTYPES/RT-04-01/sqlite_durable_receipts_probe.py`, blob `13b7cc7924e190778bcc4f2db8c95acf5e8b0a3c` |
| Test module | `research/PROTOTYPES/RT-04-01/test_rt04_durable_receipts.py`, blob `c70ef3cc9be36939940012d9a9db5a1cb8ca92c2` |
| Test methods | 4 methods in `DurableReceiptTests` |
| PLAN location | Stage 1, §1.4.1 (RT-04), Scenario 130 checklist entry |
| Current reproduction code/workflow | C-02 PR #164 head `35d53b88db5a91276882467c66818a9570b5475e` |

The model, probe, and test module have identical blob SHAs at current main and the C-02 reproduction head. The Scenario 130 report differs because C-02 appends a prospective exact SQLite source-ID baseline; this difference is explicitly retained rather than treated as the same report revision.

## 3. Local claim-to-evidence matrix

| Local claim | Falsifiable statement | Source location | Test / executable subject | Execution and evidence | Status and scope |
|---|---|---|---|---|---|
| S130-C01 | When effect and terminal record share one SQLite transaction, interruption before commit rolls both back; after commit, completion is recoverable even if the reply is lost | Scenario 130 §§Fixture, Recovery results; model `predict` | `test_crash_boundaries`; `test_fresh_processes_match_every_crash_boundary`; probe `finish` and `probe` | Required CI #44942585935, repository-structure job: the 4-method module discovered and passed within 364 tests. Native run #44942585953: `sqlite-durable-receipts` passed within 10/10 native commands | Supported within two publication policies × five interruption cuts on one local SQLite database |
| S130-C02 | With separate effect and terminal-record commits, interruption after the effect commit but before terminal commit yields released effect plus pending/absent terminal evidence; the reservation must remain held absent authoritative evidence | Scenario 130 §Recovery results; `predict`, `recover` | `test_crash_boundaries`; `test_absent_terminal_result_preserves_bounded_roles`; native `probe` | Same Required CI and native run as C01 | Supported within the finite two-commit fixture; not a production provider reconciliation protocol |
| S130-C03 | A successor reservation receives a greater committed generation, and prior invocation evidence does not consume the successor; lookup is bound to both generation and role pair | Scenario 130 §Recovery results; probe `reserve`, `lookup`, `probe` | `test_fresh_processes_match_every_crash_boundary` | Same Required CI and native run; probe assertions include monotonic generation, successor pending state, and role identity | Supported within one continuing SQLite database using AUTOINCREMENT and fresh worker processes |
| S130-C04 | A resettable counter can reproduce an old invocation key and cause stale consumption evidence to be accepted by the pure recovery model | Scenario 130 §Recovery results; model `recover` | `test_reset_counter_can_make_old_evidence_look_current` | Required CI #44942585935 discovered and passed this method as part of the 364-test suite | Supported as a counterexample to resettable identity; it does not establish a general distributed uniqueness scheme |
| S130-C05 | Reliable retry across independent providers requires stable identity, result retention, and an authoritative lookup or reconciliation protocol when effect and publication have separate commit boundaries | Scenario 130 §Implications for candidate comparison | No dedicated test or independent provider experiment in this slice | No evidence object directly supports this broader statement | Conditional design implication only; remains unresolved for independent providers, concurrent delivery, lost initial key, restored snapshots, and record expiry |

## 4. Exact execution evidence

### 4.1 Required CI

Run [#44942585935](https://github.com/aivibeflow/LLMLang/actions/runs/44942585935), on C-02 head `35d53b...`:

- `repository-structure / structure` passed.
- The log names all four methods in `test_rt04_durable_receipts.DurableReceiptTests`.
- The complete RT-04-01 unittest discovery completed with `Ran 364 tests` and `OK`.

The test module and model/probe blobs are byte-identical to current main. Thus the 364-test run executed the same four-method test module that is present in the current main baseline.

### 4.2 Native reproduction

Run [#44942585953](https://github.com/aivibeflow/LLMLang/actions/runs/44942585953), on the same C-02 head:

- native-reproduction job passed 10/10 commands with zero failures/skips;
- `sqlite-durable-receipts` passed;
- LLVM preservation passed 2/2 probes;
- downloaded SQLite 3.53.1 and Python 3.12.14 archives passed SHA-256 checks;
- the LLVM Debian package archive passed its pinned SHA-256 check;
- the runner recorded Python SQLite version 3.53.1 and source ID `2026-05-05 10:34:17 c88b22011a54b4f6fbd149e9f8e4de77658ce58143a1af0e3785e4e6475127e9`, with `durable_python_sqlite_matches_reproduction_baseline: true`.

Artifacts:
- native [14722660960](https://github.com/aivibeflow/LLMLang/actions/runs/44942585953/artifacts/14722660960), digest `sha256:ebf1339af3014608674bdad3f433954b6ff119dd4501dc28cadba93845af86fa`;
- LLVM [14722122244](https://github.com/aivibeflow/LLMLang/actions/runs/44942585953/artifacts/14722122244), digest `sha256:ff8cf1bcc7bf343e80c545a2be5d6ac98ab459f00ef7fb650b97c69812858101`.

The exact SQLite source ID is a prospective baseline established from a successful reproduction run. It was absent from the original Scenario 130 report; it is not retrospective proof about the original execution.

## 5. What this pilot demonstrates about traceability

This slice establishes that claim-level traces can be written without pretending that every link has the same evidence strength:

- C01–C04 have explicit report locations, source symbols/test methods, exact source blobs, actual CI execution, and a retained native reproduction artifact.
- C05 is a design implication with no dedicated independent-provider test; it remains conditional rather than inheriting the success status of C01–C04.
- A single test method can support multiple claims, and one claim can be supported by both a model test and a native process probe.
- The test source, test discovery/execution, native command result, and evidence artifact are separate nodes.
- A successful native probe does not generalize beyond its declared local SQLite fixture, runtime identity, and crash cuts.

## 6. Unresolved limitations

- No corpus-wide Claim ID namespace is proposed.
- No claim-to-test completeness statement is made for other Scenario reports or RT areas.
- The backend effect is a modeled row change, not a real external provider effect.
- Independent providers, concurrent delivery, lost initial invocation key, restored older snapshots, and terminal-record expiry remain untested.
- The prospective SQLite source-ID baseline does not reconstruct the original historical run's source identity.
- The native workflow is non-required; it must be rerun when source/toolchain inputs change.

**Disposition:** bounded claim-level traceability is demonstrated for Scenario 130 C01–C04. C05 and all corpus-wide completeness claims remain unresolved. No architecture or runtime policy is accepted by this pilot.
