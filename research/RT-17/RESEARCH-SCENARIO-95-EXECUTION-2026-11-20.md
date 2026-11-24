# Scenario 95 Execution — Diagnostics for Humans and Coding Agents — 2026-11-20

**Research item:** Scenario 95; RT-03, RT-09, RT-14, RT-17  
**Status:** Comparative analysis executed; candidate contract and evaluation design recorded; no LLMLang diagnostic contract selected  
**Updated:** 2026-11-20  
**Baseline:** `main` as inspected on 2026-11-20  
**Method:** Cross-check the existing Scenario 95 study against current protocol/compiler documentation, the LLMLang authoring and workload boundaries, and the earlier Scenario 87 diagnostic corpus. No LLMLang compiler or language server exists in this study scope, and no human-subject or coding-agent experiment was run.

## 1. Research question

What must be separated in a diagnostic system so that compiler facts can be rendered for people, transported to editors, consumed by agents, and used to propose repairs without confusing a suggestion with authorization or correctness evidence?

This execution narrows Scenario 95 into five independently testable contracts:

1. **Diagnostic fact:** what the compiler established, at which phase, against which source/workspace snapshot, and with what uncertainty.
2. **Presentation:** how a CLI, editor, or explanation layer renders those facts for a particular audience.
3. **Transport:** how structured facts and document positions cross JSON/API and LSP boundaries.
4. **Repair proposal:** which edits are proposed, their preconditions, applicability, and validation state.
5. **Authority and acceptance:** who or what may apply, accept, commit, or publish a change.

These boundaries are related, but none is a substitute for another.

## 2. Method and inspected material

Repository material:
- Scenario 95 — the original evidence-linked comparison and proposed discriminators.
- Scenario 87 — 18 async/await parser/context/recovery fixture intentions.
- RT-01 Reference Workloads — fixed task snapshots, hidden checks, independent review, and separate correctness/usability/cost measures.
- RT-01/14/17 Workload and Agent Evaluation preparation brief.
- ADR-015 — proposed Toolchain API, immutable snapshots, Change Sets, provenance, expected-hash preconditions, and authority enforced outside the model.
- Research taxonomy and dependency map — RT-14/RT-17 scope and their links to compiler, semantics, and security.

External prior art checked:
- Rust compiler diagnostic structure, message guidance, structured suggestions, applicability classes, and UI tests.
- LSP 3.18 as the editor transport boundary, with position encoding negotiation introduced in 3.17.
- TypeScript Language Service's on-demand phase queries, document snapshots, and incremental parsing.
- Elm's error-message catalog as a corpus-maintenance pattern.
- The 2024 within-subjects study of 106 novice programmers comparing stock compiler messages, expert-written explanations, and GPT-4 explanations.

This is a source-based comparative review. It did not rerun upstream tests, verify every linked human-subject study, or measure LLMLang performance.

## 3. Findings

### 3.1 The compiler diagnostic must be the source of truth

Rust demonstrates that one diagnostic can contain a severity, optional code, message, primary and secondary spans, labels, notes/help, and structured suggestions. Its guidance also distinguishes concise primary messages from explanatory notes and help. This is a useful precedent for separating the diagnostic fact from its terminal rendering.

A stable diagnostic code and a diagnostic occurrence are different concepts:
- a **code** names a diagnostic category or rule and may have a compatibility policy;
- an **occurrence** is one report at a particular source/workspace snapshot and location;
- rendered prose is presentation and must not be used as a machine key.

Do not infer that a code uniquely identifies an occurrence, that identical prose means identical semantics, or that a changed message means the underlying diagnostic category changed.

### 3.2 LSP is a transport, not the authoritative compiler model

LSP 3.18 provides editor-facing diagnostic ranges, severity, message, optional code/code description, source, tags, related information, and extension data. It is suitable as an adapter boundary, but it does not define the compiler's complete diagnostic lifecycle, cross-file semantic identity, CLI/JSON compatibility, repair authority, or LLMLang's causal model.

LSP positions are not intrinsically byte offsets or Unicode scalar indices. Since 3.17, client and server negotiate UTF-8, UTF-16, or UTF-32 position encoding; UTF-16 remains the mandatory fallback/default. An implementation must not silently treat a negotiated LSP character offset as an internal source byte offset. This makes Unicode position conversion a conformance test, not a cosmetic rendering detail.

### 3.3 Incremental diagnostics require snapshot discipline

TypeScript's Language Service illustrates on-demand phase queries: syntactic diagnostics can be obtained without forcing semantic checking, and file snapshots/change ranges support incremental parsing. This is evidence for separating phase cost and update lifecycle, not proof that a particular LLMLang compiler architecture is optimal.

