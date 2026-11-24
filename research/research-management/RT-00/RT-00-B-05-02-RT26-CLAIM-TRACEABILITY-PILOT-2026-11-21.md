# RT-00 B-05-02 — RT-26 Claim-Level Traceability Pilot — 2026-11-21

**Date:** 2026-11-21  
**Baseline:** current `main` at branch creation; source files are identified by Git blob SHA below  
**Scope:** merged cooperative cumulative-budget reservation fixture only  
**Disposition:** four local claims have source/test links and a historical PR validation statement; exact execution-to-blob binding is incomplete. This is not a corpus-wide Claim ID proposal or validation of RT-26 as a whole.

## 1. Purpose and boundaries

B5 established that file-level RT classification does not imply claim-level traceability. The Scenario 130 pilot demonstrated a bounded method with report-local identifiers. This second pilot applies the same method to RT-26, where a merged cooperative reservation experiment now exists.

Identifiers `R26-C01` through `R26-C04` are local to this report. They are not globally stable claim identifiers.

The pilot covers only a fixed, acyclic task hierarchy and a cooperative cumulative budget. It does not cover instantaneous live memory, CPU or I/O sampling, OS enforcement, throttling, fairness, throughput, handler semantics, or attribution for work outside cooperative admission.

## 2. Source identity and declared execution

| Item | Identity |
|---|---|
| Research report | `research/RT-26-COOPERATIVE-BUDGET-RESERVATION.md` |
| Report blob | `2f78a3c5800aace05c8b6b950bde04be3cf9e059` |
| Test module | `research/PROTOTYPES/BUDGET-RESERVATION-01/test_budget_reservation.py` |
| Test blob on current main | `ad432a046427586834c5f7a22646dd3e15235758` |
| Test class | `BudgetReservationExperiment` |
| Declared methods | 4 |
| Reproduction command | `python -B -m unittest discover -s research/PROTOTYPES/BUDGET-RESERVATION-01 -v` |
| Declared runtime | CPython 3.12.14, standard library |
| Plan location | PLAN.md §§5.2 and 7.1; RT-26 / DEP-100–108 |

The merged PR [#129](https://github.com/aivibeflow/LLMLang/pull/129) states that four focused tests, Markdown validation, and repository-layout checks passed. In addition, the exact current-main test content identified by blob `ad432a046427586834c5f7a22646dd3e15235758` was independently executed from the fetched source in CPython 3.13.5: all four methods passed (0 failures, 0 errors). This local run verifies the current blob's behavior in CPython 3.13.5, not the report's declared CPython 3.12.14 environment. The original PR #129 execution still lacks a retained run URL/log digest bound to that blob, so historical execution provenance remains incomplete.

The separate PR [#174](https://github.com/aivibeflow/LLMLang/pull/174) explores task-scope cancellation and terminal settlement. It is branch-only in this audit snapshot and is deliberately excluded from main-baseline evidence.

## 3. Local claim-to-test matrix

| Claim | Falsifiable statement | Source/test relation | Evidence status |
|---|---|---|---|
| R26-C01 | In the two-request split check/charge fixture, four of six valid interleavings admit six units against a five-unit root budget | Report §Results BUDGET-01; `test_split_check_then_charge_overshoots_in_four_of_six_interleavings` | Test declared in current source; PR #129 reports four focused tests passed. Exact run-to-blob binding not retained |
| R26-C02 | Across all 720 orders of two reservations and four settlement attempts, incremental ancestor accounting equals an independently computed subtree sum after each of 4,320 transitions and never exceeds the fixture limits | Report §Results BUDGET-02; `test_all_linearization_orders_match_an_independent_subtree_sum` | Same bounded historical execution status; exact run-to-blob binding not retained |
| R26-C03 | Repeated reservation with identical operation inputs is idempotent; reuse with different task/amount is rejected; committed units are not refunded by late cancellation | Report §Results BUDGET-03; `test_retry_and_late_cancellation_do_not_create_or_refund_spent_units` | Same bounded historical execution status; exact run-to-blob binding not retained |
| R26-C04 | Pending cancellation releases reserved capacity; repeated settlement is stable; a denied operation remains denied and a fresh operation ID can retry | Report §Results BUDGET-03; `test_cancellation_releases_pending_units_and_denied_retry_is_stable` | Same bounded historical execution status; exact run-to-blob binding not retained |

A single test can support multiple subclaims, and the report's three BUDGET result labels do not map one-to-one to the four test methods. The mapping above is source-derived from test assertions; it does not imply independent execution evidence for each claim.

## 4. What is supported

Within the fixture and its assumptions:

- separate unsynchronized check-then-charge can overshoot;
- one serialized ancestor-path reservation transition avoids that fixture's overshoot;
- incremental ledger state agrees with the independent subtree-membership oracle across the enumerated schedules;
- duplicate reservation/settlement behavior and pending-versus-committed cancellation are explicitly tested.

The strongest supported conclusion is a property of the finite model and its specified linearization assumption. It is not evidence that a production runtime has implemented an equivalent atomic transition.

## 5. Unresolved graph edges and limitations

| Edge / question | Status | Closure evidence needed |
|---|---|---|
| Report claim → test method | Source-derived, bounded | Preserve section/symbol-level mapping in a maintained graph |
| Test method → exact executed source blob | Unresolved | Retained CI log identifying checkout SHA and test blob SHA |
| Execution → artifact digest | Unresolved | Retained machine-readable result and artifact digest |
| Cooperative model → production runtime atomicity | Unresolved | Runtime implementation and concurrency/memory-model tests |
| Cumulative budget → instantaneous memory/CPU/I/O limits | Not covered | Separate measurement and enforcement experiments |
| Cancellation → task lifetime/admission race | Not covered by this fixture | Task-scope cancellation and terminal-settlement evidence |
| Budget policy → authorization/OS hard boundary | Unresolved | Explicit authority composition and target enforcement evidence |
| RT-26 → PLAN exit criteria | Not satisfied | Coverage of required dimensions, platform limits, overshoot, handlers, and operational measurements |

The pilot does not establish a complete RT-26 evidence chain. In particular, a cumulative reservation model cannot be generalized to post-hoc CPU or I/O measurements, where usage may already have occurred before the counter is observed.

## 6. Conclusion

RT-26 is **partially validated in one cooperative cumulative-budget model**, not “not started” and not complete. The four local claims have explicit report-to-test mappings. The historical PR validation is recorded with its evidence limitation; it is not promoted to an exact reproducibility claim.

No language syntax, runtime design, allocator, enforcement mechanism, or authority policy is selected. No branch-only PR #174 result is treated as merged evidence.
