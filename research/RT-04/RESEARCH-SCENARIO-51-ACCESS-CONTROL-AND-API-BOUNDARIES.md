# Research Scenario 51 — Access Control and API Boundaries

**Status:** Evidence-linked prior-art comparison; no LLMLang visibility or export policy selected  
**Research area:** RT-03 module semantics, RT-04 type/API boundaries, RT-06 dependency graph  
**Updated:** 2026-11-19

## 1. Question and scope

Which declarations can be referenced from which parts of a program, how are package/module interfaces assembled, and how should APIs prevent accidental exposure of implementation details? Keep these distinct:

1. Lexical scope: whether a name denotes a declaration at a source location.
2. Access control: whether the resolved declaration is accessible from that context.
3. Export/API membership: whether the declaration belongs to a package's externally consumable interface.
4. Re-export: whether a module may expose a name whose canonical definition is elsewhere or locally hidden.
5. Type leakage: whether a public signature may mention a less-visible type.
6. Source organization: package, module, file, nested declaration, and workspace boundaries.
7. Compatibility: which changes to visibility or exports are source/API breaking and what dependency edges they create.

This report compares official Rust, Go, and Swift references and relates them to the module/import comparison in Scenario 43. It is not normative and selects no LLMLang policy.

## 2. Prior-art comparison

### Rust: path-based module privacy and explicit visibility

Rust items are private by default. `pub` and restricted forms such as `pub(crate)` or `pub(in path)` expose items across selected module boundaries. A public `use` can re-export an item under a chosen path, including cases where the canonical path is private. Visibility checks are separate from name resolution: an item can resolve but still be inaccessible from the current context.

This gives libraries granular API construction and allows modules to hide implementation paths. The trade-off is that users and tooling must reason about a hierarchy of modules, visibility scopes, re-export paths, and effective visibility rather than a single public/private bit.

