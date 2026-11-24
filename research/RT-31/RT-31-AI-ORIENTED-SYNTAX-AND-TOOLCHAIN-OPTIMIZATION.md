# RT-31 — AI-Oriented Syntax, Semantic Separation, and Toolchain Optimization

**Status:** Research brief; architecture and implementation choices remain open  
**Priority:** P0  
**Research area:** RT-31 — AI-oriented syntax and evidence-driven Toolchain optimization  
**Related:** RT-03 language semantics; RT-05 semantic identity and SPG; RT-07 formal verification; RT-08 testing and evidence; RT-09 compiler frontends and IR; RT-14 AI authoring/context; RT-16 security and trust; RT-18 evolution; RT-19 Toolchain Server and semantic development API; RT-20 LLM patch planning; RT-22 repository/worktree MCP; RT-24 canonical semantic representation, diff, and merge; RT-30 bidirectional translation.

## 1. Goal

Design an architecture that allows LLMLang to preserve its full intended semantic capability while independently experimenting with surface syntax and interaction representations to find forms that coding models use with the fewest errors.

The research must also define an MCP session-observability capability that records sufficiently rich, reproducible interaction and validation evidence to measure model errors, distinguish their causes, and improve syntax profiles, agent instructions, diagnostics, and Toolchain behavior over time.

The central distinction is mandatory:

- **Semantics** define what programs mean and what capabilities the language provides.
- **Syntax** defines how those capabilities are expressed and exchanged.
- A syntax profile must not add, remove, weaken, or silently reinterpret semantic capabilities merely to make generation easier for a model.

This is a Toolchain and language-architecture research topic. It must not turn model-specific preferences into restrictions on the language's semantic design.

## 2. Scope and non-goals

### In scope

- Separation of semantic definitions from syntax representation and concrete surface forms.
- A layered architecture involving a language Semantic Model, an Abstract Syntax Model, and independently versioned Concrete Syntax Profiles.
- The role and boundaries of canonical Semantic IR, ASTs, syntax trees, and transformations between them.
- Multiple parsers, formatters, generators, and syntax-profile adapters over the same semantic capabilities.
- Semantic-equivalence and round-trip validation across syntax profiles.
- Controlled experiments comparing AI authoring accuracy, repair effort, token use, and task completion.
- MCP session/event recording, correlation, provenance, retention, privacy, and security.
- Error classification, analytics, and evidence-driven improvement of syntax, instructions, diagnostics, and Toolchain.
- Versioning and reproducibility of experiments, models, prompts/instructions, profiles, fixtures, and validators.

### Out of scope

- Selecting a final LLMLang textual grammar before comparative evidence exists.
- Reducing semantic capabilities to match the limitations of a particular model.
- Treating successful parsing as proof of semantic correctness.
- Treating model-generated code or self-reported success as trusted evidence.
- Automatically changing normative language semantics or production instructions from unreviewed telemetry.
- Assuming that all MCP clients expose identical model metadata or complete prompt/response traces.
- Logging secrets or unrestricted user data by default.

## 3. Architectural model to investigate

The research starts from three independently reasoned levels:

1. **Semantic Model** — authoritative meaning: values, types, operations, contracts, invariants, effects, ownership, lifecycle, errors, concurrency, and observable behavior.
2. **Abstract Syntax Model** — syntax-independent structural representation of language constructs and their composition. Its relationship to the canonical Semantic IR must be explicit; research whether they are distinct models, partially shared representations, or connected by a typed mapping.
3. **Concrete Syntax Profiles** — independently versioned lexical and grammatical choices, surface notation, delimiters, declaration forms, layout rules, and formatting conventions.

The architecture must also examine the canonical Semantic IR as the stable semantic interchange and validation boundary. It must not assume that a concrete parser's AST is itself the semantic authority.

Candidate pipeline:

`Concrete Syntax Profile → Parser → Abstract Syntax Model → semantic elaboration/validation → Canonical Semantic IR`

The reverse path should support deterministic or explicitly bounded generation:

`Canonical Semantic IR → abstract syntax projection → selected Syntax Profile → formatter/generator`

The research must define where normalization, desugaring, name resolution, type checking, contract checking, and semantic validation occur. It must identify information that must survive every transformation, including source provenance and diagnostics locations, without conflating source identity with semantic identity.

### Required invariants

- Every supported syntax profile must map to the same declared semantic capability model.
- Syntax-profile changes must not silently change semantic identity or meaning.
- Unsupported or ambiguous syntax must fail explicitly rather than being guessed.
- Profile-to-profile conversion must preserve semantics; textual round-trip identity is a separate, optional property.
- Semantic equivalence claims must be checked against explicit observations and independent oracles, not inferred from matching AST shape or successful parsing.
- Semantic features must remain expressible even if one profile or one model handles them poorly.
- The system must be able to compare syntax profiles without changing the underlying task, semantic requirements, or acceptance oracle.

