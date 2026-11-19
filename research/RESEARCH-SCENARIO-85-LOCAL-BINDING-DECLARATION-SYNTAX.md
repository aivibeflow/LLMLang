# Research Scenario 85 — Local Binding Declaration Syntax

**Status:** Evidence-linked prior-art comparison; no LLMLang binding syntax selected  
**Research area:** RT-03 declarations and scope, RT-04 mutability/initialization, RT-11 binding identity  
**Updated:** 2026-11-19

## 1. Question and scope

How does source syntax distinguish introducing a new binding from assigning to an existing place? How are mutability, type annotation/inference, destructuring, multiple bindings, and initialization expressed? This study focuses on local variable/constant binding forms.

It complements rather than replaces Scenario50 (scope/shadowing), Scenario60 (inference scope), Scenario67 (binding versus object/graph mutability), Scenario68 (construction/definite initialization), and Scenario74 (refutable binding failure). It does not choose mutability depth or assignment semantics.

## 2. Prior-art comparison

### Rust: `let` introduces a pattern binding; mutability is on the pattern

Rust `let` introduces one or more names through a pattern, optionally followed by a type annotation and initializer; a refutable pattern can use an `else` block. Type annotations are optional when inference succeeds. Rebinding with `let` shadows an earlier name, while assignment uses a separate expression form. Mutability is written with `mut` on the binding/pattern, allowing mixed binding patterns. An uninitialized local can be declared with an explicit type but must be definitely initialized before use; patterns provide destructuring.

