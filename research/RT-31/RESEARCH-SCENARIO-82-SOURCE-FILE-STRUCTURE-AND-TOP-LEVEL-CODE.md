# Research Scenario 82 — Source-File Structure and Top-Level Code

**Status:** Evidence-linked prior-art comparison; no LLMLang source-file grammar selected  
**Research area:** RT-03 source and declaration semantics, RT-04 visibility, RT-11 compilation units and build identity  
**Updated:** 2026-11-19

## 1. Question and scope

What may appear at file scope, in what order, and how does a source file join a package/module or compilation unit? This study focuses on the grammar and role of source files: header/package markers, imports, attributes/directives, declarations, top-level statements/expressions, and the relationship between files and logical modules.

Scenario 43 compares namespace/package/module boundaries, visibility, initialization, cycles, and dynamic discovery. Scenario 81 compares import binding forms. Scenario 82 asks how those elements are arranged in a source file and which file contributes which declarations or executable entry point. It does not select filesystem layout, package manager, module identity, initialization behavior, or entry-point spelling.

## 2. Prior-art comparison

### Go: explicit file header, then imports, then declarations

The grammar is `PackageClause { ImportDecl } { TopLevelDecl }`. A package clause begins every source file and identifies the package; multiple files with the same package name contribute declarations to the package. Imports belong to each file. File ordering can affect declaration/initialization details in bounded cases, so build inputs need deterministic file enumeration.