## 4. Research questions

### 4.1 Semantic/syntax boundary and intermediate representations

- What belongs in the Semantic Model, Abstract Syntax Model, and Concrete Syntax Profile?
- Which constructs require explicit semantic elaboration rather than direct AST-to-IR mapping?
- Should AST and canonical Semantic IR be separate, and what information does each own?
- How are source spans, comments, formatting, names, declarations, and provenance preserved?
- How are syntax-profile versions related to language semantic versions?
- Can multiple frontends and generators share one semantic validation pipeline?
- How are extensions, experimental syntax, deprecation, and profile migration represented?

### 4.2 Syntax profiles and transformations

- Which syntax dimensions should be independently variable: keyword choice, punctuation, nesting, declaration ordering, explicitness, named arguments, block structure, annotations, delimiters, and layout?
- Compare textual, structured, and hybrid representations without assuming one is superior.
- Define parser/generator contracts and deterministic formatting behavior.
- Define profile compatibility, feature coverage, unsupported constructs, and diagnostic behavior.
- Build profile-independent fixtures and cross-profile semantic round-trip tests.

### 4.3 Controlled AI syntax experiments

- Construct representative tasks spanning declarations, types, generic constraints, contracts, invariants, ownership, effects, control flow, error handling, concurrency, modules, and multi-step changes.
- Compare profiles using the same task semantics, context, instruction budget, model, model settings, tools, and acceptance oracle wherever possible.
- Control for model/version drift, sampling variance, task ordering, prompt leakage, and profile-specific documentation differences.
- Separate first-pass correctness from repair-assisted completion.
- Measure syntax errors, semantic errors, contract/invariant violations, unsupported constructs, hallucinated constructs, task completion, repair count, token/cost, latency, and reviewer effort.
- Report sample sizes, uncertainty, confidence intervals, and per-task/per-feature breakdowns; avoid ranking profiles from small or confounded samples.
- Include human readability and maintainability as independent dimensions rather than optimizing solely for model performance.

### 4.4 MCP session recording and evidence model

- Define session, turn, request, response, tool-call, validation-run, repair-attempt, and experiment identifiers and their correlation.
- Record available model/provider/version metadata, toolchain build, language/semantic version, syntax profile/version, instruction-set version/hash, task/fixture identity, and execution environment.
- Define event ordering, timestamps, append-only or tamper-evident storage options, partial-session handling, and idempotent ingestion.
- Record request/response/tool payloads only under explicit capture policy; support metadata-only, redacted, and approved full-content modes.
- Define secret detection/redaction, access control, encryption, retention, deletion, export, and audit requirements.
- Preserve validation results and diagnostic codes, parser/type/semantic/contract/test outcomes, repair loops, and final acceptance status.
- Distinguish unavailable metadata from absent values; never infer a model identity or context that the MCP client did not provide.

### 4.5 Error taxonomy and attribution

At minimum distinguish:

- lexical and syntax errors;
- structural/AST construction errors;
- name-resolution and reference errors;
- type, effect, ownership, and capability errors;
- contract and invariant violations;
- semantic misunderstanding despite valid syntax;
- invented or unsupported language constructs;
- invalid MCP/tool invocation or protocol misuse;
- incomplete task/context or ambiguous human intent;
- Toolchain/parser/validator defects;
- external environment, dependency, build, and test failures;
- repair regressions and repeated error patterns.

Attribution must permit multiple contributing causes and an unknown/undetermined category. A parser rejection is not automatically an AI error; a Toolchain defect must not inflate model error rates.

### 4.6 Analytics and improvement loop

- Aggregate error rates by model, task class, syntax profile, language feature, instruction version, Toolchain version, and experiment.
- Identify recurring confusion pairs, omission patterns, invalid construction patterns, repair loops, and regressions.
- Compare syntax changes with instruction/documentation changes and diagnostic improvements as separate interventions.
- Maintain fixed benchmark suites and held-out tasks to reduce overfitting.
- Require human-reviewed proposals and regression evaluation before promoting profile, instruction, or Toolchain changes.
- Track Pareto trade-offs among correctness, semantic coverage, token/cost, latency, human review, and maintainability.
- Preserve historical experiment data so metrics can be recomputed under improved classifiers.

## 5. Candidate vectors to compare