Source: [Rust Reference — Let statements](https://doc.rust-lang.org/reference/statements.html#let-statements).

### Go: `var` declarations plus short `:=` declarations

Go `var` declares one or multiple identifiers with an optional type and/or initializer. If no initializer is present, each receives its type's zero value. Inside functions, `:=` is a concise inferred declaration. It can redeclare an existing same-block variable only in a multi-name declaration where at least one non-blank name is new; such a name is assigned, not rebound. This couples declaration syntax to scope/reuse rules. Go does not distinguish immutable local bindings with a `let` keyword; `const` declarations are a separate constant form.

Source: [Go specification — Variable declarations and short variable declarations](https://go.dev/ref/spec#Variable_declarations).

### Swift: `let` versus `var`, inferred or annotated, with destructuring

Swift uses `let` for an immutable binding and `var` for a mutable binding. A type annotation is optional when the initializer supplies enough information. Tuple patterns can bind multiple names. Local `let` declarations may be initialized later if definite-initialization analysis proves they are set before use, while global constants require initializers. `var` declarations include several additional forms for properties and computed storage, so local and property declaration grammar are related but not identical.

Sources: [Swift Language Reference — Declarations, Constant Declaration](https://docs.swift.org/latest/documentation/the-swift-programming-language/declarations/), [Swift Language Guide — Constants and Variables](https://docs.swift.org/latest/documentation/the-swift-programming-language/thebasics/#Constants-and-Variables).

### Zig: `const` versus `var`, initializer required

Zig writes `const name = value` for an immutable binding and `var name = value` for a mutable one; a type annotation can be present. The declaration requires an initializer; declaring `var x: T;` without `=` is rejected. The same const/var distinction is available at function and namespace scope, with storage and compile-time behavior depending on location. This makes uninitialized local state explicit only through specific values/types rather than bare declarations.

Source: [Zig Language Reference — Assignment and variable declarations](https://ziglang.org/documentation/master/#Assignment).

## 3. Comparison matrix

| Dimension | Rust | Go | Swift | Zig |
|---|---|---|---|---|
| Immutable local form | `let x = value` | `const x = value` (separate constant declaration) | `let x = value` | `const x = value` |
| Mutable local form | `let mut x = value` | `var x T = value` or `x := value` | `var x = value` | `var x = value` |
| Type annotation | Optional after pattern | Optional before/with initializer | Optional after binding | Optional after `:` |
| Initializer omission | Allowed with type; definite initialization applies | Allowed; zero value assigned | Local `let` may be initialized later; many `var` forms permit omission by context | Not allowed for ordinary variable declaration |
| Destructuring | Pattern on `let` | Multiple identifiers and assignment values; no general pattern `var` declaration | Tuple patterns | Destructuring through assignment/aggregate forms; declaration form is identifier based |
| New name vs existing assignment | `let` creates/shadows; `=` assigns | `:=` declaration/redeclaration rule; `=` assigns | `let`/`var` declarations; `=` assigns | `const`/`var` declarations; `=` assigns |
| Multiple declarations | Pattern can bind several; repeated `let` statements | Identifier lists and grouped declarations | Pattern-initializer list | Comma-separated assignment/declaration forms in selected grammar |
| Refutable pattern behavior | `let ... else` exit required | Usually assignment/test forms handled separately | `if case`, `guard case`, `switch` forms | `if`/`switch` and destructuring forms rather than ordinary const/var declaration |
| Main surface distinction | Mutability annotation on a pattern | Concise `:=` with same-block redeclaration | Keyword selects binding mutability | Keyword selects binding mutability; initializer required |

The table separates binding mutability from mutability reachable through a reference. It also separates creating a binding from updating a place, even where a language's shorthand syntax combines declaration and assignment for some names.

## 4. Discriminating fixtures

1. Compare `let x = e`, `var x = e`, `const x = e`, and a later assignment. Confirm token/AST distinction between new binding and mutation.
2. Reuse a name in the same scope, inner scope, and multi-name declaration. Record whether it shadows, reuses an existing identity, or errors.
3. Compare inferred and annotated forms with literals, overloaded expressions, `nil`/null-like values, function results, and insufficient type information.
4. Test no-initializer forms with and without explicit type, across local, property, and namespace scope. Record definite initialization/zero-value semantics separately from spelling.
5. Destructure tuples, records, arrays, and nested patterns; mix immutable and mutable bindings; test duplicate names and ignored components.
6. Use refutable patterns in declarations. Check whether failure is syntax error, non-exhaustive error, explicit `else`, optional binding, or runtime branch.
7. Test declaration inside `if`/loop headers, short scope lifetime, shadowing, closure capture, and subsequent assignment.
8. Rename the binding but keep initializer and references structurally equivalent; compare identity/provenance requirements and expected incremental invalidation.

Capture parsed declaration kind, introduced binding identities, assignment targets, mutability marker, inferred/declared type, scope, initialization state, and diagnostic span.

## 5. Candidate axes and implications

- **Separate immutable and mutable keywords (`let`/`var` or `const`/`var`):** intent appears at declaration, with a regular assignment form; users must choose at introduction.
- **One declaration keyword with per-binding mutability marker:** supports mixed destructuring and pattern bindings, but mutable syntax can be easier to overlook inside patterns.
- **Concise inferred declaration operator (`:=`):** reduces boilerplate, but can create context-dependent rules for shadowing/redeclaration and needs clear parsing beside assignment.
- **One declaration syntax plus optional annotation:** simpler grammar; omission/inference behavior remains explicit language policy.
- **Destructuring in declarations:** concise extraction and direct pattern composition; partial binding, refutable failure, and binding mutability require precise rules.
- **Initializer required:** avoids uninitialized storage states but can make cyclic construction/resource setup harder; explicit uninitialized values are a separate mechanism.
- **Uninitialized declaration plus definite initialization:** allows staged setup but requires flow analysis and careful capture/escape rules.
- **Zero-initialize by default:** convenient for some aggregate models but conflates “empty/zero” with “valid initialized invariant” unless types constrain it.

Scenario67 should decide what a binding's mutability controls; Scenario68 should decide object construction and definite initialization; Scenario74 should decide refutable failure. Syntax can expose these policies but cannot substitute for them.

## 6. Open questions and falsifiers

- Should immutable binding be the default and how is reassignment declared?
- Does a mutability marker belong to the binding keyword or each name within a destructuring pattern?
- Is there a concise inferred declaration form separate from assignment?
- What exact same-scope redeclaration/shadowing rules apply, and should any declaration form reuse an existing binding?
- Can a binding omit its initializer, and is the alternative zero initialization, definite initialization, or an explicit uninitialized state?
- Which patterns are allowed in declarations, and how is mismatch handled?
- Are multiple names bound atomically from a multi-result expression, and what happens if evaluation/conversion fails partway?
- Are local, property, namespace, and pattern bindings one grammar family or distinct declarations?

An explicit immutable/mutable keyword pair is weakened if AI-generated code frequently chooses `var` unnecessarily or initialization scope creates friction. A Go-style short declaration is weakened if authors confuse assignment with new binding or same-block reuse is hard to inspect. Pattern binding is weakened if diagnostics cannot point to partial mismatches or ownership is unclear. Required initialization is weakened if common resource construction patterns need awkward sentinel states; bare uninitialized declarations are weakened if definite-assignment proof and closure capture behavior become difficult to explain.

No binding syntax, initializer policy, or mutability marker is selected.

## 7. Sources and temporal limits

Primary documentation was consulted 2026-11-19. Rust Reference and Go specification, Swift 6.4 documentation, and Zig master are living references; pin exact versions for future parser/behavior tests. This report is not a type-system or initialization-conformance result.
