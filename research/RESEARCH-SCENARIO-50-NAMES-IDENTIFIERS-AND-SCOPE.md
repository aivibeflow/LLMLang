# Research Scenario 50 — Names, Identifiers, and Scope

**Status:** Evidence-linked prior-art comparison; no LLMLang name-resolution policy selected  
**Research area:** RT-03 core semantics, RT-04 static semantics, RT-06 dependency extraction and invalidation  
**Updated:** 2026-11-19

## 1. Question and scope

How do declarations introduce names, when do those names become visible, how are references resolved across nested scopes and modules, and when may an inner binding shadow an outer one? These questions are related but independent:

1. Identifier spelling and reserved words.
2. Scope boundaries (blocks, functions, modules, packages, labels, and type declarations).
3. Visibility start point and declaration-order independence.
4. Shadowing and same-scope redeclaration.
5. Separate namespaces for types, values, macros, labels, and modules.
6. Imports, prelude/built-ins, qualification, and ambiguity handling.
7. Static versus runtime lookup and consequences for IDEs, dependency graphs, and incremental recompilation.

This report compares official Rust, Go, Python, and Zig references. It describes documented rules and design consequences, not a recommendation or a complete implementation experiment.

## 2. Prior-art comparison

### Rust: lexical scopes, multiple namespaces, generally permitted shadowing

Rust resolves names at compile time and partitions names into namespaces so, for example, a type and value can share a spelling. Blocks establish scopes; local `let` bindings take effect after their declaration, while items can be visible throughout their containing module or block. Pattern bindings can shadow many names, subject to documented exceptions. Imports and prelude names participate in resolution, and name resolution must account for paths, namespaces, visibility, and ambiguity.

This permits concise local transformations and ergonomic imports, but makes a single “nearest name wins” rule insufficient: the syntactic context selects a namespace, and exceptions/ambiguities must be specified. Tooling must show which declaration a use denotes.

