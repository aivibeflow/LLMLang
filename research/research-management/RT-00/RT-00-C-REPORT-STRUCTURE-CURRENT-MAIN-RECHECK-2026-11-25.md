# RT-00 C — Current-main report structure recheck — 2026-11-25

**Research item:** PLAN §0.2 — use a consistent research structure
**Baseline:** `main` at `394b256670919c191173af2828b8d9852a1ceb9d`
**Evidence type:** bounded content crosswalk of three newly merged comparative reports
**Status:** selected-report review; no template or project policy adopted

## Question and method

Do the newest LLMLang implementation studies provide the minimum information in the proposed research schema when their evidence types differ? I compared the proposed structure (problem, hypotheses, prior art, alternatives, formal model, experiments, results, limitations, decision, and draft impact) with the current-main RT-23 indexed-journal study, RT-13 LLVM conversion study, and RT-07 Dafny foreign-boundary study. I mapped information by content, including each report's committed machine-readable evidence, not by exact heading names.

## Structural crosswalk

| Information | RT-23 indexed journal | RT-13 F64→I64 lowering | RT-07 Dafny foreign boundary |
|---|---|---|---|
| Problem and scope | Opening scenario explains lost publication response and retry ambiguity; scope is bounded to a 64-entry journal and pinned generations. | Opening paragraph states the checked-conversion/poison problem and candidate validator question; exact `{tag,value}` fixture defines scope. | Opening paragraph frames proved source contract versus foreign implementation/ABI; mathematical table lookup defines scope. |
| Hypotheses or explicit question | Question is inferable from scenario and comparison, but no labeled hypothesis/question field. | Research question is inferable from opening paragraph; no labeled hypothesis field. | Problem is clear from opening paragraph; no labeled hypothesis field. |
| Prior art and alternatives | Links prior single-ref journal study; compares full scan, eight-entry window and indexed tree. | Links native conversion policy and LLVM reference; compares bit guard, ordered operations and saturation routes with negative controls. | Links Dafny transfer analysis and seL4 lookup comparison; compares verified local code, assumed extern contract and distinct C providers/ABI interpretation. |
| Model and assumptions | Defines receipt key, pinned head, first-parent history, CAS and append-only index invariant; this is a protocol model, not a separate formal specification. | Defines input/output tags, zero-on-failure value, poison behavior and exact LLVM fragment/validator model. | Gives mathematical `Expected`, bounded unsigned `Word`, postcondition, extern declaration assumption and typed ABI boundary. |
| Experiment and reproducibility | Disposable repositories, two ref backends, 64 records, before/after CAS probes, clean-clone replay, exact command, tool versions and JSON ledger. | Exact LLVM functions, Vellvm/Alive2 and native observations; tool/build pins, command, input corpus and JSON ledger. | Dafny with two bundled Z3 versions, generated caller, native C controls, pinned release hash, command and JSON ledger. |
| Results and negative cases | Full scan and index agree on 11 cases; bounded scan returns `history-window-exhausted` in eight. Object-read cost is distinguished from elapsed time. | Three checked routes refine at O0/O3; plain saturation has 63 native mismatches; validator reports saturation unsupported; deliberate poison controls are refuted. | Conditional verifier results and foreign-assumption warnings are separated; dropped guard and three incorrect C/ABI controls yield observed failures. |
| Limitations and decision boundary | States append-only/retention and current-head requirements; no process-interruption claim for the indexed layout and no route selected. | Limits results to pinned IR/model, x86-64 and tested FP conditions; no source-to-IR theorem or saturation proof; no backend selected. | States conditional proof versus unproved provider conformance; no hardware/kernel claim and no trust policy selected. |
| Draft impact and claim IDs | No direct draft change or stable per-claim IDs in the report. | No direct draft change or stable per-claim IDs in the report. | No direct draft change or stable per-claim IDs in the report. |

The three reports all preserve the core comparison chain: concrete candidate or model, method, result, limitation, and what the result cannot decide. They differ in how explicitly they name the research question and model. Each includes negative or unsupported outcomes instead of converting them to a general decision. Their exact commands and evidence ledgers make the scoped results inspectable.

## Implication for the proposed schema

These reports do not justify a rigid heading template. The most useful gap is a compact, uniform metadata and decision-boundary block, with an explicit `draft impact: none` when no draft change is proposed. A stable claim-ID register remains useful when a report supports architecture adoption or a draft change; its absence here is a traceability gap, not evidence that the reports' experiments are invalid. Formal models should be evidence-specific: a protocol invariant, LLVM input/output semantics, and mathematical Dafny postcondition are not interchangeable fields.

This is a three-report sample, not a corpus-wide audit. It supports the local observation that new high-impact studies can use different section layouts while still making their comparison reviewable. Older scenarios, prototype reports, claim-level falsifiers, global claim IDs, and future draft-change mapping remain open. No schema is accepted by this review.

## Sources and scope

- [Proposed Research Quality and Decision Rules](../RESEARCH-QUALITY-AND-DECISION-RULES-2026-11-20.md).
- [RT-23 indexed-journal recovery](../../toolchain-and-collaboration/RT-23/RT-23-INDEXED-JOURNAL-RECOVERY-2026-11-25.md).
- [RT-13 LLVM F64-to-I64 lowering](../../compiler-and-translation/RT-13/RT-13-LLVM-F64-I64-LOWERING-2026-11-25.md).
- [RT-07 Dafny kernel-style foreign boundary](../../formal-verification/RT-07/RT-07-DAFNY-KERNEL-FOREIGN-BOUNDARY-2026-11-25.md).
- Prior [five-report structure recheck](RT-00-REPORT-STRUCTURE-RECHECK-2026-11-24.md).

**Conclusion:** the selected reports contain the core information needed to compare their scoped options, despite different layouts. Uniform question/status, stable claim IDs and explicit draft-impact fields remain uneven. Keep Stage 0.2 open pending corpus coverage, independent review and maintainer adoption.