| Vector | Representation | Main hypothesis | Key risk |
|---|---|---|---|
| A | Conventional textual syntax profiles | Familiar programming-language notation is easiest to learn and review | Models may confuse similar tokens, precedence, and nesting |
| B | Explicit/verbose textual syntax | Redundancy and explicit delimiters reduce omission and ambiguity | Token overhead and verbosity |
| C | Structured syntax | Typed fields and explicit nodes reduce grammar errors | Poor ergonomics, serialization overhead, and context expansion |
| D | Hybrid syntax | Structured declarations/operations plus readable textual expressions balance precision and usability | Boundary complexity and inconsistent mental models |

These are experiment vectors, not selected designs. Additional vectors may be introduced when supported by a clear hypothesis.

## 6. Required metrics

| Metric | Definition / observation |
|---|---|
| Parse success rate | Fraction of first-pass outputs accepted by the selected profile parser |
| Syntax error rate | Syntax/lexical errors per task and per generated construct |
| Semantic correctness rate | Fraction satisfying the independent semantic acceptance oracle |
| Contract/invariant violation rate | Violations detected after successful parsing/elaboration |
| Unsupported/hallucinated construct rate | Use of constructs absent from the declared profile/language version |
| Task completion rate | Fraction meeting all declared acceptance criteria |
| First-pass success | Completion without repair feedback |
| Repair rate and repair cost | Number of repair iterations, tokens, latency, and regressions |
| Tool-call correctness | Valid MCP calls, argument shape, and protocol behavior |
| Token and latency cost | Input/output tokens where available, elapsed time, and toolchain work |
| Human review effort | Time and interventions needed to validate or correct output |
| Semantic coverage | Whether the profile can express the required semantic feature set |
| Reproducibility | Ability to replay the same pinned experiment and recover comparable outcomes |

Metrics must be defined with denominators and missing-data policy. Parsing success alone is never a proxy for semantic correctness.

## 7. Dependencies and boundaries

- RT-03 defines the semantic observations that syntax profiles must preserve.
- RT-05 and RT-24 provide identity and canonical representation constraints.
- RT-07 and RT-08 provide independent correctness, testing, and evidence oracles.
- RT-09 provides frontend, AST/IR, elaboration, and generator architecture.
- RT-14 and RT-19 provide agent context and transport-neutral Toolchain/MCP integration.
- RT-16 constrains session capture, permissions, redaction, retention, and trust.
- RT-18 constrains profile, instruction, model, and Toolchain evolution.
- RT-22 informs repository/worktree session provenance and durable audit integration.
- RT-30 provides cross-language frontend/backend and semantic-preservation lessons.

MCP session observability is a Toolchain/platform capability, not a language semantic feature. Syntax profiles are language/toolchain representations, not independent semantic dialects. Model-specific instructions are versioned experimental inputs, not normative language semantics.

## 8. Required experiments and deliverables

1. A semantic/syntax responsibility matrix and end-to-end transformation architecture.
2. A minimal reference Semantic Model/IR and Abstract Syntax Model mapping for a representative feature subset.
3. At least three materially distinct syntax profiles covering the same semantic subset.
4. Parser, generator, formatter, and cross-profile conversion prototypes.
5. A semantic-equivalence corpus with positive cases, negative controls, and independently checked observations.
6. A controlled AI evaluation harness with pinned tasks, models/settings, instructions, profiles, and validators.
7. An MCP session event schema and recording prototype with metadata-only and redacted capture modes.
8. An error taxonomy and attribution workflow, including Toolchain-originated and unknown failures.
9. An analytics report with uncertainty, per-feature results, repair outcomes, and cost/review trade-offs.
10. A documented improvement and promotion process with held-out regression suites.
11. Security/privacy threat analysis, retention policy options, and access-control tests.
12. A candidate architecture and explicit unresolved decisions; no final syntax or unrestricted logging policy is selected by this brief.

## 9. Falsifiers and acceptance gates

A proposed architecture is materially weakened if:
- two profiles that claim equivalent coverage produce different accepted semantic observations;
- a syntax change silently drops or changes semantic information;
- profile comparisons use different semantic tasks or acceptance oracles;
- measured gains disappear under repeated or held-out tasks;
- error attribution systematically confuses Toolchain defects with model mistakes;
- telemetry cannot be tied to exact model/profile/instruction/toolchain versions;
- sensitive session content is captured without a defensible policy;
- analytics cannot distinguish first-pass success from repair-assisted success.

The research may be considered complete for a declared scope only when the semantic boundary is explicit, at least three profiles are compared on a common fixture set, semantic preservation has independent evidence, MCP recording is demonstrated with privacy controls, and the evaluation reports reproducible model/task-level outcomes and limitations.

## 10. Decision boundary

This brief does not select a final grammar, AST/IR decomposition, session storage format, telemetry retention policy, model, or automatic optimization policy. It establishes the required research and evidence. Any proposed normative language rule or production architecture must be separately reviewed and explicitly accepted.
