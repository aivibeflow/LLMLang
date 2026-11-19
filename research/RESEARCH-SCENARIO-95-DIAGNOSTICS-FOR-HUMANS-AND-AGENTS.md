# Scenario 95 — Diagnostics for Humans and Coding Agents

**Status:** Evidence-linked comparison and study design; no diagnostic contract selected
**Research areas:** RT-03 semantics, RT-09 compiler, RT-14 AI authoring, RT-17 developer experience
**Updated:** 2026-11-19

## 1. Question and scope

How should LLMLang report a compile-time problem so that a human can understand and fix it, an editor can locate and present it, and an automated agent can consume it without scraping prose or making unsafe edits? This is not one message-writing problem. It spans diagnostic identity and severity, source locations, causal relationships, explanations, repairs, incremental publication, and evidence that a repair is correct.

Scenario 87 proposes async syntax/context fixtures and stage classification, but does not establish a reusable diagnostic data model, runtime/LSP contract, diagnostic quality corpus, or empirical usefulness for coding agents. This scenario complements it; it does not select language grammar, compiler architecture, or UI.

## 2. Evidence classes and limits

- **Protocol/API evidence** establishes what structured fields editors and tools can transport. It does not establish that the fields are consistently populated or understandable.
- **Compiler engineering evidence** records implemented patterns and test mechanisms. A mature implementation is prior art, not evidence that its choices optimize LLMLang.
- **Human-subject evidence** estimates effects for a named population, task, message set, and environment. It cannot automatically be generalized to professional developers or code agents.
- **Agent evidence** must test repair outcomes under realistic repository/task conditions. Human readability, preference, or a syntactically plausible suggestion is not a proxy for a correct agent patch.

## 3. Prior-art comparison

| Source/system | Diagnostic design supported by source | What it does not establish |
|---|---|---|
| Rust compiler diagnostic engineering guide | A diagnostic can carry severity, optional stable code, primary/secondary spans, labels, sub-diagnostics, notes/help, and structured source edits. Suggestions have applicability classes (`MachineApplicable`, `HasPlaceholders`, `MaybeIncorrect`, `Unspecified`). The same suggestion model can render terminal output or JSON for tools such as rustfix. Rust UI tests annotate expected diagnostics in source and can apply rustfix suggestions and compile the result. | Applicability is a producer claim, not proof a repair preserves intent. JSON and snapshots do not measure human/agent task success. Diagnostic text and code stability are different compatibility decisions. |
| Language Server Protocol (LSP) 3.18 and VS Code diagnostic API | LSP provides a cross-editor transport. Its diagnostic type has range, severity, message, optional code and code description, source, tags, related information, and optional data that can be preserved for later code-action resolution. VS Code exposes corresponding editor-facing fields such as range, severity, message, code, source, tags, and related information. This permits a compiler's model to be adapted to editor affordances. | An editor protocol does not define LLMLang's authoritative diagnostic identity, CLI serialization, repair safety, causal graph, or stable compatibility policy. Optional client capabilities and tool-specific presentation require graceful fallback. |
| TypeScript language service | It separates syntactic and semantic diagnostics and supports on-demand, per-file queries. Its documentation explicitly motivates doing only the work needed for a query and allowing the host to avoid rechecking unchanged files. | Incremental responsiveness is a service architecture result, not an evaluation of explanation quality. Per-file queries may omit cross-file context unless the language service requests it. |
| Elm error-message catalog | The compiler project maintains a collection of small broken programs intended to trigger compiler errors and provide data for systematic improvement. This is a practical corpus-building pattern, including examples of messages that commonly confuse users. | The repository itself is not a controlled assessment and does not show that all errors are covered, that fixes are correct, or that a catalog automatically provides stable machine-readable output. |
| Human-facing message studies | A randomized study with more than 700 novice participants reported faster debugging and higher perceived usefulness for a particular set of readable, concise messages with resolution hints versus standard messages. A separate 2024 within-subjects study of 106 novices found GPT-4-generated explanations faster than stock messages in only one of six tasks; expert-written explanations outperformed both stock and GPT-generated messages on objective and subjective outcomes. | These results are not contradictory: populations, tasks, messages, controls, and interventions differ. Neither study establishes effects for experts, LLMLang users, or autonomous coding agents. “Better sounding” must not stand in for fewer correct repairs or lower regression rate. |

