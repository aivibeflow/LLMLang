# Research Scenario 49 — Operators, Conversions, and Precedence

**Status:** Evidence-linked prior-art comparison; no LLMLang operator or coercion model selected  
**Research area:** RT-03 expression parsing/evaluation, RT-04 conversion and operator typing, RT-09 optimization  
**Updated:** 2026-11-19

## 1. Question and scope

How should operators group and evaluate, how may types provide operator behavior, and when can an expression change type implicitly?

Keep these decisions separate:

1. Grammar precedence and associativity: how token sequences form expression trees.
2. Evaluation order: when operands are evaluated and whether evaluation can be skipped.
3. Operator dispatch: built-in-only, statically overloaded, extension-defined, or dynamically dispatched.
4. Conversion: explicit casts, implicit coercions, contextual literal typing, lossless widening, and narrowing.
5. Operator precedence extension: fixed global table or user-defined precedence relations.
6. Semantic transparency: whether the same token may invoke arbitrary user-defined behavior.

This report compares Rust, Go, Swift, and Zig language references. It does not define exact LLMLang grammar, operator list, trait/coherence model, or conversion proof obligations.

## 2. Prior-art comparison

### Rust: fixed precedence, left-to-right operands, trait-based operator overloads

Rust specifies a fixed precedence/associativity table and separately specifies evaluation order: for multi-operand expressions, operands are evaluated left to right as written before the operator effects are applied. Many built-in operators can also be overloaded through traits in std::ops or std::cmp. The same syntax can therefore dispatch to user-defined implementations, but the precedence structure remains language-defined rather than library-defined.

This retains a stable parse while allowing domain types such as vectors or ranges to use familiar syntax. The trade-off is that operator meanings can depend on operand types, so readability and effect behavior depend on implementation conventions.

