# Token Efficiency in LLMLang

This document collects architectural and workflow techniques that could reduce token consumption when using LLMs to develop software with LLMLang.

The goal is not simply to make prompts shorter. It is to minimize the information the model must receive, the amount of output it must generate, and the number of correction cycles required to complete an operation reliably.

## 1. Reduce the Context Sent to the Model

Context reduction is often the highest-impact optimization.

- **Send only relevant project fragments.** Provide the SPG nodes affected by the current operation, their dependencies, and the contracts needed to reason about them—not the entire repository.
- **Use references and stable IDs instead of repeating definitions.** When a specification or type already exists, refer to its identifier and version rather than embedding its full text again.
- **Use incremental context.** Send only changes relative to the model's known baseline, together with enough information to establish that baseline.
- **Retrieve details on demand.** Start with a compact structural overview; let the model request additional definitions only when necessary.
- **Use compact machine-oriented representations.** For graph structures, a concise serialization may be more efficient than verbose Markdown or generic JSON.

## 2. Reduce Generated Output

- **Generate structured operations instead of prose or whole files.** For example, have the model propose operations such as `AddFunction`, `UpdateContract`, or `ReplaceNode`.
- **Use patch-based generation.** Generate a diff or a graph mutation rather than rewriting an entire module.
- **Reference existing definitions.** Avoid copying type, interface, and contract definitions into every generated fragment.
- **Return concise diagnostics.** Report an error code, the affected node or requirement ID, and the minimum explanation needed to fix it.
- **Constrain response formats.** Define a schema and omit optional explanations unless they are needed.

## 3. Reduce the Number of Iterations

Correction cycles can consume more tokens than the initial implementation.

- Check specification completeness before asking the model to implement it.
- Divide large tasks into small changes with explicit acceptance criteria.
- Run deterministic checks automatically and return only relevant failures.
- Do not ask the model to re-analyze parts that have not changed and whose previous results remain valid.
- Use independent LLM review selectively; prefer deterministic tools whenever they can perform the check.

## 4. Architectural Opportunities for LLMLang

Token efficiency can be treated as an architectural property of the language and its tooling.

| Technique | Potential token savings |
|---|---|
| Compact SPG serialization | Less context needed to describe the program graph |
| Stable node IDs | Avoids repeating long definitions |
| Dependency-aware context assembly | Sends only the dependencies required for an operation |
| Incremental compilation and validation | Avoids repeating checks for unchanged parts |
| Machine-readable diagnostics | Reduces feedback size during correction |
| Reusable contract objects | Avoids duplicating requirements and constraints |
| Patch-based generation | Outputs only the proposed changes |
| Caching analysis results | Avoids repeating explanations and checks whose inputs have not changed |

These are design opportunities, not claims that the current LLMLang concept already implements them.

## 5. Match Model Capability to Task Complexity

Not every operation requires the most capable reasoning model.

- Use a small, fast model for simple transformations.
- Use a suitable code-generation model for routine, well-constrained fragments.
- Reserve stronger reasoning models for architecture and ambiguous design decisions.
- Prefer deterministic tools over LLMs for checks that can be performed mechanically.
- Use independent strong-model audits for complex or high-impact changes where additional review is justified.

Optimize for the cost of a successful result, not merely the price of one model call. A cheaper model that needs several correction cycles may cost more than a stronger model that completes the task in one.

## 6. Recommended Priorities

A practical implementation order for LLMLang would be:

1. **Dependency-aware context assembly.** Construct the smallest SPG subgraph sufficient for the requested operation.
2. **An operation-oriented interface.** Have the model return typed graph mutations instead of rewriting source files.
3. **Incremental feedback.** Return only new diagnostics and verification-status changes.
4. **Reusable versioned context.** Store specifications, contracts, and validation results as independently addressable, versioned objects.
5. **Per-operation token measurement.** Track input tokens, output tokens, repeated context, and the number of iterations separately.

## 7. Measure Actual Tokenization

A shorter textual representation does not necessarily use fewer tokens. For example, compact JSON with many punctuation and delimiter characters may tokenize less efficiently than concise natural language or a purpose-built notation.

LLMLang should therefore evaluate candidate serializations with the actual tokenizers of its target models. Measurements should use representative SPG fragments and realistic tasks, not only synthetic examples.

## Guiding Principle

Token efficiency in LLMLang can be expressed as three goals:

- **Minimum context** needed for the model to make a decision.
- **Minimum change** needed to perform the requested operation.
- **Minimum feedback** needed to correct an invalid result.

These goals should be balanced against correctness, traceability, and the ability to independently validate model-generated changes.
