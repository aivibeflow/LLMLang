# Research Scenario 84 — Function Signatures and Call Surface

**Status:** Evidence-linked prior-art comparison; no LLMLang function declaration or call syntax selected  
**Research area:** RT-03 declarations and calls, RT-04 type/effect/resource signatures, RT-11 API identity  
**Updated:** 2026-11-19

## 1. Question and scope

How do a function declaration and its call surface express parameter identity, argument labels, return values, defaults, variadic arguments, receiver/method status, and body omission? The study concentrates on surface signatures and the source API they create.

It does not revisit argument evaluation order (Scenario77), higher-order function types (Scenario58), closures (Scenario56), generic dispatch (Scenario42), or full error/effect/resource typing. Those features can add signature dimensions and should later be checked against the baseline chosen here.

## 2. Prior-art comparison

### Rust: explicit parameter patterns and output type; method receiver is a parameter form

Rust uses `fn name(pattern: Type, ...) -> Output { ... }`. The output type may be omitted, in which case it is unit. Parameter patterns can destructure inputs. An initial `self` parameter marks an associated method; C variadics are a constrained foreign-interface form. Ordinary Rust signatures do not have named call-site arguments or default parameter values. A function body may return its tail expression implicitly; bodyless declarations appear in traits or extern blocks.