A diagnostic computed for document version N must not be published as current after version N+1 has superseded it. Cross-file analysis also needs an analysis/workspace snapshot identity: a file version alone does not identify the dependency state used by a semantic result.

Cancellation, replacement, clearing, stale-result rejection, and incomplete analysis must be explicit. An interrupted or partial analysis must not be rendered as a complete clean result.

### 3.4 Repair applicability, correctness, and authority are separate

Rust's applicability vocabulary distinguishes mechanically applicable suggestions from suggestions with placeholders, possible mistakes, or unspecified confidence. The useful lesson is that suggestions are structured data, not prose scraped from a message.

However, at least three independent questions remain:
- **Mechanical applicability:** can these edits be applied to the declared source version without ambiguous/overlapping edits?
- **Semantic correctness:** does the resulting change satisfy the requested behavior and preserve required behavior?
- **Authority:** is this actor permitted to modify or accept the workspace?

A high applicability label cannot prove the user's intent, hidden-test success, scope discipline, or authorization. In LLMLang, proposed edits should be applied to an isolated Change Set or test copy, validated against explicit preconditions, and checked before any accepted snapshot or repository state changes. This is consistent with ADR-015's proposed separation of Change Sets, immutable snapshots, validation, acceptance, and publication; ADR-015 remains Proposed.

### 3.5 Better explanations do not establish better agent repairs

The 2024 study *Not the Silver Bullet* used 106 novice participants fixing six C programs. GPT-4 explanations beat stock compiler messages on time-to-fix in only one of six tasks; expert-written explanations outperformed both on objective and subjective measures. Another study with different participants/tasks has reported different outcomes, so these results should not be collapsed into a universal claim.

Neither result establishes autonomous coding-agent repair quality. Agent evaluation must score behavior and regression tests, unrelated edits, unsafe workarounds, attempts, time/tokens, and human intervention—not message preference or explanation fluency alone.

### 3.6 Scenario 87 and Scenario 95 have complementary responsibilities

Scenario 87 already proposes 18 async/await syntax/context fixtures with stage, span, and recovery expectations. Scenario 95 should not duplicate that syntax corpus. Instead:
- Scenario 87 supplies concrete parser/context examples.
- Scenario 95 defines how those and other compiler failures are represented, transported, grouped, updated, explained, and repaired.
- A shared fixture can have both a semantic acceptance oracle (Scenario 87) and a diagnostic-contract oracle (Scenario 95).

## 4. Candidate diagnostic envelope

The following is a **research candidate**, not an accepted schema. It separates required semantics from optional renderer-specific data.

| Area | Candidate information | Reason |
|---|---|---|
| Envelope | schema version; producer/tool version; workspace or analysis snapshot ID | Enables compatibility and provenance checks. |
| Document binding | canonical document URI/identity; document version or immutable source snapshot | Prevents stale locations and repairs from being applied to changed text. |
| Diagnostic category | optional stable diagnostic code; severity; compiler phase | Keeps machine classification independent of prose. |
| Location | primary source range; zero or more related ranges with roles/labels; source-map origin | Supports primary cause, declarations, macro/generated source, and cross-file context. |
| Explanation | concise summary; optional notes/help/details; localization/presentation metadata | Allows multiple renderers without changing machine meaning. |
| Causal structure | optional cause/group relation; explicit unknown/ambiguous state | Prevents cascaded symptoms from being presented as proven independent root causes. |
| Analysis state | complete, partial, cancelled, or unknown; relevant phase/snapshot | A partial result must not imply that no further diagnostics exist. |
| Extensions | namespaced optional data with forward-compatible handling | Allows editor-specific data without making it authoritative compiler semantics. |

Do not use rendered text, array order, or an editor-specific range as a durable semantic identity. A stable occurrence identifier may be useful for update/deduplication, but its derivation and lifetime remain an open design question.

### Coordinate recommendation to evaluate

Keep compiler-internal source locations in one canonical representation tied to an immutable source snapshot (candidate: half-open UTF-8 byte ranges). Convert at the transport boundary to the negotiated LSP encoding. Test UTF-8, UTF-16, and UTF-32 mappings with non-ASCII text, supplementary-plane characters, combining marks, CRLF, and edits before/inside a diagnostic range. This is a candidate implementation strategy, not a decision about LLMLang's canonical source representation.

## 5. Candidate repair-action envelope

Repair actions should be separate objects linked to a diagnostic, not executable side effects of receiving a diagnostic.

