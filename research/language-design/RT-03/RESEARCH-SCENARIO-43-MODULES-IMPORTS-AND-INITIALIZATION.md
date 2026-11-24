# Research Scenario 43 — Modules, Imports, and Initialization

**Status:** Evidence-linked prior-art comparison; no LLMLang module system selected  
**Research area:** RT-03 name resolution and initialization, RT-04 visibility, RT-11 dependency/build identity  
**Updated:** 2026-11-19

## 1. Question and scope

How should LLMLang group declarations into namespaces and distribution units, expose APIs across boundaries, resolve imports, and handle initialization with observable effects?

Separate these decisions:

1. Namespace and source organization: are modules declared independently of files, directories, or packages?
2. Visibility: private-by-default versus public-by-default; item, file, package, or module granularity; explicit re-export.
3. Dependency boundaries: source import, compiled module interface, distribution package, and versioned dependency may be distinct units.
4. Cycles: whether module/package import cycles are permitted, rejected, or require strongly connected compilation groups.
5. Initialization: whether module-level executable initialization is supported; ordering, side effects, failure, concurrency, and cycle behavior.
6. Dynamic discovery: whether services/plugins are linked statically, declared as imports, or discovered at runtime under an explicit capability.

This is a documentation-based comparison of Rust, Go, Swift, and Java's module system. It does not select a package manager, lockfile, macro system, filesystem layout, or plugin ABI, and does not measure incremental build behavior.

## 2. Prior-art comparison

### Rust: nested modules, privacy, and explicit re-export paths

Rust modules form nested namespaces and privacy boundaries. Items are private by default; public visibility can be restricted by ancestor visibility. A public use declaration can re-export a name through a different public path, but unresolved or cyclic re-export chains are compile-time errors. Source files can host modules, yet module identity is declared through the language rather than being merely a directory convention.

This gives API authors control over a stable public path independent of private implementation organization. The cost is that name resolution and visibility depend on the module tree and re-export chain; an import graph used for build or semantic identity must distinguish canonical definitions from public aliases.