Sources: [Rust Reference — Names and name resolution](https://doc.rust-lang.org/reference/names.html), [Rust Reference — Name resolution](https://doc.rust-lang.org/reference/names/name-resolution.html), [Rust Reference — Scopes](https://doc.rust-lang.org/reference/names/scopes.html).

### Go: precise lexical blocks, declaration-specific visibility, constrained short redeclaration

Go defines explicit and implicit blocks, including package, file, function, and control-statement blocks. It states the source-text interval in which each declaration is visible. Local variable/constant scope starts at the end of its declaration; inner declarations may shadow outer identifiers. A short variable declaration may redeclare an existing variable only in the same block (or the function parameter scope), with the same type, and only if at least one non-blank name is new. Labels have a distinct scope and do not conflict with non-label identifiers.

The specification gives implementers and readers precise scope boundaries and preserves the common `x, err := ...` pattern without making arbitrary same-scope redeclaration legal. The special rule is useful but adds a syntax-specific exception to teach and implement.

Sources: [Go specification — Blocks](https://go.dev/ref/spec#Blocks), [Go specification — Declarations and scope](https://go.dev/ref/spec#Declarations_and_scope), [Go specification — Short variable declarations](https://go.dev/ref/spec#Short_variable_declarations).

### Python: statically classified local bindings with runtime lookup in enclosing environments

Python defines code blocks and determines whether a name is local by scanning binding operations in the block, absent `global` or `nonlocal` declarations. A local binding can therefore classify the name as local throughout the function even before its assignment executes, producing an unbound-local error rather than falling back to an outer binding. Free-variable lookup proceeds through enclosing function scopes and globals/built-ins at runtime; class blocks and dynamic `exec`/`eval` have special rules.

This supports dynamic namespaces and closures, but has a surprising temporal edge: adding an assignment later in a function can change the meaning of an earlier read. Static dependency analysis and refactoring must model block-wide binding classification and runtime environments, not just lexical declaration position.

Sources: [Python Language Reference — Execution model](https://docs.python.org/3/reference/executionmodel.html), [Python Language Reference — Naming and binding](https://docs.python.org/3/reference/executionmodel.html#naming-and-binding).

### Zig: lexical lookup with outer-scope shadowing prohibited

Zig documents lexical scopes and states that variables may not shadow identifiers from an outer scope. The language reference explains this policy as allowing a reader to rely on an identifier consistently denoting the same declaration within the scope where it is defined. This moves certain accidental-shadowing cases from review convention to compile-time diagnostics.

The rule improves local name stability but can require renaming short-lived bindings and may interact with nested blocks, declarations of different kinds, imports, and generated code; the exact collision classes should be checked against a pinned compiler version.

Source: [Zig Language Reference — Variables](https://ziglang.org/documentation/master/#Variables).

## 3. Comparison matrix

| Dimension | Rust | Go | Python | Zig |
|---|---|---|---|---|
| Resolution model | Compile-time, context-sensitive namespaces and paths | Compile-time lexical blocks and package/file scopes | Block-wide local classification; enclosing/global lookup at runtime | Lexical compile-time resolution |
| Local visibility start | After declaration for `let`; items have item-specific scope | Precisely specified per declaration; local variable scope starts after declaration | Local classification covers whole block; value binding happens on execution | Lexical declaration rules; pin compiler for edge cases |
| Outer shadowing | Usually allowed, with exceptions | Allowed in nested scopes | Local binding masks outer name within block | Variable shadowing outer identifiers prohibited |
| Same-scope rebinding | Duplicate item names in same namespace generally rejected; local bindings may shadow | Short declaration has narrow redeclaration exception | Rebinding is ordinary assignment; declaration distinction is absent | Check exact declaration category and version |
| Namespace separation | Multiple namespaces (e.g. type/value/macro/lifetime) | Labels are explicitly distinct; other declarations share identifier rules | Runtime namespaces include local/enclosing/global/builtins; class behavior is special | Contextual declaration categories; reference rules require compiler/spec detail |
| Imports/prelude | Imports and layered preludes participate in resolution | Imports introduce package names; package/file blocks are specified | Module globals and built-ins participate in lookup | Namespace imports; shadow prohibition aids name stability |
| Tooling consequence | Resolve by namespace, scope, path and visibility | Derive exact declaration intervals and implicit blocks | Track block-wide bindings and runtime environment | Diagnose prohibited collisions early |

## 4. Discriminating fixtures

Create a shared set of snippets and record the binding identity for every reference, accepted/rejected status, and diagnostic:

1. Read a name before and after a local declaration while an outer binding exists.
2. Declare a local function/type with the same spelling as an outer value; test use in expression and type contexts.
3. Nest blocks and test same-scope duplicate declarations versus inner shadowing.
4. Test loop/case/pattern bindings, closures, labels, and the boundary between a function body and nested function.
5. Test import aliases, re-exports, prelude/built-in shadowing, qualified names, and ambiguous candidates.
6. For Go-like short declarations, test all-existing names, one new name, blank identifiers, differing types, and nested block behavior.
7. For Python-like assignment classification, add a later assignment and compare an earlier read with and without that assignment; include `global`/`nonlocal` and class scope.
8. Capture loop variables in delayed closures/tasks, including per-loop versus per-iteration binding identity and language-version changes.
9. Expand a macro that introduces a temporary and refers to a helper; test collisions with caller locals, repeated expansion, and renamed imports under hygienic and unhygienic expansion.
10. Rename or move a declaration and compare the complete use graph, diagnostics, semantic identity, and incremental invalidation set.

The experiment should distinguish source-order resolution from whole-block binding classification and runtime dictionary lookup; report parse tree, scope tree, namespace, declaration identity, and invalidated dependents.

## 5. Cross-area implications and open hypotheses

- Shadowing is a readability and refactoring trade-off, not merely a parser rule. Allowing it can make local transformations concise but can redirect a use silently; prohibiting it gives stronger name stability but can constrain idiomatic code.
- Scope rules should be stated separately for local bindings, items, types, labels, patterns, and imports. One generic “scope” definition hides important differences.
- Distinct namespaces reduce naming collisions but make resolution depend on syntactic context and enlarge diagnostics/tooling requirements.
- Declaration-order-independent items simplify mutual references and module organization, while sequential locals make dataflow and uninitialized-use reasoning more direct.
- Whole-block binding classification or runtime lookup complicates static dependency extraction, rename safety, and cache invalidation; the exact name-to-declaration edge must be part of semantic dependency records.
- Prelude and implicit names reduce boilerplate but can change resolution across language/library versions. Explicit imports and qualified references improve provenance at a source-verbosity cost.
- Loop capture policy determines whether closures share a mutable loop variable or capture a fresh per-iteration binding; the Go 1.22 transition demonstrates that this is a versioned semantic compatibility issue, not just a style concern.
- Macro hygiene is a separate resolution dimension: generated identifiers may resolve at definition site, call site, or through syntax-context marks. Macro expansion and rename tools need explicit provenance for generated names.
- The compiler should offer a machine-readable resolution result (source span → stable declaration identity, namespace, and expansion provenance) if LLMLang's semantic graph and IDE refactoring are to share one name-resolution interpretation.

No LLMLang shadowing policy, namespace structure, prelude policy, or declaration-order rule is selected.

## 6. Next research and falsifiers

Implement a minimal resolution model for sequential locals, block-hoisted items, imported names, separate type/value namespaces, nested closures, loop captures, and macro expansion provenance. Run the shared fixtures under at least two candidate profiles: (A) Rust-like shadowing with explicit namespaces and (B) Zig-like no-shadowing with one uniform local namespace; retain Go-style limited same-scope redeclaration as a separate vector. Measure source churn, collisions, diagnostic clarity, use-graph completeness, and invalidation precision on representative edits. Add a Python-style dynamic-lookup profile only if a dynamic namespace is a stated product requirement.

The no-shadow vector is weakened if routine nested code accumulates awkward names or renames. The permissive vector is weakened if blind rename/refactor tasks frequently redirect references or require hidden namespace knowledge. Any profile is weakened if imports, prelude changes, or declaration-order edits produce dependencies not represented in the semantic graph.

## 7. Sources and temporal limits

Official language references were consulted 2026-11-19. Rust and Zig master/reference pages are rolling; Go's specification reflects its stated version; Python's execution model is versioned. Pin compiler/interpreter versions and capture exact fixtures before turning these rules into normative LLMLang requirements.