Source: [Rust Reference — Functions](https://doc.rust-lang.org/reference/items/functions.html).

### Go: typed parameter/result lists, grouped names, variadics, and receiver syntax

Go writes `func name(params) results { ... }`. Parameter and result names are optional, and within a list names must be consistently present or absent; a single unnamed result may omit parentheses. A final `...T` parameter is variadic. A method is declared using a receiver parameter list before the method name. A body can be omitted for external implementations. Calls are positional and there are no default parameters or argument labels.

Source: [Go specification — Function types and declarations](https://go.dev/ref/spec#Function_types).

### Swift: argument label and body name are separately declared

Swift uses `func name(parameters) -> Return { ... }`; a `Void` result can be omitted. Every parameter is typed. Each parameter has a name used in the body and an argument label used at the call site; by default they match, but a custom label or `_` can change caller syntax. Default values allow callers to omit arguments. Parameter modifiers include `inout`, `borrowing`, and `consuming`. Protocol method declarations omit bodies and cannot specify default parameter values.

Sources: [Swift Language Reference — Function Declaration](https://docs.swift.org/latest/documentation/the-swift-programming-language/declarations/), [Swift Language Guide — Functions](https://docs.swift.org/latest/documentation/the-swift-programming-language/functions/).

### Java: method formal parameters, return/void, overloads, and final varargs

Java methods declare a result type or `void`, a method name, and formal parameters inside a class/interface context. Arguments are positional; overload resolution uses method name and parameter types (return type alone does not distinguish overloads). At most one variable-arity parameter is permitted and it must be last. Constructors use a separate declaration form, and abstract/native methods can omit a body according to their declaration context. Java has no parameter-name labels or default argument values in the language syntax.

Sources: [Java Language Specification, Chapter 8 — Method Declarations](https://docs.oracle.com/en/java/javase/26/docs/specs/jls/jls-8.html#jls-8.4), [Java Language Specification, Chapter 8 — Variable Arity Parameters](https://docs.oracle.com/en/java/javase/26/docs/specs/jls/jls-8.html#jls-8.4.1).

## 3. Comparison matrix

| Dimension | Rust | Go | Swift | Java |
|---|---|---|---|---|
| Declaration form | `fn f(x: T) -> R` | `func f(x T) R` | `func f(x: T) -> R` | `R f(T x)` in type/member context |
| Parameter name in body | Pattern bindings | Optional parameter names | Required parameter name | Required formal parameter name |
| Call-site argument label | Positional; no label syntax | Positional | Separate label; defaults to parameter name; can be `_` | Positional |
| Return form | Optional `-> Type`; omission means unit; tail expression | Optional result; one unnamed result can be unparenthesized | Optional `-> Type`; omission means `Void` | Required result type or `void` |
| Default parameters | No general source feature | No | Yes | No |
| Variadic | Constrained C variadic | Final `...T` parameter | Variadic parameters use dedicated syntax/type lowering | Final `T...`, at most one |
| Method/receiver | `self` parameter / associated function | Receiver precedes method name | Declaration context makes it a method | Member declaration within class/interface |
| Overloading | No same-scope overload set as general surface model | No function overloading | Overloads are supported | Overloads are supported; return type alone is insufficient |
| Bodyless declaration | Traits/extern contexts | External implementation | Protocol requirements | Abstract/native/interface contexts |

## 4. Discriminating fixtures

1. Declare a three-parameter API with labels distinct from implementation names. Change only the body variable names; then change only the labels. Record source compatibility and API identity consequences.
2. Compare positional, named/labeled, mixed, reordered, duplicate, and omitted arguments. Reject or define repeated labels and label/name collisions.
3. Add defaults to parameters at the beginning, middle, and end; change a default after clients are compiled. Determine whether defaults are evaluated at the caller or callee and what artifact clients bind to.
4. Compare one result, multiple results/tuple result, unit/void, optional result syntax, and inferred result. Check signature readability and call destructuring separately from runtime semantics.
5. Add zero, one, and many variadic arguments; compare typed list/array expansion with foreign C varargs and overload selection.
6. Express a method/receiver both as a contextual member declaration and as an explicit receiver parameter. Compare generic constraints, extension methods, and first-class function values.
7. Rename parameter names while retaining external labels; rename external labels while retaining implementation names. Measure source/API breaks and diagnostic precision.
8. Test declarations without bodies, forward declarations, protocol/interface requirements, and foreign implementations. Preserve the same signature identity across declaration and implementation.

For each fixture, record declared signature identity, implementation-local parameter bindings, call-site labels, default semantics, overload candidate set, diagnostics, and recompilation/invalidation scope.

## 5. Candidate axes and implications

- **One parameter name for body and call:** compact and predictable; implementation clarity and caller phrasing are coupled.
- **Separate external label and body name:** supports sentence-like call sites and implementation refactors; adds a second name users and tools must track.
- **Positional-only calls:** compact, easy to generate, and stable under parameter rename; long calls communicate less intent and reordering is unsafe.
- **Named calls:** improve argument attribution and permit reordering; labels become stable API surface, overload/default interactions require precise resolution.
- **Default arguments:** reduce overload/helper boilerplate; changing defaults can change call behavior and cross-module callers may bake values at a different phase.
- **Multiple results versus tuple/result object:** multiple-result syntax can be concise, but composing, storing, and abstracting signatures may need tuple-like values.
- **Contextual method receiver versus explicit parameter:** affects method lookup, extensions, generic constraints, trait/object dispatch, and function-value conversion.
- **Overloads versus one name per declaration:** overloads create a candidate-resolution relation; explicit distinct names simplify selection and dependency attribution.
- **Parameter patterns versus simple identifiers:** destructuring is concise, but can complicate diagnostics, documentation names, and stable parameter identity.

These are separate from evaluation order: a label changes argument association, while evaluation order determines when expressions run. The two must be tested together later, but should not be collapsed into one rule.

## 6. Open questions and falsifiers

- Are call-site labels desirable, and are they distinct from names used inside function bodies?
- Are named arguments reorderable, or must they retain declaration order even when labeled?
- What compatibility promise applies to changing implementation parameter names, external labels, and defaults?
- Are defaults expressions evaluated by the caller, callee, or declaration environment, and are they effectful?
- Should a function return one value, unit, a tuple, or a syntactic multiple-result list?
- Is variadic syntax for ordinary typed collections sufficient, or is a separate foreign ABI variadic form required?
- Are methods a syntactic declaration context, an explicit receiver parameter, or both?
- What does overload resolution do when defaults or variadic candidates produce equal matches?
- Can parameters use patterns, or should patterns occur only in the function body/caller binding?

Single-name parameters are weakened if public APIs repeatedly need awkward caller prose or parameter renames break clients. Separate labels are weakened if generated source and diagnostics cannot explain the two names reliably. Default arguments are weakened if edits unpredictably alter already-built clients or interact with effects. Overloads are weakened if resolution becomes context-sensitive and hard to attribute. Positional-only calls are weakened if real workloads have many same-typed arguments and reviews often miss swaps.

No function signature, argument-label, default, return, variadic, or method declaration syntax is selected.

## 7. Sources and temporal limits

Primary references were consulted on 2026-11-19. Swift docs describe version 6.4; Rust Reference and Go spec are rolling; Java references are Java SE/JLS 26. Pin versions before conformance studies. This document compares stated language rules and does not make performance claims.
