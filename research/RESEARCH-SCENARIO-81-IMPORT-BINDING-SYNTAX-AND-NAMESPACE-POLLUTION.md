# Research Scenario 81 — Import Binding Syntax and Namespace Pollution

**Status:** Evidence-linked prior-art comparison; no LLMLang import form selected  
**Research area:** RT-03 name resolution, RT-04 visibility, RT-11 dependency/build identity  
**Updated:** 2026-11-19

## 1. Question and scope

How should source-level imports bind modules and declarations into a file or lexical scope? This study isolates the import declaration's local name effects from Scenario 43's module/package boundaries, visibility defaults, initialization, cycles, and distribution graph.

Decision axes include qualified module imports versus unqualified symbol imports; selective lists and aliases; wildcard/on-demand forms; absolute versus relative paths; public re-export versus local binding; import placement/scope; and whether an import is a compile-time name binding, runtime loading operation, or both. This is specification-level prior art, not a ranking or LLMLang decision.

## 2. Prior-art comparison

### Rust: local aliases, grouped paths, glob imports, and re-export

Rust `use` declarations bind imported paths into scope. `as` changes the local binding, brace groups compact multiple imports, and `*` imports all importable names from a path. Named imports and local definitions may shadow glob-import names; ambiguous cases are restricted. `pub use` changes visibility and creates a re-export path. Path interpretation changed across Rust editions, so source edition affects import meaning and belongs in the language/toolchain identity.