| Field | Candidate meaning |
|---|---|
| action ID and kind | Stable within a result snapshot; quick fix, refactor, explanation-only, or other declared action |
| target snapshot | Exact document/workspace snapshot against which the action was computed |
| edits | One or more URI/range/replacement operations, including all files touched |
| preconditions | Expected document versions/content hashes and any semantic preconditions |
| applicability | Machine-applicable, placeholders, maybe incorrect, or unknown; do not collapse this into correctness |
| validation | Not run, rejected, passed, failed, or unknown, with evidence pointers |
| scope | Exact files/entities affected and any declared exclusions |
| provenance | Compiler-generated, tool-generated, agent-authored, or human-authored proposal |

No action should silently write to the user's accepted workspace. A stale precondition, overlapping ambiguous edits, unknown scope, or failed validation must prevent the action from being treated as accepted. The policy for automatically applying a purely mechanical edit is intentionally left open.

## 6. Discriminating test corpus

The next implementation-ready corpus should combine Scenario 87's AWAIT cases with these diagnostic-level cases:

| ID | Fixture | Required observation |
|---|---|---|
| DIAG-001 | One parse error followed by a valid declaration | Primary parse diagnostic and recovery point; later declaration remains discoverable. |
| DIAG-002 | One root type mismatch producing several downstream errors | Root/cascade relation is explicit or marked unknown; duplicate symptom suppression is deterministic. |
| DIAG-003 | Use-site mismatch caused by a declaration or generic constraint elsewhere | Primary and related spans identify their distinct roles and source documents. |
| DIAG-004 | Same diagnostic through CLI, JSON, and LSP | Machine fields remain equivalent; only renderer-specific presentation differs. |
| DIAG-005 | Unicode before and inside the primary span | Internal-to-LSP conversion is correct for negotiated UTF-8/16/32 and fallback UTF-16. |
| DIAG-006 | Edit a document while an earlier analysis is running | Result for the superseded version is discarded or explicitly marked stale. |
| DIAG-007 | Cross-file semantic diagnostic after dependency change | Analysis snapshot reflects the changed dependency; unaffected-file diagnostics are invalidated/recomputed correctly. |
| DIAG-008 | Multi-file repair action with overlapping edits | Conflicts are rejected or resolved explicitly; no partial silent application. |
| DIAG-009 | Repair action computed against an old content hash | Stale precondition prevents application. |
| DIAG-010 | Plausible repair that suppresses a check or weakens a guard | It fails semantic/hidden regression checks even if it compiles. |
| DIAG-011 | Cancellation or resource limit during semantic analysis | Output is partial/cancelled/unknown, never a false clean result. |
| DIAG-012 | Unknown future diagnostic field/code extension | Consumer preserves or safely ignores optional data; no crash or invented semantics. |

For each fixture, record the expected diagnostic category, phase, primary/related spans, causal status, snapshot binding, recovery behavior, available actions, and validation oracle. Keep exact human wording snapshots separate from structural conformance tests.

## 7. Human and agent evaluation protocol

A later empirical study should use the RT-01 controls and preregister separate human and agent strata.

**Arms to compare:**
1. baseline compiler output;
2. structured diagnostic rendered tersely;
3. expert-authored expanded explanation;
4. LLM-generated explanation, clearly labelled as generated;
5. optional repair proposal, isolated from the explanation effect.

Hold source, task, checks, starting snapshot, permitted tools, and time/token budgets constant. Randomize order where possible. Do not conflate explanation and repair generation in the same arm if the aim is to identify which caused an effect.

**Primary outcomes:**
- correct task completion against hidden behavior and regression checks;
- regression rate and unrelated/out-of-scope changes;
- unsafe workaround rate (for example, disabling checks or weakening guards);
- successful repair validation and stale-action rejection.

**Secondary outcomes:**
- time, attempts, tokens, compiler invocations, and tool calls;
- root-cause identification and confidence calibration;
- human review time and agreement;
- abandonment, human intervention, and cost per accepted change.

Report novice and professional humans separately; report each agent/model/tool version separately. Publish the task set, scoring oracle, failed/abandoned attempts, and raw aggregate data. Do not rank candidate interfaces using one opaque score or hide unknown dimensions.

No participant or agent evaluation was conducted in this execution. The protocol above is a proposed follow-up, not a result.

## 8. Decision matrix