## 4. Candidate contract dimensions

Keep these independent in the comparison matrix:

1. **Core representation:** stable diagnostic code or no stable codes; severity; primary and secondary source ranges; related locations; stage (lex/parse/name/type/effect/ownership/const-eval/codegen/runtime/tool); compiler phase and snapshot identity.
2. **Text rendering:** concise summary plus optional expanded explanation, notes, examples, references, and likely cause. Decide message localization and whether prose can change without changing diagnostic identity.
3. **Machine interface:** stable JSON or library API alongside human CLI output; explicit schema version; byte/UTF-16/Unicode coordinate convention; source URI; related-origin mapping for macro/generated code; deterministic ordering and output limits.
4. **Repair representation:** zero or more code actions, each with one or multiple edits, preconditions/target snapshot, applicability classification, and post-edit validation result. A suggestion is data and does not mutate files by itself.
5. **Incremental lifecycle:** diagnostics are tied to a document snapshot/version; replacement, clearing, cancellation, stale results, duplicate suppression, and cross-file dependencies have explicit behavior.
6. **Authority/trust:** distinguish compiler-proposed edits from agent-authored edits and human-approved edits. The diagnostic channel must not silently apply changes or authorize file writes. Machine-applicable means mechanically representable under declared preconditions, not semantically approved.
7. **Failure and uncertainty:** report a precise local error, a grouped/cascaded cause, or “analysis incomplete/unknown” when the compiler cannot establish the root cause. Do not invent a high-confidence root cause from parser recovery or partial type information.

Possible vectors include: (D-A) human-oriented text first with editor scraping; (D-B) structured diagnostic source of truth with renderers for CLI/LSP/JSON and human-quality text; (D-C) structured core plus separately generated context-aware explanation; and (D-D) structured core with opt-in, typed repair actions. These vectors can combine; none is selected.

## 5. Failure modes to test

- A single primary span points at the use site, while the actual mismatch comes from a declaration or generic constraint elsewhere; secondary spans should preserve the relation.
- Parser recovery emits cascaded errors that an agent mistakes for independent root causes.
- A code fix changes the wrong occurrence, overlaps another edit, or applies to a stale document version.
- Line/column values shift between UTF-8 bytes, Unicode scalar values, UTF-16 code units, macro expansion, and generated files.
- Stable error codes remain the same while prose changes; or prose appears similar while a code's semantics changes. Consumers must not treat presentation strings as keys.
- An agent follows a plausible but wrong fix, “fixes” diagnostics by suppressing a check, widens a type unsafely, or makes unrelated edits.
- A language server publishes stale diagnostics after edits, fails to clear prior messages, or returns only syntax diagnostics when the requested operation required semantic analysis.
- Rich message context exceeds a bounded agent token budget and obscures the actual actionable fields.

## 6. Proposed discriminating evaluation

Build a version-controlled corpus of minimal valid/invalid programs covering parse recovery, name resolution, type mismatch, generic constraints, effect/capability failure, ownership/cleanup, async-context errors, import resolution, and generated-source mapping. For each case, record intended root cause, primary and secondary spans, severity, related diagnostics, recovery state, available repair(s), and whether a fix is semantically valid.

For each case emit the same internal result through (a) terse human CLI, (b) explanatory human CLI, (c) stable JSON, and (d) LSP. Validate schema, source coordinates, phase, cross-file relations, ordering, snapshot identity, and that each renderer preserves the same machine fields. Re-run fixtures after whitespace/Unicode edits and across incremental document updates. Replay edits only in a test copy; require applicable edits to target the declared source version and compile after application.