Sources: [Rust Reference — Visibility and privacy](https://doc.rust-lang.org/reference/visibility-and-privacy.html), [Rust Reference — Use declarations](https://doc.rust-lang.org/reference/items/use-declarations.html).

### Go: package boundary with export encoded in identifier spelling

Go's package is the principal visibility boundary. An identifier is exported when it begins with a Unicode uppercase letter and is declared at package scope or is a field/method name; other names cannot be selected from another package. Importing a package provides access to its exported identifiers. Package-qualified selection makes the origin of imported names explicit, while the spelling convention makes export status visible in the identifier itself.

This makes the common cross-package rule easy to recognize and avoids a separate modifier for ordinary exports. It couples public API status to identifier spelling, offers less granular nested access control, and requires package paths to distinguish unexported names in tooling/type identity.

Sources: [Go specification — Exported identifiers](https://go.dev/ref/spec#Exported_identifiers), [Go specification — Import declarations](https://go.dev/ref/spec#Import_declarations).

### Swift: layered package, module, file, and declaration access

Swift provides `open`, `public`, `package`, `internal`, `fileprivate`, and `private` levels. These range from subclassable/overridable across modules (`open`) through package and module use, file-level access, and enclosing-declaration access. The default is generally `internal`. Swift enforces that a declaration cannot be exposed more broadly than the types appearing in its public-facing signature; a public function cannot leak a private return type.

This offers fine-grained boundaries suited to frameworks and multi-module packages. More levels and defaults increase the number of API design choices, and access-level inference must be included in diagnostics and interface generation.

Source: [Swift Language Guide — Access Control](https://docs.swift.org/latest/documentation/the-swift-programming-language/accesscontrol/).

## 3. Comparison matrix

| Dimension | Rust | Go | Swift |
|---|---|---|---|
| Main external boundary | Crate/module hierarchy | Package | Module, with package/file/declaration layers |
| Default visibility | Private | Export determined by name spelling; package members internal to package | Internal |
| Granularity | Module paths and restricted `pub` | Package boundary for identifiers | `open`, `public`, `package`, `internal`, `fileprivate`, `private` |
| Public aliasing | Public `use` re-exports paths | Package-qualified names; aliases bind imported package name | Module imports and declarations with access modifiers |
| Signature leakage | Visibility and privacy constraints apply across paths | Exported declarations/types participate in package API; unexported names are package-scoped | Public API cannot depend on less-accessible types |
| Refactoring challenge | Preserve path/access/re-export behavior | Preserve exported spelling and package selectors | Preserve effective access levels and signature availability |
| Main design cost | Rich visibility graph and path reasoning | Naming convention encodes API status, coarse granularity | Many levels and access-level propagation rules |

## 4. Discriminating fixtures

1. Define a private helper type used in a public function argument/return type; record legality and diagnostics.
2. Re-export a dependency type/function through a facade while hiding its defining module; test API identity and documentation paths.
3. Split one module/package across multiple files and move a declaration between files; test visibility and source compatibility.
4. Introduce a submodule and compare private, package/module, and restricted-to-parent access.
5. Rename a public declaration and update its canonical path while preserving a compatibility re-export; inspect dependency graph and deprecation options.
6. Change a public member to internal/private and compare compile failures, interface hashes, and rebuild scope.
7. Test wildcard/implicit imports, aliases, and conflicts with local declarations separately from whether the imported item is accessible.
8. Build an external client from emitted interface metadata only; confirm private implementation details are neither required nor accidentally exposed.

Record lexical resolution, access decision, canonical declaration identity, public-path identity, generated API surface, diagnostics, source/ABI compatibility classification, and invalidated consumers.

## 5. Cross-area implications and open hypotheses

- Name resolution and access control are separate phases and should produce separate diagnostics/evidence: “unknown name” differs from “known but inaccessible.”
- The visibility lattice should align with package, module, and workspace structure. More levels offer library encapsulation; fewer levels reduce language and tooling complexity.
- Public re-exports mean the externally visible path need not equal the defining path. Semantic identity should retain both canonical origin and public path/alias, and dependency extraction should record both.
- Public signature validation prevents inaccessible types from leaking through API boundaries, but can constrain abstraction patterns. Opaque/abstract types are a distinct design dimension.
- Identifier-spelling conventions make exports glanceable but introduce case/spelling coupling; keyword modifiers separate naming from visibility but add syntax and default-policy risk.
- Access changes affect downstream compilation and compatibility even when executable behavior is unchanged; they must appear in semantic API hashes and impact analysis.
- Generated code/macros and test-only access can bypass or intentionally widen ordinary boundaries; their authority and provenance need explicit rules if supported.

No LLMLang visibility lattice, export syntax, default, re-export policy, or public-signature restriction is selected.

## 6. Next research and falsifiers

Extend the Scenario 50 resolver fixtures with an explicit access-check phase and module interface export. Compare (A) Rust-style private-by-default nested scopes and restricted re-exports, (B) Go-style package-wide boundary and export-by-identifier, and (C) Swift-style layered access modifiers with public-signature validation. Measure API surface size, accidental exposure, compatibility diagnostics, generated interface stability, and incremental invalidation under moves/renames/access changes.

Fine-grained access is weakened if ordinary use requires pervasive modifiers and access errors dominate; coarse package-only access is weakened if libraries need awkward public wrappers or leak implementation names. Any option is weakened if a facade cannot re-export a stable API without coupling clients to canonical implementation paths, or if interface-only consumers require private files.

## 7. Sources and temporal limits

Official references were consulted 2026-11-19. Rust and Swift documentation are rolling; Go's specification is versioned. Pin compiler/toolchain versions and test interface artifacts before treating implementation behavior as normative.

## Public-interface integration (2026-11-24; proposed)

Follow-up: distinguish a name exported by a catalog from access rights to use it, authority to publish or rebind it, and visibility of private implementation bodies. Public interface metadata can be readable without granting runtime capabilities. Compare alias/re-export, namespace collision, provider hijack, and leaked private dependencies. Name resolution and authorization must not silently select a different operation. No visibility syntax or access policy is selected.

Related: [Public interfaces and verified contract refinement](../RT-05/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This is a candidate follow-up; it does not change accepted rules or previously reported evidence.
