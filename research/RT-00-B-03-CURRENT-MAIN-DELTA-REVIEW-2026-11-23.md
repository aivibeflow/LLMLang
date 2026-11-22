# RT-00 B-03 — Current-main cross-cutting semantic consistency delta

**Date:** 2026-11-23  
**Repository:** `aivibeflow/LLMLang`  
**Current main baseline:** `d63ff8c851c0f3520ebe2bc67c772667b717f757`  
**Previous B-03 audit baseline:** `bd6daf5fb2ebfdc384eb00c46a81df3b84be11dc`  
**Previous B-03 report:** [RT-00-B-03-CROSS-CUTTING-SEMANTIC-CONSISTENCY-AUDIT-2026-11-21.md](RT-00-B-03-CROSS-CUTTING-SEMANTIC-CONSISTENCY-AUDIT-2026-11-21.md)  
**Disposition:** bounded current-main delta review. No new direct semantic contradiction was established. Several status statements require supersession, while the main cross-cutting design boundaries remain unresolved.

## 1. Scope and method

This is a delta review, not a replacement for the 2026-11-21 B-03 baseline audit and not a fresh reread of every RT document. The previous B-03 baseline `bd6daf5` is two commits after PR #121's merge commit `e4251f6`; it already contains PR #120's RT-26 taxonomy/dependency expansion and PR #121's SCW-30 declaration-closure proof. The current-main delta reviewed here adds later evidence from RT-26 prototype work and the scoped MCP object-format decision in PR #237.

The review checks:
- actual merged PR diffs and commit ancestry;
- current taxonomy, dependency map, PLAN, Scenario 34, RT-19 and ADR-017;
- exact source identity for the RT-26 prototype files relative to their reproduction commit;
- the Required CI run for the PR #121 Lean proof pipeline;
- current cross-cutting identity, contract, dependency/cache, backend, package, resource, and authorization boundaries.

Historical reports remain pinned to their stated revisions. A finding is not rewritten merely because a later state changes.

## 2. PR #120 and #121 — already included in the prior B-03 baseline

### 2.1 PR #120 — RT-26 registration

PR #120 merged as `134accb0d65c8a253cdd5af098d5777f985a5a2f`. It:
- registered RT-26 as the 26th RT area;
- added DEP-100 through DEP-108, bringing the detailed dependency register to 108 edges;
- added the RT-26 taxonomy row;
- added RT-26 research obligations to PLAN stages 5 and 7.

The prior B-03 baseline `bd6daf5` is after this merge. Its 26-RT / 108-DEP scope therefore already includes RT-26. Current taxonomy, dependency map, and PLAN remain structurally consistent at 26 RT areas and 108 DEP edges. The nine RT-26 edges are research dependency hypotheses, not proof that their relationships or enforcement obligations have been validated.

**Current status issue:** the RT-26 taxonomy row and the RT-26 parent document still describe the mandatory research as “not started.” That wording is no longer accurate for the entire RT-26 area because later mainline changes added two bounded prototype studies and a reproduced test run. It remains accurate that the broad research program is incomplete.

### 2.2 PR #121 — SCW-30 declaration closure

PR #121 merged as `e4251f6c88219f35e6df59d889c3af4016b1ef2c`, and is also included in the previous B-03 baseline.

The merged change adds `SolverRelationalQuery.lean` and `ProgramRelationalQueryTests.lean`, updates the Lean package roots, exposes source-binding lookup, and changes Scenario 34/PLAN status. The proof establishes, for the admitted lowered relational-query fragment, that:
- every symbol occurrence in the solver-facing formula is covered by the declared binding set;
- the binding name is unique;
- the declared sort agrees with the source binding;
- the resolved binding retains the original source declaration/role.

The two current-main files have the same Git blob identities as at PR #121's merge commit. Required CI run [#44897171334](https://github.com/aivibeflow/LLMLang/actions/runs/44897171334) passed, including the `logos-binding / lean-build-and-test` job. That job installed Lean 4.36.0, built 63 targets with warnings treated as errors, and ran the executable test entry point successfully. `ProgramRelationalQueryTests.lean` is included in the Lake roots, so its proof examples are compiled as part of the build.

**Status correction:** the older B-02b.1 report is pinned to the pre-PR-121 revision and its statement that SCW-30 remains open is historical, not current. Current Scenario 34 and PLAN mark SCW-30 complete.

