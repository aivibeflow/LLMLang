# Research Scenario 54 — Pattern Matching and Exhaustiveness

**Status:** Evidence-linked prior-art comparison; no LLMLang pattern or exhaustiveness model selected  
**Research area:** RT-03 control flow and value semantics, RT-04 type structure and diagnostics, RT-06 API evolution  
**Updated:** 2026-11-19

## 1. Question and scope

How should a program destructure values and branch on cases, and when should the compiler require or infer complete coverage? Separate these concerns:

1. Pattern vocabulary (literal, tuple, record, variant, type, range, list, binding, wildcard).
2. Irrefutable destructuring versus refutable branching.
3. Ordered decision semantics and first-match behavior.
4. Exhaustiveness and unreachable/redundant-arm analysis.
5. Pattern guards and whether they contribute to coverage proofs.
6. Branch-local binding and ownership/move behavior.
7. Open-world type evolution and downstream exhaustiveness obligations.
8. Statement-only switch versus value-producing match expression.

This report compares Rust, Swift, and Go references. It does not assume that complete static coverage is always possible or that a wildcard is always a safe forward-compatibility policy.

## 2. Prior-art comparison

### Rust: expression-valued `match`, exhaustive patterns, wildcard coverage

Rust `match` branches on patterns and is an expression: each reachable arm contributes to the expression result. The compiler requires all possible values to be covered and diagnoses missing cases; pattern analysis also detects some unreachable or redundant arms. Guards allow additional conditions but interact with usefulness/exhaustiveness. Non-exhaustive public enums require downstream callers to provide a wildcard arm, allowing the defining crate to add variants later without making downstream matches invalid.

This combines value extraction, branching, and static coverage in one construct. It supports precise diagnostics and safe handling of closed algebraic types, while wildcard arms can collapse future cases into generic behavior and hide newly introduced variants unless the API distinguishes unknown cases.