Then run a preregistered, blinded repair study with separate strata for humans and coding agents. Randomize message format while holding source/task context and model/tool budget constant. Measure:

- correct task completion with tests/spec assertions (primary outcome);
- time/attempts/tokens and compiler invocations;
- regressions, unrelated edits, unsafe/suppressed checks, and failed repairs;
- correct identification of root cause and confidence calibration;
- for suggestions, valid application rate and successful post-edit validation.

Baselines should include plain compiler output, structured diagnostic without generated prose, carefully authored explanation, and (if included) LLM-generated explanation. Keep compiler diagnostics identical across arms when isolating presentation effects. Report novice/professional users separately, pin agent model/toolchain versions, and publish the cases and scoring oracle. A study of human preferences cannot establish autonomous repair safety; a syntax-only fix benchmark cannot establish semantic correctness.

## 7. Current result and open decision questions

Prior art supports separating a structured diagnostic record from its human rendering and from any proposed edit. Rust demonstrates structured suggestions with explicit applicability and executable UI tests; LSP demonstrates transport and editor fields; TypeScript illustrates phase-separated incremental queries; Elm illustrates corpus-driven message coverage. Human studies show that message quality can affect novice debugging but that generated LLM explanations do not reliably beat authored explanations. There is no direct evidence here about agent performance on LLMLang or the cost of a full contract.

Questions that could change a candidate ranking:

1. Which diagnostic fields are normative and stable across compiler versions, and which are renderer-specific?
2. Is JSON/API output a first-class interface, with a separately versioned schema, or only an adapter over LSP?
3. Should compiler errors expose one root diagnostic with linked consequences, or a flat diagnostic list? What should happen when the root cause is uncertain?
4. Which edits may be classified as mechanically applicable, and what exact preconditions and post-edit checks are required?
5. How much context should compiler-authored diagnostics provide before explanation is delegated to an external model? How is untrusted generated text labeled?
6. What coordinate and source-map identity should diagnostics use for Unicode, macros, and generated code?
7. Do agent repair benefits persist when scoring tests, behavior, regressions, and scope discipline rather than message preference or compilation alone?

No output format, message style, or repair authority is selected by this study.

## 8. Sources

- Rust Compiler Development Guide, [Errors and lints](https://rustc-dev-guide.rust-lang.org/diagnostics.html), [UI tests](https://rustc-dev-guide.rust-lang.org/tests/ui.html), and [error codes](https://rustc-dev-guide.rust-lang.org/diagnostics/error-codes.html).
- Microsoft, [Language Server Protocol 3.18 specification](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.18/specification/) and [VS Code Diagnostic API](https://code.visualstudio.com/api/references/vscode-api#Diagnostic).
- Microsoft TypeScript Wiki, [Using the Language Service API](https://github.com/microsoft/TypeScript/wiki/using-the-language-service-api).
- Elm, [Error Message Catalog](https://github.com/elm/error-message-catalog).
- Denny et al., [Error Message Readability and Novice Debugging Performance](https://doi.org/10.1145/3341525.3387384), ITiCSE 2020.
- Becker et al., [Compiler Error Messages Considered Unhelpful: The Landscape of Text-Based Programming Error Message Research](https://doi.org/10.1145/3344429.3372508), ITiCSE-WGR 2019.
- [Not the Silver Bullet: LLM-enhanced Programming Error Messages are Ineffective in Practice](https://arxiv.org/abs/2409.18661), UKICER 2024.
- LLMLang [Scenario 87](RESEARCH-SCENARIO-87-ASYNC-AWAIT-PARSER-DIAGNOSTIC-CORPUS.md), [Scenario 60](RESEARCH-SCENARIO-60-TYPE-INFERENCE-SCOPE-AND-ANNOTATIONS.md), and [Research Option Matrix 01](RESEARCH-OPTION-MATRIX-01.md).