**Boundary:** SCW-30 is solver-facing declaration closure. It does not establish the complete source → canonical JSON → Logos AST → CPC assumptions → external solver chain. Scenario 34 continues to leave the broader SCW-31–34 correspondence/trust boundary open. PLAN's completed SCW-31 envelope slice is narrower than the full SCW-31 requirement; it must not be treated as closing the whole chain.

## 3. RT-26 — later bounded prototype evidence

After the previous B-03 baseline, commit `00857e7dee48d0026e6d47c776c8792f6f1f245d` added the cancellation and cumulative-reservation prototype studies and a dedicated reproduction workflow. It is 38 commits after the prior B-03 baseline.

The current-main Git blob identities of both test modules are identical to those at the reproduction commit:
- `test_budget_cancellation.py`: `60ff8c3886ca36acce4809d6f4742c212e44c732`;
- `test_budget_reservation.py`: `ad432a046427586834c5f7a22646dd3e15235758`.

Reproduction run [#44949563913](https://github.com/aivibeflow/LLMLang/actions/runs/44949563913) executed:
- 3 cancellation-settlement tests;
- 4 cumulative-reservation tests;
- Ubuntu 24.04 with CPython 3.12.14.

The reservation model compares separate checks with serialized hierarchical reservation. The report records overshoot in four of six separate-check schedules and agreement with direct subtree accounting over 4,320 serialized-ledger transitions. The cancellation model closes new admission immediately and settles already-admitted work before releasing reserved capacity.

**What this evidence supports:** a bounded cooperative ledger model for cumulative hierarchical reservation, cancellation admission closure, and terminal settlement.

**What it does not support:** accurate memory/CPU/disk/network metering, coroutine/task-switch accounting, hardware/software performance-counter attribution, throttling latency, real-time enforcement, OS/container hard limits, concurrent durable multi-process accounting, distributed crash recovery, or production resource-handler correctness.

The RT-26 parent document and taxonomy still say “not started.” The current status should be represented as **in progress — bounded cooperative reservation/cancellation evidence reproduced; broad accounting and enforcement research remains open**. PLAN stage 5 already records the bounded evidence; the mandatory Stage 7 research item correctly remains unchecked.

The nine DEP-100–108 relations remain hypotheses. The prototype results do not validate all nine edges or establish the authority model required to enforce them. The bounded RT-26 claim/test/run chain is also documented in B5 §10–11.3 and the B6 unresolved register; this delta reconciles its current cross-cutting status rather than repeating those audits.

## 4. PR #237 — accepted but narrowly scoped MCP object format

PR #237 merged as current-main commit `09db9b75f7ee928285fcfd8005f62ad1513202e7`. It changes ADR-015, adds ADR-017, and updates RT-19.

ADR-017 accepts JSON as the default representation for SPG objects exchanged with agents through MCP:
- one independently addressable graph object is represented by one JSON value;
- nested fields and arrays remain inside that value;
- references between independently addressable objects use SPG IDs.

The ADR explicitly does **not** decide:
- the canonical Git repository representation;
- the on-disk or in-memory storage format;
- a canonicalization profile or exact canonical bytes;
- a Content Hash algorithm, domain separation, or hash envelope;
- the complete SPG schema or all graph import/admission rules.

ADR-015 remains Proposed. RT-19's general Toolchain Server architecture and broader wire contract remain research proposals; its current text correctly distinguishes the accepted MCP-facing format from unresolved repository serialization.

**Consistency assessment:** ADR-017 does not conflict with the B-03 identity/hash findings or the RT-05/RT-24 candidate models because it deliberately stops before canonical repository bytes and hash identity. It must not be generalized into a decision that JSON is the canonical Git representation. In particular, it does not settle the separate repository-storage comparison of JSON and YSON.

## 5. Current cross-cutting status matrix

| Cross-cutting domain | Current evidence/state | Remaining boundary |
|---|---|---|
| Semantic identity and hashes | RT-05/RT-24 remain candidate models; ADR-017 selects only an MCP object representation | Canonical bytes, algorithm, domain separation, typed hash envelope, stable ID/slot/lineage policy remain unresolved |
| Contract identity and conformance | RT-20 separates ContractHash, OpHash, CCHash, ImplHash and evidence identity | Equality versus behavioral compatibility and implementation conformance are not proven |
| Dependency closure and cache identity | SCW-30 closes a narrow solver declaration set; semantic cache design requires exact Action Key inputs and fail-closed unknown dependencies | Global source/dependency closure and Action Key completeness remain open; SCW-30 is not a general dependency-closure proof |
| Source semantics and solver correspondence | SCW-30 complete in the restricted Lean fragment | Full SCW-31–34 source/JSON/Logos/CPC/solver correspondence remains open |
| Compiler/backend preservation | LLVM architecture remains a proposal; native and Wasm probes are bounded | No general source-to-LLVM preservation proof or backend equivalence proof |
| Package identity and trust | Package identity/index prototypes remain exploratory; hash equality and publisher trust are separate | Provider closure, provenance authentication, signatures, revocation, and trust policy remain open |
| Resource accounting | RT-26 has reproduced cooperative reservation/cancellation models | Broad attribution, enforcement, throttling, hard limits, and authority composition remain open |
| Security and authorization | RT-16 has a bounded 24-test authorization model with a single-process nonce ledger | Production credentials, signatures, persistent/concurrent nonce storage, sandboxing, and cross-layer authority composition remain open |
| MCP/API object representation | ADR-017 accepts JSON for MCP-facing SPG object exchange | Repository serialization, canonicalization, and hashing remain undecided |

## 6. New current-main findings

### B3-09 — MCP JSON decision is scoped, not a repository-format decision

**Status:** accepted narrow decision; no contradiction found.

The new ADR resolves the default MCP-facing representation only. The RT-19 general proposal, RT-05 canonical encoding, and RT-24 repository representation remain non-normative. Any document that treats ADR-017 as selecting canonical repository JSON would overstate its scope.

### B3-10 — SCW-30 is complete, but the end-to-end proof boundary remains open

**Status:** confirmed status update.

The pre-PR-121 B-02b.1 statement that SCW-30 is open is superseded by the merged proof and Required CI evidence. SCW-31–34 remain open at the broader acceptance level. Declaration closure must not be conflated with source completeness, JSON byte correspondence, CPC assumption provenance, or external checker trust.

### B3-11 — RT-26 has bounded evidence; “not started” is stale

**Status:** confirmed status mismatch.

Two reproducible prototype studies exist and the current test source is identical to the tested source. The broad RT-26 research remains incomplete. The taxonomy and parent RT-26 document should distinguish “bounded pilot evidence exists” from “full resource accounting/enforcement research complete.”

### Clarification — original B-03 finding count

The original B-03 executive summary's “seven material unresolved cross-document boundaries” plus “one important evidence limitation” is consistent with eight numbered findings: one finding is an evidence limitation rather than an additional cross-document boundary. No count defect is recorded, and the historical summary is not changed.

## 7. Findings that remain unresolved

- `ImpHash` / `ImplHash` remains explicitly unresolved. No normalization is proposed.
- Canonical hash bytes, algorithm, domain separation, and hash-envelope policy remain unselected.
- Contract equality versus behavioral compatibility remains unresolved.
- Global dependency closure and complete Action Key inputs remain unproven.
- LLVM source-to-backend preservation remains unproven.
- Package/provider trust and provenance authentication remain open.
- RT-26 enforcement and cross-layer resource/authorization authority composition remain open.
- SCW-31–34 remain open beyond the completed SCW-30 declaration-closure fragment.
- The 137 Scenario-named path versus 136 mapped Scenario-file discrepancy remains unresolved.

## 8. Required document alignment (defer to Stage F)

1. Update the RT-26 taxonomy row and parent-document status to “in progress — bounded cooperative model evidence exists; broad accounting/enforcement remains open.”
2. Preserve the historical B-02b.1 SCW-30 statement but add a current-status reference to PR #121 and this delta; do not rewrite its baseline.
3. Update the current unresolved register with B3-09 through B3-11 and preserve `ImpHash` / `ImplHash`.
4. Update PLAN/README/G and the RT-26 status references only after the B–E audits are reconciled.
5. Keep ADR-017's MCP-only scope explicit wherever JSON is discussed; do not extend it to repository serialization or canonical hashing.

## 9. Conclusion

The reviewed current-main changes do not establish a new direct semantic contradiction. They narrow the evidence boundary: SCW-30 is complete in its declared fragment; RT-26 has bounded cooperative reservation/cancellation evidence; and MCP-facing SPG object exchange now has a scoped JSON default. None of these closes global dependency completeness, full source-to-solver correspondence, general resource enforcement, canonical repository serialization, or the existing identity/hash questions.

The original B-03 report remains a valid historical baseline. This delta supersedes only the current statuses identified above. B-03's cross-cutting audit remains incomplete until the unresolved interfaces are reconciled and the Stage F document alignment is performed.