Sources: [Rust Reference — Visibility and privacy](https://doc.rust-lang.org/reference/visibility-and-privacy.html), [Rust Reference — Use declarations](https://doc.rust-lang.org/reference/items/use-declarations.html), [Rust Reference — Modules](https://doc.rust-lang.org/reference/items/modules.html).

### Go: package is the shared declaration and initialization unit

Go packages combine declarations across source files sharing a package clause. Imports grant access to exported identifiers; capitalization determines exported status. Package imports create an acyclic initialization order: imported packages initialize before importers, and package-level variables and init functions run sequentially. Within a package, variable initialization follows dependency analysis; initialization cycles make the program invalid. The specification notes that file ordering supplied to the compiler affects cross-file declaration order and recommends lexical file ordering for reproducibility.

This makes package boundaries easy to connect to compilation and initialization, but package-wide initialization is executable behavior. A deterministic build/runtime model must pin source-file ordering and account for transitive lexical dependencies, not merely explicit import statements.

Sources: [Go specification — Packages and program initialization](https://go.dev/ref/spec#Packages), [Go specification — Program initialization and execution](https://go.dev/ref/spec#Program_initialization_and_execution), [Go modules reference](https://go.dev/ref/mod).

### Swift: module as distribution/access boundary, with multiple visibility levels

Swift defines a module as a code distribution unit that can be imported by another module. Access control is described across declarations, source files, modules, and packages, with open, public, internal, fileprivate, and private levels. Public exposure is explicit; internal is the default for module-internal declarations. This makes API visibility more granular than a single exported/unexported bit.

The richer access lattice can encode library and package encapsulation, but API availability and implementation accessibility must be analyzed against the client's module and package context. Swift's module boundary is both a namespace/access boundary and a distribution interface; package management and module maps introduce additional interoperability concerns.

Sources: [Swift Language Guide — Access Control](https://docs.swift.org/latest/documentation/the-swift-programming-language/accesscontrol/), [Swift Package Manager — Introducing Packages](https://docs.swift.org/latest/documentation/packagemanagerdocs/introducingpackages/).

### Java: explicit readability and exports graph

The Java Platform Module System separates package namespaces from modules. A module declaration states dependencies with requires and exposes packages with exports; opens controls reflective access separately. Module resolution constructs a readability graph, and access is checked across that graph. Service-use/provision directives support provider discovery at a module boundary.

This makes dependency visibility and reflective access explicit, and allows static module readability to be separated from dynamic service discovery. It adds a second graph beyond packages/classes, and the correctness of access claims depends on module resolution and runtime layer configuration.

Sources: [Java Language Specification, Chapter 7 — Packages and Modules](https://docs.oracle.com/en/java/javase/26/docs/specs/jls/jls-7.html), [Java SE Module API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/lang/Module.html).

## 3. Comparison matrix

| Dimension | Rust modules | Go packages | Swift modules/packages | Java modules |
|---|---|---|---|---|
| Declaration grouping | Nested modules; source files can declare module structure | Multiple files share one package declaration/name and package block | Module is a distribution/import unit; package is also a source grouping in SwiftPM | Packages group types; modules group packages |
| Default visibility | Private, with ancestor restrictions | Exported identifiers follow capitalization; unexported remain package scoped | Internal by default; multiple explicit access levels | Package access plus public/protected/private; module exports gate cross-module access |
| Public API aliases | Explicit public re-exports | Import path/package name; no general re-export declaration | Public declarations and module imports | Exported packages and module readability |
| Dependency graph | Imports/names/re-exports; compile grouping is toolchain-defined | Package import DAG; initialization follows imports | Module/package graph and build targets | Readability graph resolved from module declarations |
| Initialization | No Go-style package init sequence as a general source-level module feature | Ordered package variables and init functions; cycles invalid | Global/static initialization semantics require separate language/runtime analysis | Class initialization is runtime-triggered; service loading is a distinct dynamic mechanism |
| Runtime discovery | Usually explicit linking or application mechanisms | Side-effect imports can trigger package init | Package/framework mechanisms | Services can be declared and discovered through module services |
| Build/cache question | Canonical definition versus re-export path | Package-wide files, init dependencies, and file order | Module interface and access context | Readability/resolution plus exports/opens and runtime module layer |

These are not directly equivalent constructs. In particular, Java's module graph and Go's package graph occur at different layers, and dynamic service discovery is not a source import.

## 4. Discriminating fixture

Create a small library with private implementation modules, a public facade that re-exports selected names, two source files contributing to one package/module, and a test-only access path. Add an initialization scenario with two variables whose initializer dependencies are transitive through a helper function, then introduce a cycle. Add two consumers: one statically imports the public API, and one discovers a plugin/service at runtime.

For each candidate, record:

- The canonical declaration identity and every public path that reaches it.
- Which source edits change the exported interface, package/module identity, or only an internal body.
- Whether import cycles are syntactically or semantically allowed and where diagnostics point.
- Whether module-level initialization exists; its ordering, error behavior, side effects, and determinism.
- Which exact dependencies a build graph records, including transitive initializer references and dynamic service providers.
- Whether consumers can use private/friend/test visibility without widening production API.

Run implementation experiments only after pinning compiler/tool versions and file enumeration order. Compare clean and incremental builds across a private implementation edit, public re-export edit, new initializer dependency, and provider registry edit.

## 5. Cross-area implications and open hypotheses

- A module is often simultaneously a namespace, access boundary, compilation interface, and distribution unit. These roles need not share one identity or version boundary.
- Public re-exports mean a source path can be part of API compatibility even when the canonical declaration is unchanged.
- Executable initialization turns imports into behavior dependencies. A complete dependency graph may need lexical/transitive initializer references, not just symbol references.
- Prohibiting import cycles simplifies topological initialization and separate compilation, but may pressure API factoring or require explicit mutually recursive groups.
- Runtime discovery weakens a fully static import graph; safe caching may require provider-set/configuration identity and an explicit capability or deployment manifest.
- These are research implications, not LLMLang rules. The sources do not establish which grouping or hashing boundary is best for LLMLang.

## 6. Next research and falsifiers

Prototype declaration resolution and dependency extraction for the fixture in two languages with different module/package models. Include re-export aliases, test/friend visibility, cyclic imports, transitive initializer reads, and dynamic providers. Verify that changing an internal body does not invalidate unrelated consumers where the public interface is unchanged, while any changed observable initialization or provider set invalidates the appropriate actions.

The Go-style package initialization model is weakened if deterministic initialization depends on unspecified file order or hides costly side effects. A strict no-initializer model is weakened if ordinary library use cases require ad hoc global registries or unsafe lazy state. Rust-style re-exporting is weakened if API aliases make rename/identity tracking unreliable. A Java-style explicit module graph is weakened if its configuration burden exceeds the access control and deployment benefits for target workloads.

No LLMLang namespace syntax, package boundary, visibility default, initialization policy, or plugin model is selected.

## 7. Sources and temporal limits

Official specifications and language documentation were consulted 2026-11-19. Go and Swift online manuals are rolling documentation; pin language/toolchain versions for experiments. Java references are JLS/Java SE 26 pages. This report does not claim implementation-specific compilation or runtime costs.

## Public-interface integration (2026-11-24; proposed)

Follow-up: resolve scoped exported qualified names and re-exports to exact public operation revisions before selecting an implementation. Pin the catalog and record negative/ambiguous lookup dependencies; no implicit latest resolution at execution. Import/export compatibility, module initialization ordering and provider conformance are independent checks. Compare alias-preserving rename, cyclic re-exports, conflicting namespace entries and providers with different initialization obligations.

Related: [Public interfaces and verified contract refinement](../../semantic-representation/RT-05/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This is a candidate follow-up; it does not change accepted rules or previously reported evidence.