Source: [Rust Reference — Use declarations](https://doc.rust-lang.org/reference/items/use-declarations.html).

### Go: file-scoped qualified package names and opt-in dot import

Go import paths are string literals. The default local package name comes from the imported package clause; an explicit package name aliases it. The package qualifier is local to the importing file. A dot import instead injects all exported package identifiers into that file's namespace. A blank import links a package for initialization effects without a usable local name. The specification treats an import as both a dependency relation and access to exported identifiers.

Source: [Go specification — Import declarations](https://go.dev/ref/spec#Import_declarations).

### Swift: module, submodule, or declaration imports

Swift's basic import makes a module accessible in the current file. A more specific form can import a submodule or a declaration, optionally using an import-kind such as `struct`, `func`, or `var`; in a specific-symbol form only that symbol, not its declaring module name, becomes available. The grammar does not provide a general alias or wildcard-import spelling in the cited reference.

Source: [Swift Language Reference — Declarations, Import Declaration](https://docs.swift.org/latest/documentation/the-swift-programming-language/declarations/).

### Java: single-type, on-demand, static, and module imports

Java makes a single type available under its simple name, or can import types on demand from a package/type. Separate static forms import members. Java SE 26 also specifies a module on-demand form for accessible public types in exported packages. Conflicting single imports can be compile-time errors, while on-demand imports can coexist and are resolved under shadowing/ambiguity rules. A Java import does not itself create a package alias.

Source: [Java Language Specification, Chapter 7 — Import Declarations](https://docs.oracle.com/en/java/javase/26/docs/specs/jls/jls-7.html).

### Python: qualified module binding, from-import, and relative paths

Python `import package.submodule` binds the top-level package name; `from module import name [as alias]` binds selected attributes directly, and `*` can bind all public names into the current namespace. Relative imports use leading dots in `from` form, with each additional dot moving one package level upward. The runtime import machinery is extensible, so import syntax may participate in dynamic loading; that mechanism is beyond static name-binding equivalence.

Sources: [Python Language Reference — Import statements](https://docs.python.org/3/reference/simple_stmts.html#import), [Python import system — Package Relative Imports](https://docs.python.org/3/reference/import.html#package-relative-imports).

## 3. Comparison matrix

| Dimension | Rust | Go | Swift | Java | Python |
|---|---|---|---|---|---|
| Default local binding | Imported final path segment | Package clause name | Module name | Type simple name | Top-level package name for qualified import |
| Selective names | Named `use`, grouped paths | No general member import; use package qualifier | Declaration/submodule import | Single-type/member imports | `from ... import ...` |
| Alias | `as` | Package alias | Not in cited grammar | No general alias | `as` |
| Wildcard | `*` glob; shadowing rules | Dot import injects exported names | No general wildcard syntax in cited grammar | On-demand types/static members | `from ... import *`, public names |
| Re-export | Public `use` | No general import re-export syntax | Access control/API export handled separately | Module `exports` differs from source import | Module attribute/export conventions, separate from import binding |
| Relative path | Edition/scoping-sensitive language paths | Import paths are strings; module tooling maps paths | Module/submodule paths | Canonical names | Explicit leading dots in `from` import |
| Binding scope | Block/item context for `use` | File block | File | Compilation unit declarations | Current local/module namespace |
| Import side effects | Not expressed by ordinary `use` binding alone | Blank import explicitly permits init-only dependency | Import declaration exposes module/declarations | Loading is separate from simple source binding | Import executes/loads module under runtime machinery |

These constructs differ in both syntax and semantic phase. “Wildcard” may mean lexical namespace injection, on-demand type lookup, or package access, so syntax similarity must not be mistaken for equivalent resolution behavior.

## 4. Discriminating fixtures

1. Two dependencies export the same name; compare qualified use, local alias, explicit selection, wildcard imports, shadowing, and ambiguity diagnostics.
2. Add a public facade that re-exports an implementation declaration. Rename/move the canonical declaration while preserving the facade path; identify which source/API keys change.
3. Put the same import in two files of one package, then change one file's alias. Measure name resolution and dependency invalidation locality.
4. Add case-variant and Unicode-confusable imported names, plus module names that resemble declaration names. Verify deterministic qualification and diagnostics.
5. Compare absolute and relative imports across file movement and package-root changes; determine whether path meaning changes silently.
6. Include an import used only for initialization and one dynamically resolved import. Separate binding dependencies from runtime loading/provider dependencies.
7. Test unused imports, import cycles, and imports that differ only by alias, grouping syntax, or order. Establish whether canonical source formatting can normalize them without changing semantics.

Record the resolved canonical declaration IDs, local binding IDs, import-path identity, visible namespace before/after import, diagnostic locations, and exact invalidation set.

## 5. Candidate axes and cross-area implications

- **Qualified module binding:** explicit namespace at each use; fewer collisions, potentially longer generated code and repeated path edits.
- **Selective direct binding:** concise use sites, but imported names can collide and become harder to attribute without tooling support.
- **Aliasable imports:** resolve collisions and support local naming; alias is a source binding and should remain distinct from canonical declaration identity.
- **Wildcard/on-demand imports:** reduce boilerplate, but may hide provenance, create ambiguity, and make API additions alter source resolution.
- **Explicit re-export:** supports stable facades, but the public path is API surface and must be tracked separately from definition identity.
- **Relative imports:** can improve nearby source navigation, but file/package movement may change meaning or require broad rewrites.
- **Import as runtime load:** supports dynamic systems, but source dependency declarations alone may not fully determine runtime behavior or cache keys.

Scenario 43 remains authoritative for package/module graph, visibility, cycles, initialization order, and dynamic service boundaries. Scenario 50 covers general scope/shadowing and name provenance; this study narrows to import forms and their resolution/build effects.

## 6. Open questions and falsifiers

- Should file imports introduce one module qualifier by default, or names directly?
- Are direct imports restricted to explicitly selected names? If glob forms exist, are they lexical or on-demand and how do collisions resolve?
- Is a source alias local to a file, block, compilation unit, or package?
- Are re-exports a first-class declaration with stable public identity and provenance?
- Are paths canonical package IDs, source-relative paths, or a combination with explicit markers?
- Does import syntax perform loading, or does a separate runtime declaration provide dynamic behavior?
- What tool-facing mapping keeps local names and re-export paths understandable to generators while preserving canonical identity?

Qualified-only imports are weakened if common APIs require pervasive boilerplate and generated source becomes difficult to review. Direct wildcard imports are weakened if dependency additions cause surprising resolution changes or diagnostics lose provenance. Alias and re-export designs are weakened if refactoring cannot preserve canonical identity and stable public paths. Relative paths are weakened if ordinary moves cause unclear semantic changes.

No import syntax, path form, wildcard policy, or re-export model is selected.

## 7. Sources and temporal limits

Official references were consulted 2026-11-19. Go, Rust, Swift, Python, and Java pages are living references; pin exact language/tool versions and editions for any conformance work. Findings describe specifications, not observed compiler behavior or performance.