Sources: [Rust Reference — Match expressions](https://doc.rust-lang.org/reference/expressions/match-expr.html), [Rust Reference — Patterns](https://doc.rust-lang.org/reference/patterns.html), [Rust Reference — Non-exhaustive types](https://doc.rust-lang.org/reference/attributes/type_system.html#the-non_exhaustive-attribute).

### Swift: exhaustive `switch` statements and expressions, library-evolution modes

Swift `switch` supports patterns and must cover every possible value. Its expression form ensures a value is produced on every branch. A `default` can cover remaining values. For nonfrozen enums in library-evolution contexts, clients require a default; `@unknown default` distinguishes future cases and allows the compiler to warn when a newly known case is not handled explicitly.

The model makes missing behavior visible for closed domains and gives a dedicated mechanism for future enum cases. It couples exhaustive switching with API/library evolution mode, so a type's openness affects caller diagnostics and the stability of coverage assumptions.

Sources: [Swift Language Guide — Control Flow](https://docs.swift.org/latest/documentation/the-swift-programming-language/controlflow/), [Swift Statements — Exhaustiveness and unknown defaults](https://docs.swift.org/swift-book/ReferenceManual/Statements.html).

### Go: expression/type `switch`, runtime selection without general exhaustiveness

Go `switch` statements choose a case by evaluating expression cases in order; a missing case is allowed and the switch may do nothing. Type switches branch on the dynamic type of an interface value. Cases do not implicitly fall through (explicit `fallthrough` is limited to expression switches). A `default` clause is optional, and there is no general enum exhaustiveness requirement in the language specification.

This keeps multiway branching usable for open values and interfaces without proving total coverage. The trade-off is that adding a new constant or implementation does not force callers to revisit every switch; tools may offer generated-case code actions but this is not a language-level guarantee.

Source: [Go specification — Switch statements](https://go.dev/ref/spec#Switch_statements).

## 3. Comparison matrix

| Dimension | Rust | Swift | Go |
|---|---|---|---|
| Main construct | Expression `match` | Statement and expression `switch` | Statement `switch` |
| Pattern scope | Rich patterns and destructuring | Rich case patterns and associated values | Expression constants and interface type switch |
| Exhaustiveness | Required for `match` | Required; library-evolution enums require future-case handling | Not generally required |
| Branch result | Every arm yields expression-compatible value | Switch expression yields branch value; statement form need not | Statement control flow; use explicit assignment/return |
| Wildcard/default | `_` covers remainder | `default`; `@unknown default` for future enum cases | Optional `default` |
| Guard treatment | Guard is part of arm; coverage analysis has special conservatism | `where`/pattern conditions affect case behavior | Conditional expressions or nested control flow |
| Future variant policy | `non_exhaustive` requires wildcard downstream | Frozen/nonfrozen distinction and `@unknown default` | Caller switches may omit future values silently |
| Main risk | Wildcard hides domain additions; analysis complexity | Evolution mode and defaults need careful API policy | Missing behavior is accepted unless external lint catches it |

## 4. Discriminating fixtures

1. Match a closed enum with one omitted variant; record required diagnostic and suggested cases.
2. Add a wildcard branch, then add a new variant; compare whether tooling warns that a specific branch should be added.
3. Match an open/non-exhaustive public enum from an external package; compare local implementation and client obligations.
4. Use guards that are constant true/false, overlapping ranges, and predicates the analyzer cannot prove; check what counts as covered and unreachable.
5. Test nested tuple/record/or-patterns, duplicate bindings, refutable `let`, and partial destructuring.
6. Test payload extraction across branches under copy, borrow, move, and owned-resource profiles; ensure rejected branches leave consistent ownership state.
7. Compare statement form and value form, including return, throw, diverging branches, unit branches, and branch type unification.
8. Test null/optional values, interface/dynamic types, sealed versus open hierarchies, and foreign ABI values outside the nominal variant set.
9. Rename/reorder arms and check whether binding identities and semantic dependency edges remain stable.

Capture accepted/rejected status, exhaustiveness proof assumptions, branch bindings, type/ownership result, decision order, diagnostics, and public API openness metadata.

## 5. Cross-area implications and open hypotheses

- Pattern matching, control-flow branching, and expression result production should be compared as independent features even when one syntax combines them.
- Exhaustiveness is only as strong as the closed-world assumption for the matched type. Module/package visibility, plugins, FFI, dynamic interfaces, and library evolution determine whether that assumption is sound.
- A wildcard preserves forward compatibility but can silently route new variants through stale generic behavior. An explicit “unknown future” arm can preserve runtime resilience while allowing warnings when cases become known.
- Guards generally make coverage undecidable or expensive if treated as arbitrary expressions. Specify conservative rules (for example, guarded arms do not prove coverage) and test diagnostics rather than relying on intuition.
- Redundancy detection improves maintenance but must be sound under guard semantics, value domains, numeric ranges, and open constructors.
- Destructuring bindings interact with ownership and cleanup. A successful syntactic pattern does not decide whether payloads are copied, borrowed, moved, or partially consumed.
- Expression-valued matching guarantees a result on every path and fits typed IR/control-flow graphs; statement-only switches may be simpler but make value joins explicit.
- Adding a variant can be a source-breaking change for exhaustive clients or a silent behavior gap for non-exhaustive switches. This belongs in the API compatibility model and dependency graph.

No LLMLang pattern repertoire, exhaustiveness requirement, wildcard semantics, future-variant policy, or branch ownership rule is selected.

## 6. Next research and falsifiers

Prototype a finite algebraic data type fragment with nested patterns, guards, and branch-local bindings. Compare mandatory exhaustive expression matching, exhaustive closed types plus explicit open-type fallback, and non-exhaustive statement switch. Add separate copy/borrow/move payload modes. Measure missing-case bug detection, false unreachable diagnostics, type/ownership inference complexity, API evolution behavior, and repair effort on common refactors.

Mandatory exhaustiveness is weakened if common open-world inputs require unsafe catch-all behavior or users routinely add meaningless defaults. Non-exhaustive switching is weakened if adding variants leaves many callers with latent omissions. Rich patterns are weakened if guard/ownership analysis yields opaque diagnostics or makes small updates invalidate large semantic regions.

## 7. Sources and temporal limits

Official references were consulted 2026-11-19. Rust and Swift references are rolling; Swift library-evolution settings and Rust non-exhaustive behavior should be tested with pinned toolchains. Go's language specification is versioned. Keep compiler behavior and lint/tool extensions separate from normative language rules.