Sources: [Rust Reference — Expressions, precedence, and operand order](https://doc.rust-lang.org/reference/expressions.html), [Rust core::ops guidance](https://doc.rust-lang.org/stable/core/ops/index.html).

### Go: small fixed precedence hierarchy and explicit conversion syntax

Go defines five binary precedence levels, with operators at the same level associating left to right. Operator tokens have language-defined meanings rather than user-defined overloads. Numeric types are distinct, and conversion is written explicitly as T(x), while untyped constants may adapt to a representable type through context. The specification separately gives a left-to-right ordering rule for calls, method calls, receives, and binary logical operations.

This keeps operator syntax and dispatch predictable across libraries. It places more conversions in source code and gives users fewer syntax-extension options, while retaining contextual convenience for exact constants.

Sources: [Go specification — Operators](https://go.dev/ref/spec#Operators), [Go specification — Operator precedence](https://go.dev/ref/spec#Operator_precedence), [Go specification — Conversions](https://go.dev/ref/spec#Conversions), [Go specification — Order of evaluation](https://go.dev/ref/spec#Order_of_evaluation).

### Swift: custom operator tokens and precedence groups

Swift supports operator overloading and permits custom prefix, postfix, infix, and assignment operators. A custom infix operator belongs to a precedence group; groups declare associativity and relative precedence to other groups. This lets libraries define syntax for domain-specific types while keeping parsing tied to declarations and precedence relationships.

The expressive power creates a larger reader/compiler surface: imported libraries can add unfamiliar tokens and precedence relationships. Formatting and code review cannot assume one small, closed table, so API design and tooling become important for readability.

Source: [Swift Language Guide — Advanced Operators](https://docs.swift.org/latest/documentation/the-swift-programming-language/advancedoperators/).

### Zig: fixed operator meanings with peer-type resolution

Zig documents a fixed set of built-in operator meanings and peer type resolution for selected operators. The language reference describes operators in a table so a given operator has a known built-in role; type compatibility is resolved under explicit peer-type rules rather than by arbitrary user-defined overloads. Explicit casts/coercions make type movement more visible, with compile-time-known literals able to participate in contextual typing.

This favors mechanically predictable syntax and explicit type transitions. The operator set cannot be expanded for domain-specific notation, and peer type resolution still requires a precise specification so mixed-type expressions remain unsurprising.

Sources: [Zig Language Reference — Operators](https://ziglang.org/documentation/master/#Operators), [Zig Language Reference — Peer Type Resolution](https://ziglang.org/documentation/master/#Peer-Type-Resolution).

## 3. Comparison matrix

| Dimension | Rust | Go | Swift | Zig |
|---|---|---|---|---|
| Precedence | Fixed language table | Five binary levels | Fixed standard groups plus extensible declared groups | Fixed language table |
| Associativity | Specified per level; some comparisons require parentheses | Same-level binary operators left-associative | Declared by precedence group | Language-defined |
| Operand evaluation | Specified left-to-right for listed multi-operand expressions | Specified for calls/receives/logical operators; other expressions follow spec rules | Expression semantics and short-circuit operators specified separately | Language-defined; consult operator expression rules |
| User-defined operator meaning | Trait-based overload for supported operators | No overload | Broad operator overload and custom operators | Operator set/meaning fixed; no general operator overload |
| Numeric conversions | Explicit casts plus limited coercions/contextual typing | Explicit T(x); constants can be contextually typed | Type inference and literal protocols; numeric variables generally require explicit conversion | Explicit casts/coercions and peer type resolution |
| Syntax extensibility | Operator meaning constrained by trait contracts | None | High, including relative precedence groups | None |
| Main risk | Overloaded operator meaning/effects vary by type | Boilerplate conversions; fixed notation | Imported syntax and precedence can surprise readers | Explicitness/rigidity and peer-resolution complexity |

Parsing precedence, evaluation order, and overload resolution are separate rules. One does not imply the others.

## 4. Discriminating fixture

Use a mixed numeric expression, a user-defined vector type, and an effectful operand:

- Evaluate an expression with addition, multiplication, comparison, short-circuit logic, cast, and assignment.
- Define a vector addition and equality operator; also define a deliberately surprising overload that performs I/O or mutates state.
- Import a library that declares a custom infix operator and precedence relationship; evaluate the same source with and without that import.
- Mix exact integer literals, fixed-width integers, floats, and a narrowing conversion.
- Use calls with visible side effects in both operands to record evaluation order.

For each candidate, record the parse tree, overload chosen, implicit/explicit conversions, operand evaluation sequence, skipped evaluations, result type, overflow/conversion outcome, and diagnostics. Test formatter/IDE output and whether imported dependencies can change the parse tree or only name resolution.

## 5. Cross-area implications and open hypotheses

- Precedence should generally be stable independently of operator implementation; user-defined precedence makes imports part of parsing and therefore part of editor/compiler dependency state.
- Operator overloading can preserve notation for algebraic types but can hide effects and domain-specific semantics behind familiar tokens.
- Fixed operators do not automatically guarantee clear behavior: implicit coercions, overloaded functions, peer-type inference, and evaluation order still need specification.
- Contextually typed literals improve ergonomics but should not imply lossy conversions for runtime values.
- Conversion policy should identify whether each path is exact, checked, trapping, saturating, wrapping, or implementation-dependent, linking to Scenario 45 numeric semantics.
- A formatter or semantic diff must preserve the expression tree; adding/removing parentheses is semantics-preserving only when the target grammar and operator environment are fixed.

## 6. Next research and falsifiers

Encode the fixture's expected parse trees and evaluation traces in a language-neutral table. Prototype fixed built-in operators, constrained overloads, and import-extensible precedence in at least two parser/type-checker configurations. Check whether AST identity changes under import additions, whether effectful overloads are discoverable in diagnostics, and whether formatters round-trip the exact tree.

Extensible operators are weakened if libraries routinely introduce collisions or obscure control/data flow. Built-in-only operators are weakened if common domain types become less readable or require unstable DSLs. Broad implicit conversions are weakened if they produce target-dependent or lossy behavior; wholly explicit conversions are weakened if they bury common, statically safe transformations in boilerplate. Any choice is weakened if parser, type checker, evaluator, optimizer, and semantic diff disagree on the resulting expression tree.

No LLMLang precedence table, operator-overloading policy, or implicit-conversion rule is selected.

## 7. Sources and temporal limits

Official documentation was consulted 2026-11-19. Rust, Go, and Swift references are rolling; Zig master documentation is especially version-sensitive. Pin compiler versions and test parse/type/evaluation behavior before treating implementation diagnostics as normative.