Source: [Go specification — Packages and source file organization](https://go.dev/ref/spec#Packages).

### Rust: every source file is a module, with attributes and items

A crate is the compilation/linking unit and contains a module tree. Each source file describes a module whose name/location comes from its parent module declaration or crate root. A file contains a sequence of items and may begin with attributes applying to its module; a shebang may precede content. Modules can also be inline within files. Thus physical file boundaries and logical module boundaries are related but not identical.

Sources: [Rust Reference — Crates and source files](https://doc.rust-lang.org/reference/crates-and-source-files.html), [Rust Reference — Modules](https://doc.rust-lang.org/reference/items/modules.html).

### Java: package/import prelude and compilation-unit alternatives

An ordinary compilation unit has an optional package declaration, zero or more imports, then zero or more top-level class/interface declarations. A modular compilation unit has imports optionally followed by a module declaration. Java SE 26 also defines compact compilation units, which can contain member declarations and methods as an implicit top-level class. The import scope is confined to the file/compilation unit. This gives Java a constrained conventional header plus a newer class-light source-file form.

Source: [Java Language Specification, Chapter 7 — Compilation Units](https://docs.oracle.com/en/java/javase/26/docs/specs/jls/jls-7.html#jls-7.3).

### Swift: top-level declarations in every file, executable code at the entry point

Every source file may contain top-level declarations. Top-level executable statements/expressions are a separate category and are allowed only in the executable's top-level entry point. At most one supported entry-point approach applies to an executable. Named top-level declarations are normally visible across source files in the same module, subject to access control. This separates file-level declaration convenience from executable startup code.

Source: [Swift Language Reference — Declarations, Top-Level Code](https://docs.swift.org/latest/documentation/the-swift-programming-language/declarations/).

### Kotlin: optional package header, file-local imports, declarations

A Kotlin file has zero or one package header; absent a header, it belongs to a root package. A package can span multiple files and is not tied to filesystem location, though matching folders are recommended. Imports are file-local. File contents are declarations, with multiple files treated together according to module compilation. The language specification distinguishes a module from a package and allows a package to be spread across modules.

Sources: [Kotlin Language Specification — Packages and imports](https://kotlinlang.org/spec/packages-and-imports.html), [Kotlin Documentation — Packages and imports](https://kotlinlang.org/docs/packages.html).

## 3. Comparison matrix

| Dimension | Go | Rust | Java | Swift | Kotlin |
|---|---|---|---|---|---|
| File/package association | Required package clause; same-package files contribute declarations | File defines module path in crate tree | Optional package declaration per compilation unit | Module is target-wide; file is source unit | Optional package header; root package if absent |
| Header order | Package, imports, declarations | Optional shebang/attributes, then items | Package, imports, top-level types; alternatives for module/compact units | Imports/declarations; no required package clause in cited grammar | Package header, imports, declarations |
| Import scope | File-local | Lexical/module scope of `use` | Compilation-unit-local | File-level | File-local |
| Top-level declarations | Types, values, functions, methods | Items and nested module declarations | Types in ordinary unit; members in compact unit | Declarations allowed in every file | Declarations across package files |
| Executable top-level statements | Not part of source-file declaration grammar | Statements occur in function/block; not general source-level executable content | Compact unit introduces implicit class/method form, not arbitrary statement script | Allowed in one program entry-point source | Top-level function/property declarations; no arbitrary file script in cited package spec |
| Physical layout coupling | Implementation/package tooling may constrain files | Module path can map to source path | Host/file-system conventions may constrain type files | Module target groups files | Package path and folder may differ |
| Unit boundary | Package from files | Crate containing module tree | Compilation unit and module constructs | Module/target | Module is compilation set; package is namespace |

## 4. Discriminating fixtures

1. Split one package/module's declarations across files, then move one file without changing its package header or logical module path. Compare name resolution, identity, and build inputs.
2. Move imports and declarations between files. Check whether imported names, package membership, visibility, and diagnostics remain local or leak across the group.
3. Permute file enumeration and declaration ordering. Check initialization order, macro/attribute processing, duplicate diagnostics, generated IDs, and reproducible builds.
4. Add a script-style top-level statement to a library file, an executable file, and a test file. Identify which forms are allowed and how exactly one entry point is selected.
5. Place compiler attributes/directives, package markers, imports, and declarations in invalid orders; record parser recovery and source locations.
6. Compare one-file and multi-file forms of the same module/package. Measure whether formatting, source generation, and incremental compilation preserve canonical semantic structure.
7. Test file/package names that disagree with directory names, root/unnamed-package behavior, and duplicate package headers.

For each fixture, record file identity, logical package/module identity, compilation-unit membership, import bindings, declaration visibility, source-map spans, and invalidation scope.

## 5. Candidate axes and implications

- **Strict header grammar:** fixed package/import/attribute/declaration order; simplifies parsers and makes metadata placement clear, but may constrain generated code and inline module organization.
- **Declarations-only file scope:** prevents startup work from hiding among declarations; requires explicit entry-point and initialization mechanisms.
- **Single executable entry file with permitted top-level code:** supports concise scripts while keeping library files declarative; entry-file identity and duplicate-entry diagnostics become build inputs.
- **Package header as file membership:** makes grouping explicit and independent of the directory tree; duplicated headers across files and edits can be noisy.
- **Directory-derived grouping:** lowers repetitive headers but makes filesystem moves potentially semantic and can complicate generated/virtual sources.
- **One file equals one module:** clear mapping and edit scope, with nested/inline modules still possible; may make API grouping track file refactors.
- **Multi-file package/module grouping:** supports cohesive declaration scopes but requires clear file-local imports and deterministic compilation behavior.

The grammar does not by itself determine initialization order, visibility, or import semantics. Those remain cross-linked to Scenario43 and Scenario81.

## 6. Open questions and falsifiers

- Should every file declare package/module membership, or can it be inferred from its parent/build target/path?
- Are imports required to precede declarations, and are they local to a file or shared across a compilation unit?
- Are file attributes/directives distinct from item declarations and comment directives?
- Is arbitrary top-level executable code allowed? If yes, in how many files and under what entry-point rule?
- Can a source file contribute to multiple logical namespaces or compilation units?
- Which ordering-sensitive semantics must be prevented, specified, or made irrelevant to file enumeration?
- How should generated/virtual source files participate in a path-independent module/package identity?

Strict headers are weakened if generated or interactive workflows need pervasive boilerplate and cannot create source fragments safely. Permissive top-level execution is weakened if library imports trigger hidden or order-sensitive behavior. Directory-derived package membership is weakened by meaningful path moves and virtual sources. Explicit package headers are weakened if multi-file edits routinely drift or produce inconsistent group membership.

No source-file grammar, file/package mapping, or top-level execution rule is selected.

## 7. Sources and temporal limits

Official language specifications and manuals were consulted on 2026-11-19. Java SE 26 and Kotlin specification 1.9-rfc+0.1 are versioned references; the other cited documentation can evolve. This is spec-level analysis, not an experiment on compiler/parser behavior.