| Dimension | Evidence-supported conclusion | Remaining decision |
|---|---|---|
| Canonical representation | Structured diagnostic facts are more reusable than scraping renderer prose; compiler model and renderers should be separable. | Exact fields, schema evolution, stable code/occurrence identity. |
| Human presentation | Concise primary message plus optional details is supported by compiler practice; message quality matters but study effects are population/task dependent. | Wording, localization, detail defaults, explanation provider. |
| Editor transport | LSP is a practical interoperable adapter; coordinate encoding must be negotiated and mapped. | Whether JSON/API is also first-class; pull vs push lifecycle; capability fallback. |
| Incremental lifecycle | Snapshot/version binding and phase separation are required to avoid stale or needlessly expensive reports. | Workspace snapshot identity, invalidation, ordering, cancellation semantics. |
| Causal diagnostics | Primary/secondary locations and related information are useful; cascades need explicit handling. | Root/cause graph semantics and behavior when uncertain. |
| Repair | Suggestions should be structured and preconditioned; applicability is not semantic correctness. | Automatic application policy, proof/test requirements, repair provenance. |
| Authority | Agent proposal and accepted change are different lifecycle states. | Exact authorization/approval policy and trust model. |
| Evaluation | Human message preference cannot substitute for agent repair correctness. | Workload selection, sample size, participant recruitment, agent benchmark execution. |

## 9. Recommendations and explicit non-decisions

Recommendations for the next design/prototype iteration:

1. Treat a structured diagnostic envelope as the source of truth; make CLI, JSON, and LSP renderers/adapters consume it.
2. Bind every diagnostic to document and analysis snapshots; represent partial/cancelled/unknown analysis explicitly.
3. Keep stable diagnostic codes, occurrence identity, and message text separate.
4. Keep repair actions separate from diagnostics, with exact snapshot preconditions and complete edit sets.
5. Track mechanical applicability, semantic validation, and authority as separate states.
6. Test Unicode mapping and stale-result handling before considering an editor integration conformant.
7. Reuse Scenario 87 parser fixtures and RT-01 task controls; do not create a second disconnected acceptance corpus.
8. Evaluate agent repair by behavior, regressions, scope, and review effort—not by explanation preference.

These are recommendations, not accepted project policy. This execution does **not** select a diagnostic schema, code stability policy, coordinate representation, renderer, LSP lifecycle, repair authority, automatic-apply rule, or LLM explanation mechanism.

## 10. Quality-gate assessment

Assessment uses the proposed Q1–Q5 vocabulary from the Scenario 0.2 study. That vocabulary is not yet accepted project policy.

| Gate | Result | Reason |
|---|---|---|
| Q1 Traceable | Pass | Research item, repository artifacts, upstream sources, and affected RT areas are named. |
| Q2 Method inspectable | Pass with limits | Source-review method and scope are recorded; no LLMLang executable experiment was possible. |
| Q3 Claims evidence-labelled | Pass | Protocol/compiler facts, study observations, recommendations, and non-decisions are separated. |
| Q4 Adversarial coverage | Partial | Stale results, Unicode, cascades, malformed/unknown data, unsafe fixes, cancellation, and overlapping edits are specified; fixtures were not executed. |
| Q5 Decision-safe | Pass | No research recommendation is represented as accepted language or architecture policy. |

## 11. Sources

- Rust Compiler Development Guide, [Errors and lints](https://rustc-dev-guide.rust-lang.org/diagnostics.html), [UI tests](https://rustc-dev-guide.rust-lang.org/tests/ui.html), and [Applicability](https://doc.rust-lang.org/stable/nightly-rustc/rustc_lint_defs/enum.Applicability.html).
- Microsoft, [Language Server Protocol 3.18 specification](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.18/specification/).
- Microsoft TypeScript Wiki, [Using the Language Service API](https://github.com/microsoft/TypeScript/wiki/using-the-language-service-api) and [Using the Compiler API](https://github.com/microsoft/TypeScript/wiki/Using-the-Compiler-API).
- Elm, [Error Message Catalog](https://github.com/elm/error-message-catalog).
- Santos and Becker, [Not the Silver Bullet: LLM-enhanced Programming Error Messages are Ineffective in Practice](https://doi.org/10.1145/3689535.3689554), UKICER 2024; 106 novice participants, six C debugging tasks.
- LLMLang [Scenario 87](../RT-31/RESEARCH-SCENARIO-87-ASYNC-AWAIT-PARSER-DIAGNOSTIC-CORPUS.md), [RT-01 Reference Workloads](../RT-01/RT-01-REFERENCE-WORKLOADS.md), [ADR-015](../../docs/adr/015-toolchain-server-semantic-api.md), and [Research Quality and Decision Rules](../RESEARCH-QUALITY-AND-DECISION-RULES-2026-11-20.md).

---

**Conclusion:** Scenario 95 now has an executed comparative synthesis, a candidate diagnostic/repair boundary, 12 diagnostic-level discriminators, and a controlled evaluation protocol. It establishes neither an LLMLang implementation result nor human/agent performance. The research item is therefore **partially researched**, not complete; the next substantive gate is implementation of the structural fixtures and, separately, a preregistered human/agent evaluation.
